"""Exercise MCP device management in isolation; --live sends one authorized test."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import tempfile
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def check(live=False):
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as temporary:
        env = dict(os.environ)
        if not live:
            env['BARK_CONFIG_DIR'] = temporary
            env['BARK_DEVICE_KEY'] = 'SYNTHETIC-MCP-KEY'
        params = StdioServerParameters(command='python3', args=[str(root / 'launcher.py')], env=env)
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                names = [t.name for t in (await session.list_tools()).tools]
                expected = ['list_bark_devices', 'add_bark_device', 'remove_bark_device', 'set_default_bark_device', 'send_bark_notification']
                assert set(names) == set(expected)
                print('MCP startup and five-tool discovery: PASS')
                if live:
                    devices = await session.call_tool('list_bark_devices', {})
                    assert not devices.isError
                    print('Private devices (names only):', devices.model_dump_json())
                    result = await session.call_tool('send_bark_notification', {'title': 'Codex', 'body': 'Bark Notifications v0.1 multi-device upgrade test passed', 'group': 'Codex'})
                    assert not result.isError
                    value = json.loads(result.content[0].text)
                    assert value['success'] and all(r['bark_code'] == 200 for r in value['results'])
                    print('Live notification:', json.dumps(value, ensure_ascii=False))
                else:
                    for tool, arguments in [('add_bark_device', {'name': 'test-device', 'device_key': 'SYNTHETIC-SECOND-KEY'}), ('set_default_bark_device', {'name': 'test-device'}), ('list_bark_devices', {}), ('remove_bark_device', {'name': 'test-device'})]:
                        result = await session.call_tool(tool, arguments)
                        assert not result.isError
                        assert 'SYNTHETIC' not in result.model_dump_json()
                        print(tool + ': PASS')
                    result = await session.call_tool('send_bark_notification', {'body': 'Test', 'device': 'unknown'})
                    assert result.isError
                    print('Invalid send rejected before network: PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', help='Send one real push using the default device.')
    asyncio.run(check(parser.parse_args().live))
