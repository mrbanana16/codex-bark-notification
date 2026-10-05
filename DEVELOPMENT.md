# Development v0.1

Python 3.10+ is required. The tested host is macOS with Codex CLI 0.149.1.
Keep the working `.codex-plugin/plugin.json` and `.mcp.json` compatibility format; do not add duplicate portable manifests without host validation.

Install from the repository with `python3 install.py`. The root installer resolves dependencies and marketplace paths from the repository root. The installer migrates only the known v0.1 marketplace source; it refuses to replace unrelated repository sources. Reinstall changed code using the Codex plugin CLI so its cache is regenerated, rather than editing installed cache files.

The runtime lives in `~/.codex/bark-notifications/venv`; it is never part of Git. Configuration uses `XDG_CONFIG_HOME` (otherwise `~/.config`) on macOS/Linux or `APPDATA` on Windows. `BARK_CONFIG_DIR` overrides the configuration directory for isolated testing. Do not point it into a public repository for real credentials.

Device configuration is UTF-8 JSON version 1, written atomically under a file lock. POSIX file/directory permissions are 0600/0700. Permission-setting failures produce an English warning without printing credentials. Windows relies on user directory ACLs; Windows execution has not been tested on this Mac.

On first launch only, a legacy `BARK_DEVICE_KEY` or the prior private `device-key` file is migrated to the default device `legacy`. An existing devices.json is never overwritten. Once migrated, normal sending uses only devices.json, not the environment.

Run offline tests with the installed runtime:

```bash
~/.codex/bark-notifications/venv/bin/python -m unittest discover -s tests -v
~/.codex/bark-notifications/venv/bin/python tests/mcp_smoke.py
```

`tests/mcp_smoke.py --live` sends one real notification to the configured default. Run it only with explicit user authorization. All other tests use temporary configuration and synthetic credentials.

Each selected device receives a separate POST to the existing Bark V2 endpoint. Duplicate device names are deduplicated. Every target and notification field is validated before the first request. Mixed results return `success=false` with per-device outcomes; successful recipients must not be resent automatically. Network errors and timeouts mean delivery is unknown.

Device management is provided through MCP tools in Codex conversations. No hooks, background monitor, or cloud service is required. Notification authorization is enforced by the Skill and host; the server does not independently infer the user's intent.
