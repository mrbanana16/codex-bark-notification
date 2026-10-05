"""Private device storage with atomic writes and serialized updates."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import tempfile
import warnings
from mcp.server.fastmcp.exceptions import ToolError


def config_path():
    override = os.environ.get('BARK_CONFIG_DIR')
    if override:
        return Path(override).expanduser() / 'devices.json'
    if os.name == 'nt':
        base = Path(os.environ.get('APPDATA', str(Path.home() / 'AppData/Roaming')))
    else:
        base = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
    return base / 'codex-bark-notification/devices.json'


def protect(path, mode):
    if os.name != 'nt':
        try:
            path.chmod(mode)
        except OSError:
            warnings.warn('Could not restrict Bark configuration permissions; check local file access.', stacklevel=2)


def validate_name(name):
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _.-]{0,63}', name):
        raise ToolError('Device name must be 1-64 characters: letters, digits, spaces, underscore, dot, or hyphen; start with a letter or digit.')
    return name


class DeviceStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else config_path()

    @contextmanager
    def locked(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            protect(self.path.parent, 0o700)
            fd = os.open(self.path.with_suffix('.lock'), os.O_CREAT | os.O_RDWR, 0o600)
            with os.fdopen(fd, 'r+b') as lock:
                if os.name == 'nt':
                    import msvcrt
                    lock.write(b'0'); lock.flush(); lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    if os.name == 'nt':
                        lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        except OSError:
            raise ToolError('Could not access private Bark configuration. Check local directory permissions.') from None

    def _read(self):
        if not self.path.exists():
            return {'version': 1, 'default_device': None, 'devices': {}}
        protect(self.path, 0o600)
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('devices'), dict):
                raise ValueError
            for name, device in data['devices'].items():
                validate_name(name)
                if not isinstance(device, dict) or not isinstance(device.get('device_key'), str) or not device['device_key'].strip():
                    raise ValueError
            keys = [device['device_key'] for device in data['devices'].values()]
            if any(key in name for key in keys for name in data['devices']):
                raise ValueError
            default = data.get('default_device')
            if default is not None and (not isinstance(default, str) or default not in data['devices']):
                raise ValueError
            return data
        except (ValueError, TypeError, ToolError, UnicodeError):
            raise ToolError('Invalid Bark devices configuration. Check version, devices, and default_device; existing data was not overwritten.') from None

    def _write(self, data):
        fd, temporary = tempfile.mkstemp(prefix='.devices-', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            protect(self.path, 0o600)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def list(self):
        with self.locked():
            data = self._read()
            return [{'name': name, 'default': name == data['default_device']} for name in data['devices']]

    def add(self, name, key, set_default=False):
        validate_name(name)
        if not isinstance(key, str) or not key.strip():
            raise ToolError('Device Key must not be empty.')
        if key.strip() in name:
            raise ToolError('Device name must not contain its Device Key.')
        with self.locked():
            data = self._read()
            if name in data['devices']:
                raise ToolError('A device with this name already exists; remove it explicitly before replacing it.')
            if any(d['device_key'] in name or key.strip() in n for n, d in data['devices'].items()):
                raise ToolError('Device names must not contain Device Keys.')
            data['devices'][name] = {'device_key': key.strip()}
            if set_default:
                data['default_device'] = name
            self._write(data)
        return {'success': True, 'name': name, 'message': 'Bark device added successfully.'}

    def remove(self, name):
        with self.locked():
            data = self._read()
            if name not in data['devices']:
                raise ToolError('Device does not exist. Use list_bark_devices to see configured names.')
            del data['devices'][name]
            cleared = data['default_device'] == name
            if cleared:
                data['default_device'] = None
            self._write(data)
        return {'success': True, 'default_cleared': cleared, 'message': 'Bark device removed successfully.'}

    def set_default(self, name):
        with self.locked():
            data = self._read()
            if name not in data['devices']:
                raise ToolError('Device does not exist. Use list_bark_devices to see configured names.')
            data['default_device'] = name
            self._write(data)
        return {'success': True, 'message': 'Default Bark device updated successfully.'}

    def resolve(self, requested=None):
        with self.locked():
            data = self._read()
        if requested is None:
            name = data['default_device']
            if name is None and len(data['devices']) == 1:
                name = next(iter(data['devices']))
            if name is None:
                raise ToolError('No default Bark device is configured. Add a device, specify device, or set a default device.')
            names = [name]
        else:
            names = [requested] if isinstance(requested, str) else requested
            if not names or not all(isinstance(n, str) and n in data['devices'] for n in names):
                raise ToolError('Unknown or empty device selection. Use list_bark_devices to see configured names.')
        names = list(dict.fromkeys(names))
        return [(name, data['devices'][name]['device_key']) for name in names], [d['device_key'] for d in data['devices'].values()]

    def migrate_legacy(self):
        with self.locked():
            if self.path.exists():
                return False
            key = os.environ.get('BARK_DEVICE_KEY', '').strip()
            legacy = Path.home() / '.codex/bark-notifications/private/device-key'
            if not key and legacy.is_file():
                key = legacy.read_text(encoding='utf-8').strip()
            if not key:
                return False
            self._write({'version': 1, 'default_device': 'legacy', 'devices': {'legacy': {'device_key': key}}})
            return True
