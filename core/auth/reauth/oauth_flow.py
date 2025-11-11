"""YouTube OAuth consent and token exchange workflow for automation."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable, Dict, Optional
from urllib.parse import parse_qs, urlparse

import requests

from core.auth.reauth.models import AutomationCredential, ReauthResult, ReauthStatus
from core.utils.logger import get_logger

LOGGER = get_logger(__name__)


@dataclass
class OAuthConfig:
    """Configuration needed to drive the YouTube OAuth flow."""

    client_id: str
    client_secret: str
    redirect_port: int = 8080
    scopes: Optional[list[str]] = None
    prompt: str = "consent"
    access_type: str = "offline"
    timeout_seconds: int = 300


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Lightweight HTTP handler that captures the OAuth authorization code."""

    callback: Callable[[Dict[str, Optional[str]]], None]

    def __init__(self, callback: Callable[[Dict[str, Optional[str]]], None], *args, **kwargs):
        self.callback = callback
        super().__init__(*args, **kwargs)

    def log_message(self, format: str, *args) -> None:  # noqa: D401
        """Silence default HTTP request logging."""
        return

    def do_GET(self) -> None:  # noqa: D401
        """Handle the OAuth redirect."""
        try:
            if self.path == "/favicon.ico":
                self.send_response(404)
                self.end_headers()
                return

            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            payload = {
                "code": params.get("code", [None])[0],
                "error": params.get("error", [None])[0],
                "state": params.get("state", [None])[0],
            }

            if payload["error"]:
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    "<html><body><h1>Authorization Error</h1>"
                    "<p>Please return to the application.</p></body></html>".encode()
                )
            else:
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    "<html><body><h1>Authorization Complete</h1>"
                    "<p>You can close this window.</p></body></html>".encode()
                )

            self.callback(payload)
        except Exception as exc:  # pragma: no cover - defensive logging
            LOGGER.exception("Error handling OAuth callback: %s", exc)
            self.callback({"code": None, "error": str(exc), "state": None})


class OAuthFlow:
    """Encapsulates building the consent URL, running callback server, and exchanging tokens."""

    def __init__(self, config: OAuthConfig) -> None:
        self.config = config
        self._result: Optional[Dict[str, Optional[str]]] = None
        self._server: Optional[HTTPServer] = None

    def build_authorization_url(self, credential: AutomationCredential, state: str) -> str:
        """Construct the YouTube OAuth consent URL for the target channel."""
        scopes = self.config.scopes or [
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube",
            "https://www.googleapis.com/auth/youtube.force-ssl",
        ]

        params = {
            "client_id": self.config.client_id,
            "redirect_uri": f"http://localhost:{self.config.redirect_port}/callback",
            "scope": " ".join(scopes),
            "response_type": "code",
            "access_type": self.config.access_type,
            "prompt": self.config.prompt,
            "login_hint": credential.login_email,
            "state": state,
        }

        query = "&".join(f"{key}={requests.utils.quote(str(value))}" for key, value in params.items())
        url = f"https://accounts.google.com/o/oauth2/v2/auth?{query}"
        LOGGER.debug("Generated authorization URL for %s", credential.channel_name)
        return url

    def _start_callback_server(self) -> None:
        """Launch the HTTP server in a background thread."""
        handler = lambda *args: _OAuthCallbackHandler(self._store_result, *args)  # noqa: E731
        self._server = HTTPServer(("localhost", self.config.redirect_port), handler)
        thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        thread.start()
        LOGGER.debug("Started OAuth callback server on port %s", self.config.redirect_port)

    def _shutdown_callback_server(self) -> None:
        """Tear down the callback server if running."""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            LOGGER.debug("Shutdown OAuth callback server on port %s", self.config.redirect_port)
        self._server = None

    def _store_result(self, payload: Dict[str, Optional[str]]) -> None:
        """Store callback payload."""
        self._result = payload

    def wait_for_authorization(self) -> Dict[str, Optional[str]]:
        """Block until an authorization code or error is received or timeout occurs."""
        start = time.time()
        while self._result is None and (time.time() - start) < self.config.timeout_seconds:
            time.sleep(0.5)

        self._shutdown_callback_server()

        if self._result is None:
            LOGGER.error("OAuth flow timed out after %s seconds", self.config.timeout_seconds)
            return {"code": None, "error": "Timeout waiting for authorization", "state": None}

        return self._result

    def exchange_code_for_tokens(self, code: str) -> Dict[str, Optional[str]]:
        """Exchange authorization code for access and refresh tokens."""
        token_endpoint = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": f"http://localhost:{self.config.redirect_port}/callback",
        }

        response = requests.post(token_endpoint, data=data, timeout=30)
        if not response.ok:
            error_text = response.text
            LOGGER.error("Token exchange failed: %s", error_text)
            return {"error": error_text}

        payload = response.json()
        return {
            "access_token": payload.get("access_token"),
            "refresh_token": payload.get("refresh_token"),
            "expires_in": payload.get("expires_in"),
            "scope": payload.get("scope"),
        }

    def run(
        self,
        credential: AutomationCredential,
        state: str,
        open_browser: Callable[[str], None],
    ) -> ReauthResult:
        """Execute the full flow and return the result."""
        try:
            self._result = None
            self._start_callback_server()

            auth_url = self.build_authorization_url(credential, state)
            open_browser(auth_url)
            LOGGER.info("Opened browser for OAuth consent: channel=%s", credential.channel_name)

            outcome = self.wait_for_authorization()

            if outcome.get("error"):
                return ReauthResult(
                    channel_name=credential.channel_name,
                    status=ReauthStatus.FAILED,
                    error=outcome["error"],
                )

            code = outcome.get("code")
            if not code:
                return ReauthResult(
                    channel_name=credential.channel_name,
                    status=ReauthStatus.FAILED,
                    error="Authorization code not received",
                )

            tokens = self.exchange_code_for_tokens(code)
            if tokens.get("error"):
                return ReauthResult(
                    channel_name=credential.channel_name,
                    status=ReauthStatus.FAILED,
                    error=str(tokens["error"]),
                )

            return ReauthResult(
                channel_name=credential.channel_name,
                status=ReauthStatus.SUCCESS,
                access_token=tokens.get("access_token"),
                refresh_token=tokens.get("refresh_token"),
                expires_in=tokens.get("expires_in"),
                metadata={"scope": str(tokens.get("scope"))},
            )

        except Exception as exc:  # pragma: no cover - defensive logging
            LOGGER.exception("Unexpected error during OAuth flow: %s", exc)
            return ReauthResult(
                channel_name=credential.channel_name,
                status=ReauthStatus.FAILED,
                error=str(exc),
            )
        finally:
            self._shutdown_callback_server()



