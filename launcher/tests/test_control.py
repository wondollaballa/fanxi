"""The launcher's control-port client and process table."""
from __future__ import annotations

import json
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401

from fanxi_launcher.control import ControlClient, ControlError, Instance, InstanceManager


class FakeProcess:
    _next = 41000

    def __init__(self):
        FakeProcess._next += 1
        self.pid = FakeProcess._next
        self.returncode = None

    def poll(self):
        return self.returncode


class FakeGame:
    def __init__(self):
        self.launched = []

    def launch(self, game_dir, client, token, extra=None, extra_env=None, log_name="game.log"):
        self.launched.append({
            "game_dir": game_dir, "client": client, "token": token,
            "extra_env": extra_env, "log_name": log_name,
        })
        return FakeProcess()

    def log_path(self, name):
        return Path(tempfile.gettempdir()) / name


class OneShotServer:
    def __init__(self, response):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.sock.listen(1)
        self.response = response
        self.requests = []
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        conn, _ = self.sock.accept()
        with conn:
            buf = b""
            while b"\n" not in buf:
                chunk = conn.recv(4096)
                if not chunk:
                    return
                buf += chunk
            line = buf.split(b"\n", 1)[0]
            request = json.loads(line)
            self.requests.append(request)
            conn.sendall((json.dumps(self.response(request)) + "\n").encode())

    def close(self):
        self.sock.close()


class ControlClientTest(unittest.TestCase):
    def test_call_returns_result(self):
        def respond(request):
            return {"id": request["id"], "ok": True, "result": {"echo": request["cmd"]}}
        server = OneShotServer(respond)
        self.addCleanup(server.close)
        client = ControlClient(server.port, timeout=5)
        self.addCleanup(client.close)
        self.assertEqual(client.call("state"), {"echo": "state"})
        self.assertEqual(server.requests[0]["cmd"], "state")

    def test_error_raises(self):
        server = OneShotServer(lambda request: {"id": request["id"], "ok": False,
                                                "error": "still signing in"})
        self.addCleanup(server.close)
        client = ControlClient(server.port, timeout=5)
        self.addCleanup(client.close)
        with self.assertRaises(ControlError) as ctx:
            client.call("metrics")
        self.assertIn("signing in", str(ctx.exception))


class InstanceManagerTest(unittest.TestCase):
    def setUp(self):
        self.game = FakeGame()
        self.manager = InstanceManager(self.game, base_port=55200)

    def test_launch_sets_control_port_and_one_per_account(self):
        account = {"username": "onedough"}
        character = {"id": 1, "name": "Onedough"}
        instance = self.manager.launch(account, character, {"server": "127.0.0.1"}, "token",
                                       "/games/ffxi")
        self.assertEqual(instance.port, 55200)
        self.assertEqual(self.game.launched[0]["extra_env"], {"FFXI_CONTROL": "55200"})
        self.assertEqual(self.game.launched[0]["log_name"], "game-onedough.log")
        self.assertEqual(self.manager.running_for("ONEDOUGH"), instance)
        with self.assertRaises(ControlError):
            self.manager.launch(account, character, {"server": "127.0.0.1"}, "token", "/games/ffxi")

    def test_allocate_port_skips_used(self):
        used = self.manager.allocate_port()
        instance = Instance(account="a", character={"name": "A"}, port=used,
                            process=FakeProcess(), log_path=Path("/tmp/a.log"))
        self.manager.instances.append(instance)
        self.assertNotEqual(self.manager.allocate_port(), used)

    def test_active_drops_exited_processes(self):
        instance = Instance(account="a", character={"name": "A"}, port=55200,
                            process=FakeProcess(), log_path=Path("/tmp/a.log"))
        self.manager.instances.append(instance)
        self.assertEqual(len(self.manager.active()), 1)
        instance.process.returncode = 1
        self.assertEqual(self.manager.active(), [])


if __name__ == "__main__":
    unittest.main()
