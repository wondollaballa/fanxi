"""Command line: run the server, prepare the database, create an admin."""
from __future__ import annotations

import argparse
import getpass
import logging
import sys
import time
from dataclasses import replace
from pathlib import Path

from . import __version__
from .config import Config
from .db import Database
from .game.gateway import Gateway
from .game.world import load_huffman
from .http_api import Api, serve
from .security import hash_password, now_iso, validate_password, validate_username, ValidationError
from .service import FanxiService


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def _service(config: Config) -> tuple[Database, FanxiService]:
    config.ensure_dirs()
    db = Database(config.db_path, config.root)
    db.initialize()
    return db, FanxiService(config, db)


def cmd_init(args) -> int:
    config = Config.from_env()
    db, _ = _service(config)
    tables = [r[0] for r in db.all("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
    print("Fanxi database: %s" % config.db_path)
    print("tables: %s" % ", ".join(tables))
    return 0


def cmd_doctor(args) -> int:
    config = Config.from_env()
    print("Fanxi %s" % __version__)
    print("repository:   %s" % config.root)
    print("database:     %s" % config.db_path)
    print("HTTP:         http://%s:%d" % (config.bind, config.http_port))
    print("public host:  %s" % config.public_host)
    print("game ports:   auth %(auth_port)d, data %(data_port)d, lobby %(view_port)d, zone %(zone_port)d/udp"
          % config.ports)
    game = config.find_game_dir()
    print("game folder:  %s" % (game or "not found (set FANXI_GAME_DIR)"))
    huffman = config.find_huffman_dir()
    print("compress.dat: %s" % (huffman / "compress.dat" if huffman else "not found (zone gateway off)"))
    print("registration: %s" % ("open" if config.registration_open else "closed"))
    print("admin key:    %s" % ("set" if config.admin_key else "not set (admin role only)"))
    return 0


def cmd_cert(args) -> int:
    config = Config.from_env()
    from .game.gateway import ensure_certificate
    pair = ensure_certificate(config)
    if pair is None:
        print("could not make a certificate; is openssl installed?", file=sys.stderr)
        return 1
    print("certificate: %s\nkey:         %s" % pair)
    return 0


def cmd_create_admin(args) -> int:
    config = Config.from_env()
    db, service = _service(config)
    username = getattr(args, "username", None)
    if not username:
        username = input("Admin username: ").strip()
    password = getattr(args, "password", None)
    if not password:
        password = getpass.getpass("Admin password: ")
        confirm = getpass.getpass("Again: ")
        if password != confirm:
            print("passwords do not match", file=sys.stderr)
            return 1
    try:
        username = validate_username(username)
        password = validate_password(password)
    except ValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    existing = db.one("SELECT id FROM accounts WHERE username = ?", (username,))
    if existing:
        db.execute("UPDATE accounts SET password_hash = ?, role = 'admin', status = 'active', updated_at = ? "
                   "WHERE id = ?", (hash_password(password), now_iso(), existing["id"]))
        print("updated admin %s (id %d)" % (username, existing["id"]))
        return 0
    account_id = db.execute(
        "INSERT INTO accounts (username, email, password_hash, status, role, created_at, updated_at) "
        "VALUES (?, ?, ?, 'active', 'admin', ?, ?)",
        (username, args.email, hash_password(password), now_iso(), now_iso()),
    )
    db.execute("INSERT INTO audit_log (account_id, action, detail, created_at) VALUES (?, 'admin.create', ?, ?)",
               (account_id, username, now_iso()))
    print("created admin %s (id %d)" % (username, account_id))
    return 0


def cmd_run(args) -> int:
    config = Config.from_env()
    if args.db:
        config = replace(config, db_path=Path(args.db).resolve())
    if args.bind:
        config = replace(config, bind=args.bind)
    if args.http_port:
        config = replace(config, http_port=args.http_port)
    if args.public_host:
        config = replace(config, public_host=args.public_host)
    if args.game_dir:
        config = replace(config, game_dir=Path(args.game_dir).resolve())
    if args.huffman:
        config = replace(config, huffman_dir=Path(args.huffman).resolve())
    if args.admin_key is not None:
        config = replace(config, admin_key=args.admin_key)
    _setup_logging(config.log_level)
    db, service = _service(config)
    api = Api(config, service)
    server, _thread = serve(config, service, api)

    gateway = None
    huffman_dir = config.find_huffman_dir()
    if not args.no_game:
        huffman = load_huffman(huffman_dir)
        if huffman is None:
            logging.getLogger("fanxi").error(
                "zone gateway off: no compress.dat (set FANXI_HUFFMAN or FANXI_GAME_DIR); HTTP still runs"
            )
        else:
            try:
                gateway = Gateway(config, service, huffman)
                gateway.start()
            except (OSError, RuntimeError) as exc:
                logging.getLogger("fanxi").error("zone gateway failed to start: %s", exc)
                gateway = None

    status = service.status()
    print("")
    print("  Fanxi %s — %s" % (__version__, status["name"]))
    print("  launcher API   http://%s:%d/api/v1" % (config.bind, server.server_address[1]))
    print("  database       %s" % config.db_path)
    if gateway:
        print("  game gateway   %s:%d (auth), %d (lobby), %d/udp (zone)" % (
            config.public_host, config.ports["auth_port"], config.ports["view_port"], config.ports["zone_port"]))
    else:
        print("  game gateway   off")
    print("  admin key      %s" % ("set" if config.admin_key else "not set (use an admin account)"))
    print("  press Ctrl-C to stop")
    print("")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        if gateway:
            gateway.stop()
        server.shutdown()
        server.server_close()
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="fanxi-server", description="Fanxi's launcher API and game gateway.")
    parser.add_argument("--version", action="version", version="Fanxi server " + __version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create the database and starter data")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("run", help="run the HTTP API and the game gateway")
    p.add_argument("--no-game", action="store_true", help="HTTP API only, no game sockets")
    p.add_argument("--bind", help="address for HTTP and game sockets (default 127.0.0.1)")
    p.add_argument("--http-port", type=int, help="launcher API port (default 8080)")
    p.add_argument("--public-host", help="the address the game client reaches this server at")
    p.add_argument("--db", help="database file")
    p.add_argument("--game-dir", help="the FINAL FANTASY XI folder (for compress.dat)")
    p.add_argument("--huffman", help="folder holding compress.dat")
    p.add_argument("--admin-key", help="key for admin API calls (empty to disable)")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("create-admin", help="create or update an administrator account")
    p.add_argument("username", nargs="?")
    p.add_argument("password", nargs="?")
    p.add_argument("--email")
    p.set_defaults(func=cmd_create_admin)

    p = sub.add_parser("cert", help="make the auth port's self-signed certificate")
    p.set_defaults(func=cmd_cert)

    p = sub.add_parser("doctor", help="show configuration and paths")
    p.set_defaults(func=cmd_doctor)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
