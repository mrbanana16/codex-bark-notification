"""Install the private local runtime and register this repository marketplace."""
from pathlib import Path
import os
import json
import shutil
import subprocess
import sys
import venv


def main():
    root = Path(__file__).resolve().parent
    codex = shutil.which('codex')
    if not codex:
        raise SystemExit('Codex CLI is required and must be available on PATH.')
    runtime = Path.home() / '.codex/bark-notifications/venv'
    python = runtime / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        venv.EnvBuilder(with_pip=True).create(runtime)
    subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(root / 'requirements.txt')], check=True)
    # The existing marketplace name is retained to avoid duplicate plugins.
    inventory = json.loads(subprocess.check_output([codex, 'plugin', 'marketplace', 'list', '--json'], text=True))
    for entry in inventory['marketplaces']:
        if entry['name'] == 'bark-personal':
            source = entry.get('marketplaceSource', {}).get('source', entry.get('root', ''))
            if source and Path(source).resolve() != root:
                legacy = Path.home() / '.codex/bark-notifications/marketplace'
                if Path(source).resolve() != legacy.resolve():
                    raise SystemExit('bark-personal is registered from another repository. Review and remove that marketplace explicitly before installing this copy.')
                subprocess.run([codex, 'plugin', 'marketplace', 'remove', 'bark-personal'], check=True)
    subprocess.run([codex, 'plugin', 'marketplace', 'add', str(root)], check=True)
    subprocess.run([codex, 'plugin', 'add', 'bark-notifications@bark-personal'], check=True)
    print('Bark Notifications v0.1 installed. Reload Codex and open a new conversation.')


if __name__ == '__main__':
    main()
