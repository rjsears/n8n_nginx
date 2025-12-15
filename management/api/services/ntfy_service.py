"""
NTFY Service - Handle all interactions with the NTFY server.
Provides message sending, health checks, and template processing.
"""

import httpx
import logging
import os
import re
from typing import Dict, Any, Optional, List
from datetime import datetime, UTC

logger = logging.getLogger(__name__)

# Priority level mappings
PRIORITY_NAMES = {
    1: "min",
    2: "low",
    3: "default",
    4: "high",
    5: "urgent"
}

PRIORITY_VALUES = {
    "min": 1,
    "low": 2,
    "default": 3,
    "high": 4,
    "urgent": 5,
    "max": 5
}

# Common emoji shortcodes for quick reference
COMMON_EMOJIS = {
    # Status
    "success": ["white_check_mark", "heavy_check_mark", "tada", "+1", "thumbsup"],
    "warning": ["warning", "exclamation", "bangbang"],
    "error": ["x", "no_entry", "skull", "rotating_light", "sos"],
    "info": ["information_source", "bulb", "memo"],

    # Actions
    "start": ["rocket", "arrow_forward", "play_or_pause_button"],
    "stop": ["stop_sign", "octagonal_sign", "hand"],
    "restart": ["arrows_counterclockwise", "recycle"],

    # System
    "server": ["computer", "desktop_computer", "server"],
    "database": ["floppy_disk", "cd", "dvd"],
    "network": ["globe_with_meridians", "satellite", "signal_strength"],
    "security": ["lock", "key", "shield"],

    # Backup
    "backup": ["package", "file_folder", "inbox_tray"],
    "restore": ["outbox_tray", "arrow_up", "arrow_heading_up"],

    # Time
    "scheduled": ["clock", "alarm_clock", "timer_clock", "hourglass"],
    "expired": ["hourglass_flowing_sand", "stopwatch"],
}


