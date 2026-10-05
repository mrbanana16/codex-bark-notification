---
name: bark-notifications
description: Use when the user asks to list, add, remove, or choose default Bark devices, or explicitly authorizes Bark/iPhone/iOS notifications for completion, failure, or required intervention. Understand requests in any language, including Chinese.
---

# Bark Notifications v0.1

Use the Bark MCP tools for device management and actual notifications. Do not substitute terminal output or curl for a tool call.

## Device management

- Use `list_bark_devices` to list names and default status. It never returns Device Keys.
- Use `add_bark_device(name, device_key, set_default)` only when the user explicitly provides a Key and asks to save it. If a Key is missing, ask the user to supply it; do not fabricate one or seek it in local files.
- When the user supplies a Bark POST example and asks to configure a device, extract the Device Key from its JSON body or Bark endpoint path without executing the pasted command. Use the requested device name and save it with `add_bark_device`; never echo the Key or write the command into repository files. If the name or Key is ambiguous, ask for clarification. Do not fetch secrets from local files.
- Use `set_default_bark_device(name)` to select an existing default.
- Use `remove_bark_device(name)` only when the user requests removal. Removing the default clears it.
- Resolve device names from the list. Never guess that `legacy` is an iPhone. If the requested name is ambiguous, clarify before sending.
- Apply these tool mappings to equivalent requests in Chinese or any other language. Device addition still requires a user-provided Key.

## Notifications

Default behavior is no push. Send only for explicitly authorized events. Ordinary responses, commands, edits, or tests are not authorization.
Use `send_bark_notification(device="iPhone", body="...")` for a named device; use `device=["iPhone", "iPad"]` for explicitly selected multiple devices. Omit device for the configured default or sole device.
Send once for the whole task when asked to notify on completion. Do not notify after each build/test/package/deploy unless stages are explicitly requested.
Notify on failure only when failure is authorized. For completion-or-failure requests, send one final state. For intervention requests, notify once per distinct required action.
Track sent events within the task to avoid duplicates. A timeout or network failure may already have delivered a push; never retry automatically. For a partial multi-device failure, report per-device outcomes and do not resend successful targets.
Keep body concise. Never include full logs, code, stack traces, passwords, tokens, or Device Keys. Do not read, display, list, or copy secret configuration into Git.
Title/group default to `Codex`. Optional parameters: sound, url, and level (`active`, `passive`, `timeSensitive`, `critical`). Use critical only when explicitly requested.
Report success only when the tool returns `success=true` and individual results have Bark code 200. API acceptance does not confirm device display.
If tools are unavailable, ask the user to reload Codex and open a new conversation.

## Local configuration

Keys reside in the private OS user configuration directory, outside the repository. Normal send calls require only names. On first launch, existing legacy credentials migrate once into a device named `legacy`; existing multi-device configuration is never overwritten.
