"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/services/n8n_api_service.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richardjsears@gmail.com
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

import httpx
import logging
import os
from typing import Dict, Any, Optional, List
from api.config import settings

logger = logging.getLogger(__name__)

# Path to the mounted .env file (via ./:/app/host_project:rw)
HOST_ENV_PATH = "/app/host_project/.env"


def _read_env_file_value(key: str) -> Optional[str]:
    """Read a value directly from the .env file."""
    try:
        if os.path.exists(HOST_ENV_PATH):
            with open(HOST_ENV_PATH, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        if k.strip() == key:
                            # Remove surrounding quotes if present
                            v = v.strip()
                            if (v.startswith('"') and v.endswith('"')) or \
                               (v.startswith("'") and v.endswith("'")):
                                v = v[1:-1]
                            return v
    except Exception as e:
        logger.warning(f"Failed to read {key} from .env file: {e}")
    return None


class N8nApiService:
    """Service to interact with n8n's REST API."""

    def __init__(self):
        self.base_url = settings.n8n_api_url.rstrip("/")

    @property
    def api_key(self) -> Optional[str]:
        """
        Get the API key dynamically, checking multiple sources.
        Priority: os.environ > .env file > settings (cached at startup)
        This allows the key to be updated at runtime without restart.
        """
        # First check os.environ (updated by settings API)
        key = os.environ.get("N8N_API_KEY")
        if key:
            return key

        # Then read directly from the .env file (most reliable for runtime updates)
        key = _read_env_file_value("N8N_API_KEY")
        if key:
            return key

        # Fall back to settings (cached at startup)
        return settings.n8n_api_key

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for n8n API requests."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["X-N8N-API-KEY"] = self.api_key
        return headers

    def is_configured(self) -> bool:
        """Check if n8n API is configured."""
        return bool(self.api_key)

    async def test_connection(self) -> Dict[str, Any]:
        """Test connection to n8n API."""
        if not self.api_key:
            return {
                "success": False,
                "error": "n8n API key not configured. Set N8N_API_KEY in environment.",
            }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/workflows",
                    headers=self._get_headers(),
                    params={"limit": 1},
                )
                if response.status_code == 200:
                    return {"success": True, "message": "Connected to n8n API"}
                elif response.status_code == 401:
                    return {"success": False, "error": "Invalid n8n API key"}
                else:
                    return {
                        "success": False,
                        "error": f"n8n API returned status {response.status_code}",
                    }
        except httpx.ConnectError:
            return {"success": False, "error": "Cannot connect to n8n API"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def list_workflows(self, limit: int = 100) -> Dict[str, Any]:
        """List workflows from n8n."""
        if not self.api_key:
            return {"success": False, "error": "n8n API key not configured"}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/workflows",
                    headers=self._get_headers(),
                    params={"limit": limit},
                )
                if response.status_code == 200:
                    data = response.json()
                    return {"success": True, "workflows": data.get("data", [])}
                else:
                    return {
                        "success": False,
                        "error": f"Failed to list workflows: {response.status_code}",
                    }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def create_workflow(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new workflow in n8n."""
        if not self.api_key:
            return {"success": False, "error": "n8n API key not configured"}

        # Strip fields that n8n doesn't accept when creating new workflows
        # These are n8n-internal fields that get generated by n8n itself
        workflow_clean = {k: v for k, v in workflow.items() if k not in (
            "id", "versionId", "meta", "tags", "createdAt", "updatedAt"
        )}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"Creating workflow: {workflow_clean.get('name')}")
                response = await client.post(
                    f"{self.base_url}/workflows",
                    headers=self._get_headers(),
                    json=workflow_clean,
                )
                logger.info(f"n8n response status: {response.status_code}")
                if response.status_code in (200, 201):
                    data = response.json()
                    return {
                        "success": True,
                        "workflow": data,
                        "workflow_id": data.get("id"),
                    }
                else:
                    error_detail = response.text
                    try:
                        error_json = response.json()
                        error_detail = error_json.get("message", error_detail)
                    except Exception:
                        pass
                    logger.error(f"n8n workflow creation failed: {response.status_code} - {error_detail}")
                    return {
                        "success": False,
                        "error": f"Failed to create workflow ({response.status_code}): {error_detail}",
                    }
        except Exception as e:
            logger.error(f"Error creating workflow: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def get_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Get a workflow by ID."""
        if not self.api_key:
            return {"success": False, "error": "n8n API key not configured"}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/workflows/{workflow_id}",
                    headers=self._get_headers(),
                )
                if response.status_code == 200:
                    return {"success": True, "workflow": response.json()}
                elif response.status_code == 404:
                    return {"success": False, "error": "Workflow not found"}
                else:
                    return {
                        "success": False,
                        "error": f"Failed to get workflow: {response.status_code}",
                    }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def activate_workflow(self, workflow_id: str, active: bool = True) -> Dict[str, Any]:
        """Activate or deactivate a workflow using n8n public API."""
        if not self.api_key:
            return {"success": False, "error": "n8n API key not configured"}

        # n8n public API uses separate endpoints for activate/deactivate
        endpoint = "activate" if active else "deactivate"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/workflows/{workflow_id}/{endpoint}",
                    headers=self._get_headers(),
                )
                if response.status_code == 200:
                    return {"success": True, "workflow": response.json()}
                elif response.status_code == 401:
                    return {"success": False, "error": "Invalid n8n API key"}
                elif response.status_code == 404:
                    return {"success": False, "error": "Workflow not found"}
                else:
                    # Try to get error details from response
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("message", response.text)
                    except Exception:
                        error_msg = response.text
                    return {
                        "success": False,
                        "error": f"Failed to {endpoint} workflow ({response.status_code}): {error_msg}",
                    }
        except httpx.ConnectError:
            return {"success": False, "error": "Cannot connect to n8n API"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def execute_workflow(self, workflow_id: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute a workflow manually.
        Note: The n8n public API doesn't have a direct execute endpoint.
        Workflows should typically be triggered via webhooks.
        This uses the internal REST API which may not be available in all setups.
        """
        if not self.api_key:
            return {"success": False, "error": "n8n API key not configured"}

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Try the public API endpoint first (may not exist in all versions)
                response = await client.post(
                    f"{self.base_url}/workflows/{workflow_id}/run",
                    headers=self._get_headers(),
                    json=data or {},
                )

                if response.status_code == 200:
                    result = response.json()
                    return {
                        "success": True,
                        "execution_id": result.get("data", {}).get("executionId"),
                        "data": result,
                    }
                elif response.status_code == 404:
                    # Endpoint doesn't exist or workflow not found
                    return {
                        "success": False,
                        "error": "Workflow not found or execute endpoint not available. "
                                 "Try using a webhook trigger instead.",
                    }
                elif response.status_code == 401:
                    return {"success": False, "error": "Invalid n8n API key"}
                elif response.status_code == 400:
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("message", response.text)
                    except Exception:
                        error_msg = response.text
                    return {"success": False, "error": f"Cannot execute: {error_msg}"}
                else:
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("message", response.text)
                    except Exception:
                        error_msg = response.text
                    return {
                        "success": False,
                        "error": f"Execute failed ({response.status_code}): {error_msg}",
                    }
        except httpx.ConnectError:
            return {"success": False, "error": "Cannot connect to n8n API"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def generate_broadcast_test_workflow(
        self, webhook_url: str
    ) -> Dict[str, Any]:
        """
        Generate a test workflow that broadcasts to ALL webhook-enabled channels.
        Uses targets: ["all"]
        """
        return {
            "name": "Notification Test - Broadcast to All Channels",
            "nodes": [
                {
                    "parameters": {
                        "content": "![](https://github.com/rjsears/n8n_nginx/blob/main/images/n8n_repo_banner.jpg?raw=true)",
                        "height": 416,
                        "width": 704,
                    },
                    "id": "banner-image",
                    "name": "Banner",
                    "type": "n8n-nodes-base.stickyNote",
                    "typeVersion": 1,
                    "position": [384, -288],
                },
                {
                    "parameters": {
                        "content": "# 📢 Broadcast Test Workflow\n\n## What This Does\nSends a notification to **ALL** webhook-enabled channels.\n\n## Setup Instructions\n1. Click on the **Send to All Channels** node\n2. Create a new **Header Auth** credential:\n   - **Name**: `X-API-Key`\n   - **Value**: Your webhook API key from Management Console\n3. Save the credential\n4. Click **Execute Workflow** to test\n\n## Targeting\nThis workflow uses `\"targets\": [\"all\"]` which sends to every channel that has **Webhook Enabled** checked.",
                        "height": 612,
                        "width": 320,
                        "color": 4,
                    },
                    "id": "note-instructions",
                    "name": "Setup Instructions",
                    "type": "n8n-nodes-base.stickyNote",
                    "typeVersion": 1,
                    "position": [-64, -208],
                },
                {
                    "parameters": {},
                    "id": "manual-trigger",
                    "name": "Click to Test",
                    "type": "n8n-nodes-base.manualTrigger",
                    "typeVersion": 1,
                    "position": [416, 192],
                },
                {
                    "parameters": {
                        "method": "POST",
                        "url": webhook_url,
                        "authentication": "genericCredentialType",
                        "genericAuthType": "httpHeaderAuth",
                        "sendBody": True,
                        "specifyBody": "json",
                        "jsonBody": '={\n  "title": "📢 Broadcast Test",\n  "message": "This notification was sent to ALL webhook-enabled channels at {{ $now.format(\'yyyy-MM-dd HH:mm:ss\') }}",\n  "priority": "normal",\n  "targets": ["all"]\n}',
                        "options": {},
                    },
                    "id": "http-request",
                    "name": "Send to All Channels",
                    "type": "n8n-nodes-base.httpRequest",
                    "typeVersion": 4.2,
                    "position": [640, 192],
                    "credentials": {
                        "httpHeaderAuth": {
                            "id": "PLACEHOLDER",
                            "name": "Management Webhook API Key",
                        },
                    },
                },
                {
                    "parameters": {
                        "conditions": {
                            "options": {
                                "caseSensitive": True,
                                "leftValue": "",
                                "typeValidation": "strict",
                            },
                            "conditions": [
                                {
                                    "id": "condition-success",
                                    "leftValue": "={{ $json.success }}",
                                    "rightValue": True,
                                    "operator": {
                                        "type": "boolean",
                                        "operation": "equals",
                                    },
                                },
                            ],
                            "combinator": "and",
                        },
                        "options": {},
                    },
                    "id": "if-success",
                    "name": "Check Result",
                    "type": "n8n-nodes-base.if",
                    "typeVersion": 2,
                    "position": [848, 192],
                },
                {
                    "parameters": {
                        "content": "=## ✅ Success!\n\n**Channels notified:** {{ $json.channels_notified }}\n\n**Channels:** {{ $json.channels.join(', ') }}",
                        "width": 280,
                        "color": 4,
                    },
                    "id": "note-success",
                    "name": "Success Output",
                    "type": "n8n-nodes-base.stickyNote",
                    "typeVersion": 1,
                    "position": [1232, 368],
                },
                {
                    "parameters": {
                        "content": "=## ❌ Failed\n\n**Errors:** {{ $json.errors ? $json.errors.join(', ') : ($json.detail || 'Unknown error') }}",
                        "width": 280,
                        "color": 5,
                    },
                    "id": "note-failure",
                    "name": "Error Output",
                    "type": "n8n-nodes-base.stickyNote",
                    "typeVersion": 1,
                    "position": [912, 496],
                },
            ],
            "connections": {
                "Click to Test": {
                    "main": [[{"node": "Send to All Channels", "type": "main", "index": 0}]],
                },
                "Send to All Channels": {
                    "main": [[{"node": "Check Result", "type": "main", "index": 0}]],
                },
                "Check Result": {
                    "main": [
                        [{"node": "Success Output", "type": "main", "index": 0}],
                        [{"node": "Error Output", "type": "main", "index": 0}],
                    ],
                },
            },
            "settings": {
                "executionOrder": "v1",
            },
        }

    def generate_channel_test_workflow(
        self, webhook_url: str
    ) -> Dict[str, Any]:
        """
        Generate a test workflow that targets a SPECIFIC channel by slug.
        User must edit the channel slug in the JSON body.
        """
        return {
            "name": "Notification Test - Target Specific Channel",
            "nodes": [
                {
                    "parameters": {
                        "content": "![](https://github.com/rjsears/n8n_nginx/blob/main/images/n8n_repo_banner.jpg?raw=true)",
                        "height": 384,
                        "width": 656,
                    },
                    "id": "banner-image",
                    "name": "Banner",
                    "type": "n8n-nodes-base.stickyNote",
                    "typeVersion": 1,
                    "position": [400, -944],
                },
                {
                    "parameters": {
                        "content": "# 🎯 Channel Targeting Test\n\n## What This Does\nSends a notification to a **SPECIFIC** channel using its slug.\n\n## Setup Instructions\n1. **Find your channel slug** in Management Console → Notifications → Channels tab\n2. Click on the **Send to Channel** node\n3. Edit the JSON body and replace `YOUR_CHANNEL_SLUG` with your actual slug\n4. Create a new **Header Auth** credential:\n   - **Name**: `X-API-Key`\n   - **Value**: Your webhook API key\n5. Click **Execute Workflow** to test\n\n## Example Slugs\n- `devops_slack`\n- `alerts_email`\n- `mobile_push`\n\n## Targeting Syntax\n`\"targets\": [\"channel:your_slug\"]`",
                        "height": 712,
                        "width": 340,
                        "color": 6,
                    },
                    "id": "note-instructions",
                    "name": "Setup Instructions",
                    "type": "n8n-nodes-base.stickyNote",
                    "typeVersion": 1,
                    "position": [-64, -912],
                },
                {
                    "parameters": {},
                    "id": "manual-trigger",
                    "name": "Click to Test",
                    "type": "n8n-nodes-base.manualTrigger",
                    "typeVersion": 1,
                    "position": [416, -464],
                },
                {
                    "parameters": {
                        "method": "POST",
                        "url": webhook_url,
                        "authentication": "genericCredentialType",
                        "genericAuthType": "httpHeaderAuth",
                        "sendBody": True,
                        "specifyBody": "json",
                        "jsonBody": '={\n  "title": "🎯 Channel Test",\n  "message": "This notification was sent to a SPECIFIC channel at {{ $now.format(\'yyyy-MM-dd HH:mm:ss\') }}",\n  "priority": "normal",\n  "targets": ["channel:YOUR_CHANNEL_SLUG"]\n}',
                        "options": {},
                    },
                    "id": "http-request",
                    "name": "Send to Channel",
                    "type": "n8n-nodes-base.httpRequest",
                    "typeVersion": 4.2,
                    "position": [640, -464],
                    "credentials": {
                        "httpHeaderAuth": {
                            "id": "PLACEHOLDER",
                            "name": "Management Webhook API Key",
                        },
                    },
                },
                {
                    "parameters": {
                        "conditions": {
                            "options": {
                                "caseSensitive": True,
                                "leftValue": "",
                                "typeValidation": "strict",
                            },
                            "conditions": [
                                {
                                    "id": "condition-success",
                                    "leftValue": "={{ $json.success }}",
                                    "rightValue": True,
                                    "operator": {
                                        "type": "boolean",
                                        "operation": "equals",
                                    },
                                },
                            ],
                            "combinator": "and",
                        },
                        "options": {},
                    },
                    "id": "if-success",
                    "name": "Check Result",
                    "type": "n8n-nodes-base.if",
                    "typeVersion": 2,
                    "position": [864, -464],
                },
                {
                    "parameters": {
                        "content": "=## ✅ Success!\n\n**Channels notified:** {{ $json.channels_notified }}\n\n**Channel:** {{ $json.channels.join(', ') }}",
                        "width": 280,
                        "color": 4,
                    },
                    "id": "note-success",
                    "name": "Success Output",
                    "type": "n8n-nodes-base.stickyNote",
                    "typeVersion": 1,
                    "position": [1216, -336],
                },
                {
                    "parameters": {
                        "content": "=## ❌ Failed\n\n**Errors:** {{ $json.errors ? $json.errors.join(', ') : ($json.detail || 'Unknown error') }}\n\n**Common Issues:**\n- Channel slug doesn't exist\n- Channel not webhook-enabled\n- Invalid API key",
                        "height": 200,
                        "width": 280,
                        "color": 5,
                    },
                    "id": "note-failure",
                    "name": "Error Output",
                    "type": "n8n-nodes-base.stickyNote",
                    "typeVersion": 1,
                    "position": [928, -144],
                },
            ],
            "connections": {
                "Click to Test": {
                    "main": [[{"node": "Send to Channel", "type": "main", "index": 0}]],
                },
                "Send to Channel": {
                    "main": [[{"node": "Check Result", "type": "main", "index": 0}]],
                },
                "Check Result": {
                    "main": [
                        [{"node": "Success Output", "type": "main", "index": 0}],
                        [{"node": "Error Output", "type": "main", "index": 0}],
                    ],
                },
            },
            "settings": {
                "executionOrder": "v1",
            },
        }

    def generate_group_test_workflow(
        self, webhook_url: str
    ) -> Dict[str, Any]:
        """
        Generate a test workflow that targets a notification GROUP.
        User must edit the group slug in the JSON body.
        """
        return {
            "name": "Notification Test - Target Group",
            "nodes": [
                {
                    "parameters": {
                        "content": "![](https://github.com/rjsears/n8n_nginx/blob/main/images/n8n_repo_banner.jpg?raw=true)",
                        "height": 400,
                        "width": 640,
                    },
                    "id": "banner-image",
                    "name": "Banner",
                    "type": "n8n-nodes-base.stickyNote",
                    "typeVersion": 1,
                    "position": [464, -304],
                },
                {
                    "parameters": {
                        "content": "# 👥 Group Targeting Test\n\n## What This Does\nSends a notification to **ALL channels in a group** using the group's slug.\n\n## Setup Instructions\n1. **Create a group** in Management Console → Notifications → Groups tab\n2. **Add channels** to the group\n3. Click on the **Send to Group** node\n4. Edit the JSON body and replace `YOUR_GROUP_SLUG` with your actual group slug\n5. Create a new **Header Auth** credential:\n   - **Name**: `X-API-Key`\n   - **Value**: Your webhook API key\n6. Click **Execute Workflow** to test\n\n## Example Groups\n- `devops` → All DevOps team channels\n- `critical_alerts` → High-priority channels\n- `management` → Management team\n\n## Targeting Syntax\n`\"targets\": [\"group:your_slug\"]`",
                        "height": 756,
                        "width": 360,
                        "color": 3,
                    },
                    "id": "note-instructions",
                    "name": "Setup Instructions",
                    "type": "n8n-nodes-base.stickyNote",
                    "typeVersion": 1,
                    "position": [0, -288],
                },
                {
                    "parameters": {},
                    "id": "manual-trigger",
                    "name": "Click to Test",
                    "type": "n8n-nodes-base.manualTrigger",
                    "typeVersion": 1,
                    "position": [464, 160],
                },
                {
                    "parameters": {
                        "method": "POST",
                        "url": webhook_url,
                        "authentication": "genericCredentialType",
                        "genericAuthType": "httpHeaderAuth",
                        "sendBody": True,
                        "specifyBody": "json",
                        "jsonBody": '={\n  "title": "👥 Group Test",\n  "message": "This notification was sent to ALL channels in a GROUP at {{ $now.format(\'yyyy-MM-dd HH:mm:ss\') }}",\n  "priority": "normal",\n  "targets": ["group:YOUR_GROUP_SLUG"]\n}',
                        "options": {},
                    },
                    "id": "http-request",
                    "name": "Send to Group",
                    "type": "n8n-nodes-base.httpRequest",
                    "typeVersion": 4.2,
                    "position": [688, 160],
                    "credentials": {
                        "httpHeaderAuth": {
                            "id": "PLACEHOLDER",
                            "name": "Management Webhook API Key",
                        },
                    },
                },
                {
                    "parameters": {
                        "conditions": {
                            "options": {
                                "caseSensitive": True,
                                "leftValue": "",
                                "typeValidation": "strict",
                            },
                            "conditions": [
                                {
                                    "id": "condition-success",
                                    "leftValue": "={{ $json.success }}",
                                    "rightValue": True,
                                    "operator": {
                                        "type": "boolean",
                                        "operation": "equals",
                                    },
                                },
                            ],
                            "combinator": "and",
                        },
                        "options": {},
                    },
                    "id": "if-success",
                    "name": "Check Result",
                    "type": "n8n-nodes-base.if",
                    "typeVersion": 2,
                    "position": [912, 160],
                },
                {
                    "parameters": {
                        "content": "=## ✅ Success!\n\n**Channels notified:** {{ $json.channels_notified }}\n\n**Channels in group:** {{ $json.channels.join(', ') }}",
                        "width": 300,
                        "color": 4,
                    },
                    "id": "note-success",
                    "name": "Success Output",
                    "type": "n8n-nodes-base.stickyNote",
                    "typeVersion": 1,
                    "position": [1264, 352],
                },
                {
                    "parameters": {
                        "content": "=## ❌ Failed\n\n**Errors:** {{ $json.errors ? $json.errors.join(', ') : ($json.detail || 'Unknown error') }}\n\n**Common Issues:**\n- Group slug doesn't exist\n- Group is disabled\n- No channels in group\n- Invalid API key",
                        "height": 220,
                        "width": 300,
                        "color": 5,
                    },
                    "id": "note-failure",
                    "name": "Error Output",
                    "type": "n8n-nodes-base.stickyNote",
                    "typeVersion": 1,
                    "position": [912, 432],
                },
            ],
            "connections": {
                "Click to Test": {
                    "main": [[{"node": "Send to Group", "type": "main", "index": 0}]],
                },
                "Send to Group": {
                    "main": [[{"node": "Check Result", "type": "main", "index": 0}]],
                },
                "Check Result": {
                    "main": [
                        [{"node": "Success Output", "type": "main", "index": 0}],
                        [{"node": "Error Output", "type": "main", "index": 0}],
                    ],
                },
            },
            "settings": {
                "executionOrder": "v1",
            },
        }

    def generate_notification_test_workflow(
        self, webhook_url: str, api_key: str
    ) -> Dict[str, Any]:
        """
        Generate a test workflow for notification webhook.
        This workflow has a manual trigger and sends a test notification.
        DEPRECATED: Use generate_broadcast_test_workflow instead.
        """
        # For backwards compatibility, generate the broadcast workflow
        return self.generate_broadcast_test_workflow(webhook_url)

    async def create_notification_test_workflow(
        self, webhook_url: str, api_key: str
    ) -> Dict[str, Any]:
        """Create the notification test workflow in n8n (broadcasts to all)."""
        workflow = self.generate_broadcast_test_workflow(webhook_url)
        return await self.create_workflow(workflow)

    async def create_channel_test_workflow(
        self, webhook_url: str
    ) -> Dict[str, Any]:
        """Create a workflow that targets a specific channel."""
        workflow = self.generate_channel_test_workflow(webhook_url)
        return await self.create_workflow(workflow)

    async def create_group_test_workflow(
        self, webhook_url: str
    ) -> Dict[str, Any]:
        """Create a workflow that targets a notification group."""
        workflow = self.generate_group_test_workflow(webhook_url)
        return await self.create_workflow(workflow)


# Singleton instance
n8n_api = N8nApiService()