class NtfyService:
    """Service to interact with the NTFY server."""

    def __init__(self, base_url: Optional[str] = None, public_url: Optional[str] = None):
        """
        Initialize the NTFY service.

        Args:
            base_url: NTFY server URL for internal communication. Defaults to local container or env var.
            public_url: NTFY public URL for documentation/examples. Defaults to env var or constructs from DOMAIN.
        """
        # Internal URL for container-to-container communication
        self.base_url = base_url or os.environ.get("NTFY_BASE_URL", "http://n8n_ntfy:80")
        self.base_url = self.base_url.rstrip("/")

        # Public URL for external access (used in examples/documentation)
        if public_url:
            self.public_url = public_url.rstrip("/")
        else:
            # Try NTFY_PUBLIC_URL first, then construct from DOMAIN
            env_public_url = os.environ.get("NTFY_PUBLIC_URL")
            if env_public_url:
                self.public_url = env_public_url.rstrip("/")
            else:
                # Construct from DOMAIN env var (e.g., ntfy.loft.aero)
                domain = os.environ.get("DOMAIN", "")
                if domain:
                    self.public_url = f"https://ntfy.{domain}"
                else:
                    # Fallback to placeholder
                    self.public_url = "https://ntfy.your-domain.com"

    async def health_check(self) -> Dict[str, Any]:
        """
        Check NTFY server health.

        Returns:
            Health status dict with 'healthy' boolean and details.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/v1/health")

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "healthy": data.get("healthy", False),
                        "status": "connected",
                        "message": "NTFY server is healthy",
                        "details": data
                    }
                else:
                    return {
                        "healthy": False,
                        "status": "error",
                        "message": f"NTFY returned status {response.status_code}",
                        "details": None
                    }
        except httpx.ConnectError:
            return {
                "healthy": False,
                "status": "disconnected",
                "message": "Cannot connect to NTFY server",
                "details": None
            }
        except Exception as e:
            logger.error(f"NTFY health check error: {e}")
            return {
                "healthy": False,
                "status": "error",
                "message": str(e),
                "details": None
            }

    async def send_message(
        self,
        topic: str,
        message: str,
        title: Optional[str] = None,
        priority: int = 3,
        tags: Optional[List[str]] = None,
        click: Optional[str] = None,
        attach: Optional[str] = None,
        icon: Optional[str] = None,
        actions: Optional[List[Dict[str, Any]]] = None,
        delay: Optional[str] = None,
        email: Optional[str] = None,
        markdown: bool = False,
        auth_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a message to an NTFY topic.

        Args:
            topic: Target topic name
            message: Message body
            title: Optional message title
            priority: Priority level 1-5
            tags: List of tags/emojis
            click: URL to open on notification click
            attach: Attachment URL
            icon: Custom icon URL
            actions: List of action button definitions
            delay: Delay/schedule string (e.g., "30m", "tomorrow 10am")
            email: Forward notification to this email
            markdown: Enable markdown formatting
            auth_token: Optional authentication token

        Returns:
            Result dict with success status and details.
        """
        try:
            headers = {
                "Content-Type": "application/json",
            }

            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"

            # Build JSON payload
            payload = {
                "topic": topic,
                "message": message,
            }

            if title:
                payload["title"] = title

            if priority != 3:
                payload["priority"] = priority

            if tags:
                payload["tags"] = tags

            if click:
                payload["click"] = click

            if attach:
                payload["attach"] = attach

            if icon:
                payload["icon"] = icon

            if actions:
                payload["actions"] = actions

            if delay:
                payload["delay"] = delay

            if email:
                payload["email"] = email

            if markdown:
                payload["markdown"] = True

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.base_url,
                    headers=headers,
                    json=payload
                )

                if response.status_code in (200, 201):
                    result = response.json()
                    return {
                        "success": True,
                        "message_id": result.get("id"),
                        "topic": topic,
                        "scheduled": delay is not None,
                        "response": result
                    }
                elif response.status_code == 401:
                    return {
                        "success": False,
                        "error": "Authentication required or invalid token",
                        "status_code": 401
                    }
                elif response.status_code == 403:
                    return {
                        "success": False,
                        "error": "Access denied to this topic",
                        "status_code": 403
                    }
                elif response.status_code == 429:
                    return {
                        "success": False,
                        "error": "Rate limit exceeded",
                        "status_code": 429
                    }
                else:
                    error_text = response.text
                    try:
                        error_json = response.json()
                        error_text = error_json.get("error", error_text)
                    except Exception:
                        pass
                    return {
                        "success": False,
                        "error": f"NTFY error ({response.status_code}): {error_text}",
                        "status_code": response.status_code
                    }

        except httpx.ConnectError:
            return {
                "success": False,
                "error": "Cannot connect to NTFY server"
            }
        except Exception as e:
            logger.error(f"Error sending NTFY message: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def send_with_template(
        self,
        topic: str,
        template_name: str,
        data: Dict[str, Any],
        priority: Optional[int] = None,
        extra_tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Send a message using NTFY's built-in template support.

        Args:
            topic: Target topic
            template_name: Template name ('github', 'grafana', 'alertmanager', or custom)
            data: JSON data to be processed by the template
            priority: Override template priority
            extra_tags: Additional tags to append

        Returns:
            Result dict.
        """
        try:
            headers = {
                "Content-Type": "application/json",
                "X-Template": template_name,
            }

            if priority:
                headers["X-Priority"] = str(priority)

            if extra_tags:
                headers["X-Tags"] = ",".join(extra_tags)

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/{topic}",
                    headers=headers,
                    json=data
                )

                if response.status_code in (200, 201):
                    return {
                        "success": True,
                        "response": response.json() if response.text else None
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Template error ({response.status_code}): {response.text}"
                    }

        except Exception as e:
            logger.error(f"Error sending templated message: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def build_action(
        self,
        action_type: str,
        label: str,
        url: Optional[str] = None,
        method: str = "POST",
        headers: Optional[Dict[str, str]] = None,
        body: Optional[str] = None,
        intent: Optional[str] = None,
        extras: Optional[Dict[str, str]] = None,
        clear: bool = False,
    ) -> Dict[str, Any]:
        """
        Build an action button definition.

        Args:
            action_type: 'view', 'http', or 'broadcast'
            label: Button label text
            url: URL for view/http actions
            method: HTTP method for http actions
            headers: Headers for http actions
            body: Body for http actions
            intent: Android intent for broadcast actions
            extras: Android extras for broadcast actions
            clear: Clear notification after action

        Returns:
            Action definition dict.
        """
        action = {
            "action": action_type,
            "label": label,
        }

        if action_type == "view":
            if url:
                action["url"] = url
            if clear:
                action["clear"] = True

        elif action_type == "http":
            if url:
                action["url"] = url
            if method != "POST":
                action["method"] = method
            if headers:
                action["headers"] = headers
            if body:
                action["body"] = body
            if clear:
                action["clear"] = True

        elif action_type == "broadcast":
            if intent:
                action["intent"] = intent
            if extras:
                action["extras"] = extras
            if clear:
                action["clear"] = True

        return action

    def get_priority_name(self, level: int) -> str:
        """Get priority name from numeric level."""
        return PRIORITY_NAMES.get(level, "default")

    def get_priority_value(self, name: str) -> int:
        """Get priority numeric value from name."""
        return PRIORITY_VALUES.get(name.lower(), 3)

    def get_emoji_suggestions(self, category: Optional[str] = None) -> Dict[str, List[str]]:
        """
        Get emoji suggestions by category.

        Args:
            category: Specific category or None for all

        Returns:
            Dict of category -> emoji shortcode list.
        """
        if category:
            return {category: COMMON_EMOJIS.get(category, [])}
        return COMMON_EMOJIS

    def validate_delay(self, delay: str) -> Dict[str, Any]:
        """
        Validate a delay string.

        Args:
            delay: Delay string like "30m", "2h", "tomorrow 10am"

        Returns:
            Validation result with parsed info.
        """
        # Duration pattern: number + unit
        duration_pattern = r'^(\d+)\s*(s|sec|second|seconds|m|min|minute|minutes|h|hour|hours|d|day|days)$'

        # Check duration format
        match = re.match(duration_pattern, delay.strip(), re.IGNORECASE)
        if match:
            value = int(match.group(1))
            unit = match.group(2).lower()

            # Convert to seconds for validation
            multipliers = {
                's': 1, 'sec': 1, 'second': 1, 'seconds': 1,
                'm': 60, 'min': 60, 'minute': 60, 'minutes': 60,
                'h': 3600, 'hour': 3600, 'hours': 3600,
                'd': 86400, 'day': 86400, 'days': 86400,
            }
            seconds = value * multipliers.get(unit, 1)

            # NTFY limits: min 10s, max 3 days
            if seconds < 10:
                return {"valid": False, "error": "Minimum delay is 10 seconds"}
            if seconds > 259200:  # 3 days
                return {"valid": False, "error": "Maximum delay is 3 days"}

            return {
                "valid": True,
                "type": "duration",
                "value": delay,
                "seconds": seconds
            }

        # Timestamp pattern: Unix timestamp
        if delay.isdigit():
            ts = int(delay)
            now = int(datetime.now(UTC).timestamp())
            if ts <= now:
                return {"valid": False, "error": "Timestamp must be in the future"}
            if ts > now + 259200:
                return {"valid": False, "error": "Maximum delay is 3 days"}
            return {
                "valid": True,
                "type": "timestamp",
                "value": delay,
                "seconds": ts - now
            }

        # Natural language - let NTFY handle validation
        natural_patterns = [
            r'tomorrow',
            r'today',
            r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
            r'\d{1,2}:\d{2}\s*(am|pm)?',
            r'\d{1,2}\s*(am|pm)',
        ]

        for pattern in natural_patterns:
            if re.search(pattern, delay, re.IGNORECASE):
                return {
                    "valid": True,
                    "type": "natural",
                    "value": delay,
                    "note": "NTFY will parse this naturally"
                }

        return {
            "valid": False,
            "error": f"Invalid delay format: {delay}"
        }

    def format_message_preview(
        self,
        title: Optional[str],
        message: str,
        priority: int,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Format a message for preview display.

        Returns dict with formatted preview components.
        """
        # Convert tags to emojis where possible (simplified)
        emoji_tags = []
        text_tags = []

        if tags:
            for tag in tags:
                # This is simplified - real implementation would use full emoji list
                if tag in ["warning", "x", "white_check_mark", "tada", "skull", "rocket"]:
                    emoji_tags.append(tag)
                else:
                    text_tags.append(tag)

        return {
            "title": title,
            "message": message,
            "priority": self.get_priority_name(priority),
            "priority_level": priority,
            "emoji_tags": emoji_tags,
            "text_tags": text_tags,
        }


# Create singleton instance
ntfy_service = NtfyService()
