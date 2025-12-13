"""
n8n API service - interact with n8n's REST API for workflow management.
"""

import httpx
import logging
from typing import Dict, Any, Optional, List
from api.config import settings

logger = logging.getLogger(__name__)


class N8nApiService:
    """Service to interact with n8n's REST API."""

    def __init__(self):
        self.base_url = settings.n8n_api_url.rstrip("/")
        self.api_key = settings.n8n_api_key

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

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/workflows",
                    headers=self._get_headers(),
                    json=workflow,
                )
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
                    return {
                        "success": False,
                        "error": f"Failed to create workflow: {error_detail}",
                    }
        except Exception as e:
            logger.error(f"Error creating workflow: {e}")
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

    def generate_notification_test_workflow(
        self, webhook_url: str, api_key: str
    ) -> Dict[str, Any]:
        """
        Generate a test workflow for notification webhook.
        This workflow has a manual trigger and sends a test notification.
        """
        return {
            "name": "Management Console - Test Notifications",
            "nodes": [
                {
                    "parameters": {},
                    "id": "manual-trigger",
                    "name": "Manual Trigger",
                    "type": "n8n-nodes-base.manualTrigger",
                    "typeVersion": 1,
                    "position": [250, 300],
                },
                {
                    "parameters": {
                        "method": "POST",
                        "url": webhook_url,
                        "authentication": "genericCredentialType",
                        "genericAuthType": "httpHeaderAuth",
                        "sendBody": True,
                        "specifyBody": "json",
                        "jsonBody": '={\n  "title": "Test from n8n",\n  "message": "This is a test notification sent from your n8n workflow at {{ $now.format(\'yyyy-MM-dd HH:mm:ss\') }}",\n  "priority": "normal"\n}',
                        "options": {},
                    },
                    "id": "http-request",
                    "name": "Send Notification",
                    "type": "n8n-nodes-base.httpRequest",
                    "typeVersion": 4.2,
                    "position": [470, 300],
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
                    "position": [690, 300],
                },
                {
                    "parameters": {
                        "content": "=## Notification Sent Successfully!\n\n**Channels notified:** {{ $json.channels_notified }}\n\n**Channels:** {{ $json.channels.join(', ') }}",
                        "height": 160,
                        "width": 260,
                    },
                    "id": "note-success",
                    "name": "Success",
                    "type": "n8n-nodes-base.stickyNote",
                    "typeVersion": 1,
                    "position": [910, 180],
                },
                {
                    "parameters": {
                        "content": "=## Notification Failed\n\n**Errors:** {{ $json.errors ? $json.errors.join(', ') : 'Unknown error' }}",
                        "height": 160,
                        "width": 260,
                        "color": 5,
                    },
                    "id": "note-failure",
                    "name": "Failure",
                    "type": "n8n-nodes-base.stickyNote",
                    "typeVersion": 1,
                    "position": [910, 400],
                },
            ],
            "connections": {
                "Manual Trigger": {
                    "main": [[{"node": "Send Notification", "type": "main", "index": 0}]],
                },
                "Send Notification": {
                    "main": [[{"node": "Check Result", "type": "main", "index": 0}]],
                },
                "Check Result": {
                    "main": [
                        [{"node": "Success", "type": "main", "index": 0}],
                        [{"node": "Failure", "type": "main", "index": 0}],
                    ],
                },
            },
            "settings": {
                "executionOrder": "v1",
            },
        }

    async def create_notification_test_workflow(
        self, webhook_url: str, api_key: str
    ) -> Dict[str, Any]:
        """Create the notification test workflow in n8n."""
        workflow = self.generate_notification_test_workflow(webhook_url, api_key)
        return await self.create_workflow(workflow)


# Singleton instance
n8n_api = N8nApiService()
