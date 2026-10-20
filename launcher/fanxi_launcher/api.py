"""The launcher's HTTP client for the Fanxi server."""
from __future__ import annotations

import json
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request

from . import __version__


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

    @property
    def unauthorized(self) -> bool:
        return self.status == 401


class NetworkError(Exception):
    pass


class FanxiApi:
    def __init__(self, base_url: str, timeout: float = 15.0, insecure: bool = False):
        base = (base_url or "").strip().rstrip("/")
        if base.endswith("/api/v1"):
            base = base[:-7]
        if not base.startswith(("http://", "https://")):
            base = "http://" + base
        self.base = base
        self.timeout = timeout
        self.insecure = insecure
        self.context = ssl._create_unverified_context() if insecure else None

    @property
    def api_root(self) -> str:
        return self.base + "/api/v1"

    def _request(self, method: str, path: str, body=None, token: str | None = None,
                 query: dict | None = None):
        url = self.api_root + path
        if query:
            url += "?" + urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})
        data = None
        headers = {
            "Accept": "application/json",
            "User-Agent": "FanxiLauncher/" + __version__,
        }
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = "Bearer " + token
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout, context=self.context) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                payload = json.loads(raw.decode("utf-8"))
                error = payload.get("error", {})
                message = error.get("message") or exc.reason
                code = error.get("code") or "http_error"
            except (ValueError, UnicodeDecodeError):
                message, code = str(exc.reason), "http_error"
            raise ApiError(exc.code, code, message)
        except urllib.error.URLError as exc:
            reason = exc.reason
            if isinstance(reason, ConnectionRefusedError):
                raise NetworkError("cannot reach %s: is the Fanxi server running?" % self.base)
            if isinstance(reason, socket.timeout):
                raise NetworkError("the Fanxi server at %s took too long to answer" % self.base)
            if isinstance(reason, ssl.SSLError):
                raise NetworkError("TLS failed for %s: %s" % (self.base, reason))
            raise NetworkError("cannot reach %s: %s" % (self.base, reason))
        except TimeoutError:
            raise NetworkError("the Fanxi server at %s took too long to answer" % self.base)
        if not raw:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise NetworkError("the server sent something that is not JSON")

    # --- endpoints -----------------------------------------------------------------------------
    def health(self):
        return self._request("GET", "/health")

    def status(self):
        return self._request("GET", "/status")

    def news(self, limit: int = 10):
        return self._request("GET", "/news", query={"limit": limit})["news"]

    def releases(self, platform: str | None = None, channel: str = "stable"):
        return self._request("GET", "/releases", query={"platform": platform, "channel": channel})["releases"]

    def register(self, username: str, password: str, email: str | None = None):
        return self._request("POST", "/auth/register",
                             {"username": username, "password": password, "email": email})

    def login(self, username: str, password: str):
        return self._request("POST", "/auth/login", {"username": username, "password": password})

    def logout(self, token: str):
        return self._request("POST", "/auth/logout", token=token)

    def me(self, token: str):
        return self._request("GET", "/me", token=token)

    def characters(self, token: str):
        return self._request("GET", "/characters", token=token)["characters"]

    def create_character(self, token: str, data: dict):
        return self._request("POST", "/characters", data, token=token)["character"]

    def rename_character(self, token: str, character_id: int, name: str):
        return self._request("PATCH", "/characters/%d" % int(character_id), {"name": name},
                             token=token)["character"]

    def launch(self, token: str, character_id: int | None = None):
        return self._request("POST", "/launch", {"character_id": character_id}, token=token)
