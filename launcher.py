"""Launch the user-level runtime and migrate legacy credentials once."""
import os
from pathlib import Path
import runpy
import sys

root = Path(__file__).resolve().parent
runtime = Path.home() / '.codex/bark-notifications/venv'
python = runtime / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
if Path(sys.prefix).resolve() != runtime.resolve():
    if not python.is_file():
        raise SystemExit('Bark runtime is not installed. Run python3 install.py from the repository.')
    os.execv(str(python), [str(python), str(root / 'launcher.py')])
sys.path.insert(0, str(root))
from devices import DeviceStore
DeviceStore().migrate_legacy()
runpy.run_path(str(root / 'server.py'), run_name='__main__')
