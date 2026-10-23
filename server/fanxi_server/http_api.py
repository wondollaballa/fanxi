"""The launcher-facing HTTP API.

A small router on top of http.server: JSON in, JSON out, Bearer tokens for players and either a
player with the admin role or FANXI_ADMIN_KEY for admin calls. The handlers are plain functions of
(api, request), so tests can call Api.handle() without opening a socket.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import traceback
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from . import __version__
from .config import Config
from .security import ValidationError, safe_equal
from .service import ApiError, FanxiService

log = logging.getLogger("fanxi.http")
MAX_BODY = 64 * 1024


@dataclass
class Request:
    method: str
    path: str
    query: dict[str, list[str]] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    remote: str = ""
    account: dict | None = None
    auth_token: str | None = None
    params: dict[str, str] = field(default_factory=dict)

    def json(self) -> dict:
        if not self.body:
            return {}
        try:
            value = json.loads(self.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ApiError(400, "bad_json", "the request body is not valid JSON")
        if not isinstance(value, dict):
            raise ApiError(400, "bad_json", "the request body must be a JSON object")
        return value

    def arg(self, name: str, default: str | None = None) -> str | None:
        values = self.query.get(name)
        return values[0] if values else default


@dataclass
class Response:
    status: int
    payload: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)

    def json(self) -> dict | list | None:
        return json.loads(self.payload.decode()) if self.payload else None


def json_response(status: int, value) -> Response:
    body = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return Response(status, body, {"Content-Type": "application/json; charset=utf-8"})


class Api:
    def __init__(self, config: Config, service: FanxiService):
        self.config = config
        self.service = service
        self.routes: list[tuple[str, re.Pattern, object]] = []
        self.started_at = service.started_at

        def route(method: str, pattern: str):
            def register(fn):
                self.routes.append((method, re.compile("^" + pattern + "$"), fn))
                return fn
            return register

        # public
        route("GET", r"/api/v1/health")(self.health)
        route("GET", r"/api/v1/status")(self.status)
        route("GET", r"/api/v1/news")(self.news)
        route("GET", r"/api/v1/releases")(self.releases)
        route("POST", r"/api/v1/auth/register")(self.register)
        route("POST", r"/api/v1/auth/login")(self.login)
        # authenticated
        route("POST", r"/api/v1/auth/logout")(self.logout)
        route("GET", r"/api/v1/me")(self.me)
        route("GET", r"/api/v1/characters")(self.characters)
        route("POST", r"/api/v1/characters")(self.create_character)
        route("PATCH", r"/api/v1/characters/(?P<character_id>\d+)")(self.patch_character)
        route("PATCH", r"/api/v1/characters/(?P<character_id>\d+)/design")(self.patch_character_design)
        route("POST", r"/api/v1/launch")(self.launch)
        # server-owned sub-accounts; the main account's token is the only key
        route("GET", r"/api/v1/accounts/sub")(self.sub_accounts)
        route("POST", r"/api/v1/accounts/sub")(self.create_sub_account)
        route("PATCH", r"/api/v1/accounts/sub/(?P<sub_id>\d+)")(self.update_sub_account)
        route("POST", r"/api/v1/accounts/sub/(?P<sub_id>\d+)/launch")(self.launch_sub)
        route("POST", r"/api/v1/accounts/sub/(?P<sub_id>\d+)/characters")(self.create_sub_character)
        route("DELETE", r"/api/v1/accounts/sub/(?P<sub_id>\d+)")(self.delete_sub_account)
        # admin
        route("GET", r"/api/v1/admin/stats")(self.admin_stats)
        route("POST", r"/api/v1/admin/news")(self.admin_news)
        route("POST", r"/api/v1/admin/releases")(self.admin_release)
        route("POST", r"/api/v1/admin/accounts/(?P<account_id>\d+)/status")(self.admin_account_status)

    # --- dispatch ------------------------------------------------------------------------------
    def handle(self, request: Request) -> Response:
        try:
            request.path = request.path.rstrip("/") or "/"
            for method, pattern, fn in self.routes:
                if method != request.method:
                    continue
                match = pattern.match(request.path)
                if not match:
                    continue
                request.params = match.groupdict()
                if request.path.startswith("/api/v1/admin/"):
                    self._require_admin(request)
                elif request.path not in ("/api/v1/health", "/api/v1/status", "/api/v1/news",
                                          "/api/v1/releases", "/api/v1/auth/register", "/api/v1/auth/login"):
                    self._require_player(request)
                response = fn(request)
                return self._with_cors(response)
            return self._with_cors(json_response(404, {"error": {"code": "not_found", "message": "no such endpoint"}}))
        except ApiError as exc:
            if exc.status >= 500:
                log.warning("%s %s: %s", request.method, request.path, exc.message)
            return self._with_cors(json_response(exc.status, {"error": {"code": exc.code, "message": exc.message}}))
        except ValidationError as exc:
            return self._with_cors(json_response(422, {"error": {"code": "validation_error", "message": str(exc)}}))
        except Exception:
            log.error("%s %s failed:\n%s", request.method, request.path, traceback.format_exc())
            return self._with_cors(json_response(500, {"error": {"code": "internal_error",
                                                               "message": "the server hit an error"}}))

    def _require_player(self, request: Request) -> None:
        token = self._bearer(request)
        if not token:
            raise ApiError(401, "unauthorized", "sign in first")
        request.auth_token = token
        request.account = self.service.authenticate(token)

    def _require_admin(self, request: Request) -> None:
        key = request.headers.get("x-admin-key", "")
        if self.config.admin_key and key and safe_equal(key, self.config.admin_key):
            request.account = None
            return
        token = self._bearer(request)
        if token:
            account = self.service.authenticate(token)
            if account["role"] == "admin":
                request.auth_token = token
                request.account = account
                return
        raise ApiError(403, "forbidden", "the admin key or an admin account is required")

    @staticmethod
    def _bearer(request: Request) -> str | None:
        value = request.headers.get("authorization", "")
        if value.lower().startswith("bearer "):
            return value[7:].strip()
        return None

    def _with_cors(self, response: Response) -> Response:
        response.headers.setdefault("Access-Control-Allow-Origin", self.config.cors_origin)
        response.headers.setdefault("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Admin-Key")
        response.headers.setdefault("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    # --- public --------------------------------------------------------------------------------
    def health(self, request: Request) -> Response:
        return json_response(200, {"status": "ok", "name": self.service.server_name(), "version": __version__})

    def status(self, request: Request) -> Response:
        return json_response(200, self.service.status())

    def news(self, request: Request) -> Response:
        try:
            limit = int(request.arg("limit", "10") or 10)
        except ValueError:
            limit = 10
        return json_response(200, {"news": self.service.news(limit)})

    def releases(self, request: Request) -> Response:
        return json_response(200, {
            "releases": self.service.releases(request.arg("platform"), request.arg("channel", "stable") or "stable")
        })

    def register(self, request: Request) -> Response:
        body = request.json()
        result = self.service.register(
            str(body.get("username") or ""), str(body.get("password") or ""),
            body.get("email"), request.remote,
        )
        return json_response(201, {"token": result.token, "expires_at": result.expires_at,
                                   "account": result.account})

    def login(self, request: Request) -> Response:
        body = request.json()
        result = self.service.login(
            str(body.get("username") or ""), str(body.get("password") or ""), request.remote
        )
        return json_response(200, {"token": result.token, "expires_at": result.expires_at,
                                   "account": result.account,
                                   "characters": self.service.list_characters(result.account["id"])})

    # --- authenticated -------------------------------------------------------------------------
    def logout(self, request: Request) -> Response:
        assert request.auth_token
        self.service.logout(request.auth_token, request.remote)
        return Response(204)

    def me(self, request: Request) -> Response:
        assert request.account
        return json_response(200, {
            "account": self.service.public_account(request.account),
            "characters": self.service.list_characters(request.account["id"]),
        })

    def characters(self, request: Request) -> Response:
        assert request.account
        return json_response(200, {"characters": self.service.list_characters(request.account["id"])})

    def create_character(self, request: Request) -> Response:
        assert request.account
        return json_response(201, {"character": self.service.create_character(request.account["id"], request.json())})

    def patch_character(self, request: Request) -> Response:
        assert request.account
        body = request.json()
        if "name" not in body:
            raise ApiError(422, "validation_error", "only a name can be changed here")
        character = self.service.rename_character(
            request.account["id"], int(request.params["character_id"]), str(body["name"])
        )
        return json_response(200, {"character": character})

    def patch_character_design(self, request: Request) -> Response:
        assert request.account
        character = self.service.save_design_for_account(
            request.account["id"], int(request.params["character_id"]), request.json()
        )
        return json_response(200, {"character": character})

    def launch(self, request: Request) -> Response:
        assert request.account
        body = request.json()
        character_id = body.get("character_id")
        if character_id is not None:
            try:
                character_id = int(character_id)
            except (TypeError, ValueError):
                raise ApiError(422, "validation_error", "character_id must be a number")
        return json_response(200, self.service.launch(request.account, character_id, request.remote))

    # --- sub-accounts --------------------------------------------------------------------------
    def sub_accounts(self, request: Request) -> Response:
        assert request.account
        return json_response(200, {
            "subs": self.service.sub_accounts(request.account["id"]),
            "limit": self.service.max_subs(),
        })

    def create_sub_account(self, request: Request) -> Response:
        assert request.account
        sub = self.service.create_sub_account(request.account["id"], request.json(), request.remote)
        return json_response(201, {"sub": sub, "limit": self.service.max_subs()})

    def launch_sub(self, request: Request) -> Response:
        assert request.account
        body = request.json()
        character_id = body.get("character_id")
        if character_id is not None:
            try:
                character_id = int(character_id)
            except (TypeError, ValueError):
                raise ApiError(422, "validation_error", "character_id must be a number")
        sub_id = int(request.params["sub_id"])
        return json_response(200, self.service.launch_sub(
            request.account["id"], sub_id, character_id, request.remote))

    def update_sub_account(self, request: Request) -> Response:
        assert request.account
        body = request.json()
        if str(body.get("status") or "") != "active":
            raise ApiError(422, "validation_error", "only status active can be set here")
        sub = self.service.activate_sub_account(request.account["id"], int(request.params["sub_id"]))
        return json_response(200, {"sub": sub})

    def create_sub_character(self, request: Request) -> Response:
        assert request.account
        body = request.json()
        source = body.get("character") if isinstance(body.get("character"), dict) else body
        character = self.service.create_sub_character(
            request.account["id"], int(request.params["sub_id"]), source)
        return json_response(201, {"character": character})

    def delete_sub_account(self, request: Request) -> Response:
        assert request.account
        purge = (request.arg("purge") or "").lower() in ("1", "true", "yes")
        result = self.service.suspend_sub_account(
            request.account["id"], int(request.params["sub_id"]), purge=purge)
        return json_response(200, {"sub": result})

    # --- admin ---------------------------------------------------------------------------------
    def admin_stats(self, request: Request) -> Response:
        return json_response(200, {
            "status": self.service.status(),
            "audit": [dict(r) for r in self.service.db.all(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT 50")],
        })

    def admin_news(self, request: Request) -> Response:
        body = request.json()
        post = self.service.create_news(str(body.get("slug") or ""), str(body.get("title") or ""),
                                        str(body.get("body") or ""))
        return json_response(201, {"news": post})

    def admin_release(self, request: Request) -> Response:
        return json_response(201, {"release": self.service.create_release(request.json())})

    def admin_account_status(self, request: Request) -> Response:
        body = request.json()
        account = self.service.set_account_status(int(request.params["account_id"]), str(body.get("status") or ""))
        return json_response(200, {"account": account})


# --- the socket ----------------------------------------------------------------------------------

class FanxiHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class Handler(BaseHTTPRequestHandler):
    server_version = "Fanxi/" + __version__
    sys_version = ""

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PATCH(self):
        self._dispatch("PATCH")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def do_OPTIONS(self):
        self.send_response(204)
        for key, value in self.server.api._with_cors(Response(204)).headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _dispatch(self, method: str):
        parsed = urlsplit(self.path)
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length > MAX_BODY:
            self._send(json_response(413, {"error": {"code": "too_large", "message": "request body is too large"}}))
            return
        body = self.rfile.read(length) if length else b""
        headers = {k.lower(): v for k, v in self.headers.items()}
        request = Request(
            method=method,
            path=parsed.path.rstrip("/") or "/",
            query=parse_qs(parsed.query),
            headers=headers,
            body=body,
            remote=self.client_address[0],
        )
        response = self.server.api.handle(request)
        self._send(response)

    def _send(self, response: Response):
        self.send_response(response.status)
        for key, value in response.headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(response.payload)))
        self.end_headers()
        if response.payload:
            try:
                self.wfile.write(response.payload)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def log_message(self, fmt, *args):
        log.debug("%s %s", self.address_string(), fmt % args)


def serve(config: Config, service: FanxiService, api: Api | None = None) -> tuple[FanxiHTTPServer, threading.Thread]:
    api = api or Api(config, service)
    server = FanxiHTTPServer((config.bind, config.http_port), Handler)
    server.api = api
    thread = threading.Thread(target=server.serve_forever, name="fanxi-http", daemon=True)
    thread.start()
    log.info("HTTP API on http://%s:%d", config.bind, config.http_port)
    return server, thread
