import json
import logging
from typing import Annotated, Literal
from pydantic import Field
from devices import DeviceStore
import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
mcp = FastMCP("Bark Notifications", instructions="Send notifications only with explicit user authorization. One final notification per task unless stages are requested. Never include secrets or full logs.")

def safe_message(value, keys):
    message = str(value)
    for key in sorted(keys, key=len, reverse=True):
        message = message.replace(key, "[REDACTED]")
    return message[:500]


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
def list_bark_devices() -> list[dict]:
    """List configured device names and default status. Never returns Device Keys."""
    return DeviceStore().list()


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False})
def add_bark_device(name: Annotated[str, Field(description="A unique device name, such as iPhone.")], device_key: Annotated[str, Field(description="Secret Bark Device Key supplied explicitly by the user; never echo it.")], set_default: Annotated[bool, Field(description="Set this device as the default.")] = False) -> dict:
    """Save a user-provided Bark device locally, outside the repository. Refuses duplicate names; never returns the Key."""
    return DeviceStore().add(name, device_key, set_default)


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "openWorldHint": False})
def remove_bark_device(name: Annotated[str, Field(description="The configured device name to remove.")]) -> dict:
    """Remove an explicitly selected Bark device. Removing the default clears default_device."""
    return DeviceStore().remove(name)


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False})
def set_default_bark_device(name: Annotated[str, Field(description="An existing device name.")]) -> dict:
    """Select an existing device as the default for notifications without a device argument."""
    return DeviceStore().set_default(name)


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
async def send_bark_notification(
    body: Annotated[str, Field(description="Concise notification text; must not contain secrets.")],
    title: Annotated[str, Field(description="Notification title.")] = "Codex",
    group: Annotated[str, Field(description="Bark notification group.")] = "Codex",
    sound: Annotated[str | None, Field(description="Optional Bark sound name.")] = None,
    level: Annotated[Literal["active", "passive", "timeSensitive", "critical"] | None, Field(description="Notification level; critical requires explicit authorization.")] = None,
    url: Annotated[str | None, Field(description="Optional URL opened when the notification is tapped.")] = None,
    device: Annotated[str | list[str] | None, Field(description="Device name or names; omitted uses the default or sole device.")] = None,
) -> dict:
    """Send explicitly authorized iOS notifications via Bark to named devices. Never needs a Device Key. One final notification per task unless stages are requested. Success means API acceptance, not confirmed device delivery."""
    targets, keys = DeviceStore().resolve(device)
    if not body.strip():
        raise ToolError("body must not be empty.")
    # Validate every target before sending to avoid accidental partial delivery.
    fields = (body, title, group, sound, level, url)
    if any(secret in str(value) for secret in keys for value in fields if value is not None):
        raise ToolError("Notification content must not contain Device Keys.")
    results = []
    for name, key in targets:
        try:
            result = await _send_one(key, keys, body, title, group, sound, level, url)
            results.append({"device": name, **result})
        except ToolError as error:
            results.append({"device": name, "success": False, "error": safe_message(error, keys)})
    return {"success": all(result["success"] for result in results), "results": results}


async def _send_one(key, keys, body, title, group, sound, level, url):
    payload = {"device_key": key, "title": title, "body": body, "group": group}
    for name, value in (("sound", sound), ("level", level), ("url", url)):
        if value is not None:
            payload[name] = value
    if any(secret in str(v) for secret in keys for k, v in payload.items() if k != "device_key"):
        raise ToolError("Notification content must not contain the Bark Device Key.")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0), follow_redirects=False, trust_env=False) as client:
            response = await client.post("https://api.day.app/push", content=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Content-Type": "application/json; charset=utf-8"})
    except httpx.TimeoutException:
        raise ToolError("Bark request timed out. Delivery is unknown; do not retry automatically.") from None
    except httpx.RequestError:
        raise ToolError("Network error contacting api.day.app. Check network/DNS/TLS. Delivery is unknown; do not retry automatically.") from None
    try:
        result = response.json()
    except ValueError:
        raise ToolError(f"Bark returned HTTP {response.status_code} with invalid JSON.") from None
    if not isinstance(result, dict):
        raise ToolError(f"Bark returned HTTP {response.status_code} with unexpected JSON.")
    message = safe_message(result.get("message", "No error message supplied"), keys)
    if not 200 <= response.status_code < 300 or result.get("code") != 200:
        raise ToolError(f"Bark API failed: HTTP {response.status_code}, Bark code {safe_message(result.get('code'), keys)}: {message}")
    return {"success": True, "http_status": response.status_code, "bark_code": 200, "message": message}

if __name__ == "__main__":
    mcp.run(transport="stdio")
