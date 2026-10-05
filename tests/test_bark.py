"""Offline tests use isolated configuration and synthetic credentials only."""
import asyncio
import concurrent.futures
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import httpx
from mcp.server.fastmcp.exceptions import ToolError
import server
from devices import DeviceStore


class Client:
    def __init__(self, outcome, calls):
        self.outcome = outcome
        self.calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class BarkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'BARK_CONFIG_DIR': self.temp.name})
        self.env.start()
        self.store = DeviceStore()
        self.key = 'SYNTHETIC-KEY-ONE'

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_management_tools_and_default_removal(self):
        server.add_bark_device('iphone', self.key, True)
        server.add_bark_device('ipad', 'SYNTHETIC-KEY-TWO')
        self.assertEqual(server.list_bark_devices(), [{'name': 'iphone', 'default': True}, {'name': 'ipad', 'default': False}])
        self.assertNotIn(self.key, json.dumps(server.list_bark_devices()))
        server.set_default_bark_device('ipad')
        self.assertEqual(self.store.resolve()[0][0][0], 'ipad')
        self.assertTrue(server.remove_bark_device('ipad')['default_cleared'])
        self.assertEqual(self.store.resolve()[0][0][0], 'iphone')
        server.remove_bark_device('iphone')
        with self.assertRaises(ToolError):
            self.store.resolve()

    def test_validation_and_duplicate(self):
        for name, key in [('', self.key), ('iphone', ''), (self.key, self.key)]:
            with self.assertRaises(ToolError):
                server.add_bark_device(name, key)
        self.store.add('iphone', self.key)
        with self.assertRaises(ToolError):
            self.store.add('iphone', 'REPLACEMENT')
        self.assertEqual(self.store.resolve('iphone')[0][0][1], self.key)
        for action in [lambda: self.store.remove(self.key), lambda: self.store.set_default(self.key)]:
            with self.assertRaises(ToolError) as error:
                action()
            self.assertNotIn(self.key, str(error.exception))

    def test_ambiguous_and_selected_devices(self):
        self.store.add('iphone', self.key)
        self.store.add('ipad', 'SYNTHETIC-KEY-TWO')
        with self.assertRaises(ToolError):
            self.store.resolve()
        self.assertEqual(len(self.store.resolve(['iphone', 'iphone', 'ipad'])[0]), 2)
        with self.assertRaises(ToolError):
            self.store.resolve(['iphone', 'missing'])

    def test_corrupt_config_not_overwritten(self):
        self.store.path.write_text('{broken', encoding='utf-8')
        with self.assertRaises(ToolError):
            self.store.add('iphone', self.key)
        self.assertEqual(self.store.path.read_text(), '{broken')

    def test_config_names_cannot_leak_keys(self):
        self.store.path.write_text(json.dumps({'version': 1, 'default_device': None, 'devices': {self.key: {'device_key': self.key}}}))
        with self.assertRaises(ToolError) as error:
            self.store.list()
        self.assertNotIn(self.key, str(error.exception))

    def test_atomic_concurrent_writes(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda n: DeviceStore().add('device-' + str(n), 'SYNTHETIC-' + str(n)), range(12)))
        self.assertEqual(len(self.store.list()), 12)
        if os.name != 'nt':
            self.assertEqual(self.store.path.stat().st_mode & 0o777, 0o600)

    def test_permission_failure_warns(self):
        self.store.add('iphone', self.key)
        with patch.object(Path, 'chmod', side_effect=PermissionError), self.assertWarns(UserWarning):
            self.assertEqual(len(self.store.list()), 1)

    def test_legacy_migration_once(self):
        with patch.dict(os.environ, {'BARK_DEVICE_KEY': self.key}):
            self.assertTrue(self.store.migrate_legacy())
            self.store.add('ipad', 'SYNTHETIC-KEY-TWO', True)
            self.assertFalse(self.store.migrate_legacy())
        self.assertEqual(self.store.resolve()[0][0][0], 'ipad')

    def send(self, outcome, **kwargs):
        calls = []
        with patch.object(server.httpx, 'AsyncClient', return_value=Client(outcome, calls)):
            result = asyncio.run(server.send_bark_notification('Task complete', **kwargs))
        return result, calls

    def test_post_defaults_and_multiple_devices(self):
        self.store.add('iphone', self.key, True)
        self.store.add('ipad', 'SYNTHETIC-KEY-TWO')
        result, calls = self.send(httpx.Response(200, json={'code': 200, 'message': 'success'}), device=['iphone', 'iphone', 'ipad'])
        self.assertTrue(result['success'])
        self.assertEqual(len(calls), 2)
        url, kwargs = calls[0]
        self.assertEqual(url, 'https://api.day.app/push')
        self.assertEqual(kwargs['headers']['Content-Type'], 'application/json; charset=utf-8')
        payload = json.loads(kwargs['content'])
        self.assertEqual(payload['device_key'], self.key)
        self.assertEqual(payload['title'], 'Codex')
        self.assertEqual(payload['group'], 'Codex')
        self.assertNotIn(self.key, json.dumps(result))

    def test_errors_and_redaction(self):
        self.store.add('iphone', self.key, True)
        outcomes = [(httpx.ConnectError(self.key), 'Network error'), (httpx.ReadTimeout(self.key), 'timed out'), (httpx.Response(403, json={'code': self.key, 'message': self.key}), '[REDACTED]'), (httpx.Response(200, json={'code': 400, 'message': 'failure'}), 'failed'), (httpx.Response(200, text='invalid'), 'invalid JSON'), (httpx.Response(200, json=[]), 'unexpected JSON')]
        for outcome, text in outcomes:
            with self.subTest(text=text):
                result, calls = self.send(outcome)
                self.assertFalse(result['success'])
                self.assertIn(text, result['results'][0]['error'])
                self.assertNotIn(self.key, json.dumps(result))
                self.assertEqual(len(calls), 1)

    def test_secret_content_and_invalid_targets_never_sent(self):
        self.store.add('iphone', self.key, True)
        with patch.object(server.httpx, 'AsyncClient') as client:
            for kwargs in [{'body': self.key}, {'body': ''}, {'body': 'ok', 'device': ['iphone', 'missing']}]:
                with self.assertRaises(ToolError):
                    asyncio.run(server.send_bark_notification(**kwargs))
            client.assert_not_called()

    def test_partial_delivery(self):
        self.store.add('iphone', self.key)
        self.store.add('ipad', 'SYNTHETIC-KEY-TWO')
        with patch.object(server, '_send_one', side_effect=[{'success': True, 'bark_code': 200}, ToolError('Timed out')]):
            result = asyncio.run(server.send_bark_notification('Task complete', device=['iphone', 'ipad']))
        self.assertFalse(result['success'])
        self.assertTrue(result['results'][0]['success'])
        self.assertFalse(result['results'][1]['success'])


if __name__ == '__main__':
    unittest.main()
