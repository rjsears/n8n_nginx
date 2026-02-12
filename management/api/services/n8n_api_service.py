"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/services/n8n_api_service.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
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

    # =========================================================================
    # Credential Management Methods
    # =========================================================================

    async def list_credentials(self) -> Dict[str, Any]:
        """List all credentials from n8n."""
        if not self.api_key:
            return {"success": False, "error": "n8n API key not configured"}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/credentials",
                    headers=self._get_headers(),
                )
                if response.status_code == 200:
                    data = response.json()
                    return {"success": True, "credentials": data.get("data", [])}
                elif response.status_code == 401:
                    return {"success": False, "error": "Invalid n8n API key"}
                else:
                    return {
                        "success": False,
                        "error": f"Failed to list credentials: {response.status_code}",
                    }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_credential_schema(self, credential_type: str) -> Dict[str, Any]:
        """Get the JSON schema for a credential type."""
        if not self.api_key:
            return {"success": False, "error": "n8n API key not configured"}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/credentials/schema/{credential_type}",
                    headers=self._get_headers(),
                )
                if response.status_code == 200:
                    return {"success": True, "schema": response.json()}
                elif response.status_code == 404:
                    return {"success": False, "error": f"Unknown credential type: {credential_type}"}
                else:
                    return {
                        "success": False,
                        "error": f"Failed to get schema: {response.status_code}",
                    }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def find_credential_by_name(self, name: str, credential_type: str = None) -> Optional[Dict[str, Any]]:
        """Find a credential by name, optionally filtering by type."""
        result = await self.list_credentials()
        if not result["success"]:
            return None

        for cred in result["credentials"]:
            if cred.get("name") == name:
                if credential_type is None or cred.get("type") == credential_type:
                    return cred
        return None

    async def create_header_auth_credential(
        self, name: str, header_name: str, header_value: str
    ) -> Dict[str, Any]:
        """
        Create a Header Auth credential in n8n.

        Args:
            name: Display name for the credential (e.g., "Management Webhook API Key")
            header_name: The HTTP header name (e.g., "X-API-Key")
            header_value: The header value (the actual API key)

        Returns:
            Dict with success status, credential_id, and full credential object
        """
        if not self.api_key:
            return {"success": False, "error": "n8n API key not configured"}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"Creating Header Auth credential: {name}")
                response = await client.post(
                    f"{self.base_url}/credentials",
                    headers=self._get_headers(),
                    json={
                        "name": name,
                        "type": "httpHeaderAuth",
                        "data": {
                            "name": header_name,
                            "value": header_value
                        }
                    }
                )

                if response.status_code in (200, 201):
                    cred = response.json()
                    logger.info(f"Created credential with ID: {cred.get('id')}")
                    return {
                        "success": True,
                        "credential_id": cred.get("id"),
                        "credential": cred
                    }
                elif response.status_code == 401:
                    return {"success": False, "error": "Invalid n8n API key"}
                elif response.status_code == 400:
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("message", response.text)
                    except Exception:
                        error_msg = response.text
                    logger.error(f"Credential creation failed (400): {error_msg}")
                    return {"success": False, "error": f"Invalid credential data: {error_msg}"}
                else:
                    error_msg = response.text
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("message", error_msg)
                    except Exception:
                        pass
                    logger.error(f"Credential creation failed ({response.status_code}): {error_msg}")
                    return {
                        "success": False,
                        "error": f"Failed to create credential ({response.status_code}): {error_msg}",
                    }
        except httpx.ConnectError:
            return {"success": False, "error": "Cannot connect to n8n API"}
        except Exception as e:
            logger.error(f"Error creating credential: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def delete_credential(self, credential_id: str) -> Dict[str, Any]:
        """Delete a credential by ID."""
        if not self.api_key:
            return {"success": False, "error": "n8n API key not configured"}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(
                    f"{self.base_url}/credentials/{credential_id}",
                    headers=self._get_headers(),
                )
                if response.status_code in (200, 204):
                    return {"success": True}
                elif response.status_code == 404:
                    return {"success": False, "error": "Credential not found"}
                elif response.status_code == 401:
                    return {"success": False, "error": "Invalid n8n API key"}
                else:
                    return {
                        "success": False,
                        "error": f"Failed to delete credential: {response.status_code}",
                    }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_or_create_webhook_credential(
        self, webhook_api_key: str, credential_name: str = "Management Webhook API Key"
    ) -> Dict[str, Any]:
        """
        Get existing or create new Header Auth credential for webhook authentication.

        This is the main method to call when setting up test workflows.
        It will reuse an existing credential if one with the same name exists,
        or create a new one if not.

        Args:
            webhook_api_key: The API key for authenticating to management webhooks
            credential_name: Name for the credential in n8n

        Returns:
            Dict with success, credential_id, and whether it was created or reused
        """
        # Check if credential already exists
        existing = await self.find_credential_by_name(credential_name, "httpHeaderAuth")

        if existing:
            logger.info(f"Found existing credential: {credential_name} (ID: {existing.get('id')})")
            return {
                "success": True,
                "credential_id": existing.get("id"),
                "credential": existing,
                "created": False,
                "message": "Using existing credential"
            }

        # Create new credential
        result = await self.create_header_auth_credential(
            name=credential_name,
            header_name="X-API-Key",
            header_value=webhook_api_key
        )

        if result["success"]:
            result["created"] = True
            result["message"] = "Created new credential"

        return result

    def generate_broadcast_test_workflow(
        self, webhook_url: str, credential_id: str = None
    ) -> Dict[str, Any]:
        """
        Generate a test workflow that broadcasts to ALL webhook-enabled channels.
        Uses targets: ["all"]

        Args:
            webhook_url: The webhook URL for the management console
            credential_id: Optional n8n credential ID. If provided, the workflow
                          will be pre-configured with this credential.
        """
        # Determine instruction text based on whether credential is pre-configured
        if credential_id:
            instructions = (
                "# 📢 Broadcast Test Workflow\n\n"
                "## What This Does\nSends a notification to **ALL** webhook-enabled channels.\n\n"
                "## Ready to Use!\n"
                "The credential has been **automatically configured** for you.\n\n"
                "Just click **Execute Workflow** to test!\n\n"
                "## Targeting\n"
                "This workflow uses `\"targets\": [\"all\"]` which sends to every channel "
                "that has **Webhook Enabled** checked."
            )
        else:
            instructions = (
                "# 📢 Broadcast Test Workflow\n\n"
                "## What This Does\nSends a notification to **ALL** webhook-enabled channels.\n\n"
                "## Setup Instructions\n"
                "1. Click on the **Send to All Channels** node\n"
                "2. Create a new **Header Auth** credential:\n"
                "   - **Name**: `X-API-Key`\n"
                "   - **Value**: Your webhook API key from Management Console\n"
                "3. Save the credential\n"
                "4. Click **Execute Workflow** to test\n\n"
                "## Targeting\n"
                "This workflow uses `\"targets\": [\"all\"]` which sends to every channel "
                "that has **Webhook Enabled** checked."
            )

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
                        "content": instructions,
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
                            "id": credential_id or "PLACEHOLDER",
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
        self, webhook_url: str, credential_id: str = None
    ) -> Dict[str, Any]:
        """
        Generate a test workflow that targets a SPECIFIC channel by slug.
        User must edit the channel slug in the JSON body.

        Args:
            webhook_url: The webhook URL for the management console
            credential_id: Optional n8n credential ID. If provided, the workflow
                          will be pre-configured with this credential.
        """
        # Determine instruction text based on whether credential is pre-configured
        if credential_id:
            instructions = (
                "# 🎯 Channel Targeting Test\n\n"
                "## What This Does\nSends a notification to a **SPECIFIC** channel using its slug.\n\n"
                "## Setup Instructions\n"
                "1. **Find your channel slug** in Management Console → Notifications → Channels tab\n"
                "2. Click on the **Send to Channel** node\n"
                "3. Edit the JSON body and replace `YOUR_CHANNEL_SLUG` with your actual slug\n"
                "4. Click **Execute Workflow** to test\n\n"
                "✅ **Credential is already configured!**\n\n"
                "## Example Slugs\n- `devops_slack`\n- `alerts_email`\n- `mobile_push`\n\n"
                "## Targeting Syntax\n`\"targets\": [\"channel:your_slug\"]`"
            )
        else:
            instructions = (
                "# 🎯 Channel Targeting Test\n\n"
                "## What This Does\nSends a notification to a **SPECIFIC** channel using its slug.\n\n"
                "## Setup Instructions\n"
                "1. **Find your channel slug** in Management Console → Notifications → Channels tab\n"
                "2. Click on the **Send to Channel** node\n"
                "3. Edit the JSON body and replace `YOUR_CHANNEL_SLUG` with your actual slug\n"
                "4. Create a new **Header Auth** credential:\n"
                "   - **Name**: `X-API-Key`\n"
                "   - **Value**: Your webhook API key\n"
                "5. Click **Execute Workflow** to test\n\n"
                "## Example Slugs\n- `devops_slack`\n- `alerts_email`\n- `mobile_push`\n\n"
                "## Targeting Syntax\n`\"targets\": [\"channel:your_slug\"]`"
            )

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
                        "content": instructions,
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
                            "id": credential_id or "PLACEHOLDER",
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
        self, webhook_url: str, credential_id: str = None
    ) -> Dict[str, Any]:
        """
        Generate a test workflow that targets a notification GROUP.
        User must edit the group slug in the JSON body.

        Args:
            webhook_url: The webhook URL for the management console
            credential_id: Optional n8n credential ID. If provided, the workflow
                          will be pre-configured with this credential.
        """
        # Determine instruction text based on whether credential is pre-configured
        if credential_id:
            instructions = (
                "# 👥 Group Targeting Test\n\n"
                "## What This Does\nSends a notification to **ALL channels in a group** using the group's slug.\n\n"
                "## Setup Instructions\n"
                "1. **Create a group** in Management Console → Notifications → Groups tab\n"
                "2. **Add channels** to the group\n"
                "3. Click on the **Send to Group** node\n"
                "4. Edit the JSON body and replace `YOUR_GROUP_SLUG` with your actual group slug\n"
                "5. Click **Execute Workflow** to test\n\n"
                "✅ **Credential is already configured!**\n\n"
                "## Example Groups\n- `devops` → All DevOps team channels\n"
                "- `critical_alerts` → High-priority channels\n- `management` → Management team\n\n"
                "## Targeting Syntax\n`\"targets\": [\"group:your_slug\"]`"
            )
        else:
            instructions = (
                "# 👥 Group Targeting Test\n\n"
                "## What This Does\nSends a notification to **ALL channels in a group** using the group's slug.\n\n"
                "## Setup Instructions\n"
                "1. **Create a group** in Management Console → Notifications → Groups tab\n"
                "2. **Add channels** to the group\n"
                "3. Click on the **Send to Group** node\n"
                "4. Edit the JSON body and replace `YOUR_GROUP_SLUG` with your actual group slug\n"
                "5. Create a new **Header Auth** credential:\n"
                "   - **Name**: `X-API-Key`\n"
                "   - **Value**: Your webhook API key\n"
                "6. Click **Execute Workflow** to test\n\n"
                "## Example Groups\n- `devops` → All DevOps team channels\n"
                "- `critical_alerts` → High-priority channels\n- `management` → Management team\n\n"
                "## Targeting Syntax\n`\"targets\": [\"group:your_slug\"]`"
            )

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
                        "content": instructions,
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
                            "id": credential_id or "PLACEHOLDER",
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
        self, webhook_url: str, api_key: str, credential_id: str = None
    ) -> Dict[str, Any]:
        """
        Generate a test workflow for notification webhook.
        This workflow has a manual trigger and sends a test notification.
        DEPRECATED: Use generate_broadcast_test_workflow instead.
        """
        # For backwards compatibility, generate the broadcast workflow
        return self.generate_broadcast_test_workflow(webhook_url, credential_id)

    async def create_notification_test_workflow(
        self, webhook_url: str, api_key: str
    ) -> Dict[str, Any]:
        """
        Create the notification test workflow in n8n (broadcasts to all).
        Automatically creates/reuses the Header Auth credential.
        """
        # First, get or create the webhook credential
        cred_result = await self.get_or_create_webhook_credential(api_key)
        credential_id = cred_result.get("credential_id") if cred_result["success"] else None

        if not cred_result["success"]:
            logger.warning(f"Could not create credential: {cred_result.get('error')}")
            # Continue anyway - workflow will have placeholder credential

        workflow = self.generate_broadcast_test_workflow(webhook_url, credential_id)
        result = await self.create_workflow(workflow)

        # Include credential info in result
        if result["success"] and cred_result["success"]:
            result["credential_id"] = credential_id
            result["credential_created"] = cred_result.get("created", False)

        return result

    async def create_channel_test_workflow(
        self, webhook_url: str, webhook_api_key: str = None
    ) -> Dict[str, Any]:
        """
        Create a workflow that targets a specific channel.
        Automatically creates/reuses the Header Auth credential if api_key provided.
        """
        credential_id = None
        if webhook_api_key:
            cred_result = await self.get_or_create_webhook_credential(webhook_api_key)
            credential_id = cred_result.get("credential_id") if cred_result["success"] else None

        workflow = self.generate_channel_test_workflow(webhook_url, credential_id)
        result = await self.create_workflow(workflow)

        if result["success"] and credential_id:
            result["credential_id"] = credential_id

        return result

    async def create_group_test_workflow(
        self, webhook_url: str, webhook_api_key: str = None
    ) -> Dict[str, Any]:
        """
        Create a workflow that targets a notification group.
        Automatically creates/reuses the Header Auth credential if api_key provided.
        """
        credential_id = None
        if webhook_api_key:
            cred_result = await self.get_or_create_webhook_credential(webhook_api_key)
            credential_id = cred_result.get("credential_id") if cred_result["success"] else None

        workflow = self.generate_group_test_workflow(webhook_url, credential_id)
        result = await self.create_workflow(workflow)

        if result["success"] and credential_id:
            result["credential_id"] = credential_id

        return result


# Singleton instance
n8n_api = N8nApiService()
