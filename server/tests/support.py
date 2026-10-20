"""Shared test helpers: temporary databases, a fake Huffman table and free ports."""
from __future__ import annotations

import socket
import struct
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

from fanxi_server.config import Config  # noqa: E402
from fanxi_server.db import Database  # noqa: E402
from fanxi_server.service import FanxiService  # noqa: E402


def make_config(tmp_path: Path, **overrides) -> Config:
    config = Config(
        root=ROOT,
        db_path=tmp_path / "fanxi.db",
        tls_cert=tmp_path / "tls" / "auth-cert.pem",
        tls_key=tmp_path / "tls" / "auth-key.pem",
        registration_open=True,
        admin_key="test-admin-key",
    )
    if overrides:
        config = replace(config, **overrides)
    config.ensure_dirs()
    return config


def make_service(tmp_path: Path, **overrides):
    config = make_config(tmp_path, **overrides)
    db = Database(config.db_path, config.root)
    db.initialize()
    return config, db, FanxiService(config, db)


def make_huffman_dir(tmp_path: Path) -> Path:
    """A table where every byte is its own 8-bit code: valid and reversible."""
    words = [0] * 512
    for b in range(256):
        words[(b + 128) & 255] = b
        words[256 + ((b + 128) & 255)] = 8
    folder = tmp_path / "game" / "res"
    folder.mkdir(parents=True)
    (folder / "compress.dat").write_bytes(struct.pack("<512I", *words))
    return folder


def free_tcp_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def free_udp_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def game_ports() -> dict:
    return {
        "auth_port": free_tcp_port(),
        "data_port": free_tcp_port(),
        "view_port": free_tcp_port(),
        "zone_port": free_udp_port(),
        "search_port": free_udp_port(),
    }
