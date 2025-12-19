"""YouTube OAuth consent and token exchange workflow for automation."""

from __future__ import annotations

import socket
import subprocess
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
            # Ignore non-callback paths
            if self.path == "/favicon.ico":
                self.send_response(404)
                self.end_headers()
                return
            
            # Ignore Chrome DevTools and other non-OAuth requests
            if not self.path.startswith("/callback"):
                LOGGER.debug("Ignoring non-callback request: %s", self.path)
                self.send_response(404)
                self.end_headers()
                return

            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            payload = {
                "code": params.get("code", [None])[0],
                "error": params.get("error", [None])[0],
                "error_description": params.get("error_description", [None])[0],
                "error_uri": params.get("error_uri", [None])[0],
                "state": params.get("state", [None])[0],
            }

            if payload["error"]:
                # Log detailed error information
                error_msg = f"OAuth authorization error: {payload['error']}"
                if payload.get("error_description"):
                    error_msg += f" - {payload['error_description']}"
                if payload.get("error_uri"):
                    error_msg += f" (URI: {payload['error_uri']})"
                LOGGER.error(
                    "OAuth callback received error. Path: %s, Error: %s, Description: %s, URI: %s",
                    self.path,
                    payload["error"],
                    payload.get("error_description"),
                    payload.get("error_uri")
                )
                
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    "<html><body><h1>Authorization Error</h1>"
                    "<p>Please return to the application.</p></body></html>".encode()
                )
                self.callback(payload)
            elif payload["code"]:
                # Only process callbacks with authorization code
                LOGGER.info(
                    "OAuth callback received successfully. Path: %s, Has code: yes, State: %s",
                    self.path,
                    payload.get("state", "unknown")
                )
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    "<html><body><h1>Authorization Complete</h1>"
                    "<p>You can close this window.</p></body></html>".encode()
                )
                self.callback(payload)
            else:
                # Callback without code - ignore it (might be Chrome DevTools or other requests)
                LOGGER.debug("OAuth callback received without code, ignoring: %s", self.path)
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    "<html><body><h1>OK</h1></body></html>".encode()
                )
                # Don't call callback for requests without code
        except Exception as exc:  # pragma: no cover - defensive logging
            LOGGER.exception("Error handling OAuth callback: %s", exc)
            self.callback({"code": None, "error": str(exc), "state": None})


class OAuthFlow:
    """Encapsulates building the consent URL, running callback server, and exchanging tokens."""

    def __init__(self, config: OAuthConfig) -> None:
        self.config = config
        self._result: Optional[Dict[str, Optional[str]]] = None
        self._server: Optional[HTTPServer] = None
        self._actual_port: Optional[int] = None  # Store the actual port used (may differ from config if port was busy)

    def _is_port_available(self, port: int) -> bool:
        """Check if a port is available for binding."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("localhost", port))
                return True
            except OSError:
                return False
    
    def _free_port_if_needed(self, port: int) -> bool:
        """Attempt to free a port if it's in use by another reauth process.
        
        This is safe because we only kill processes that are likely our own reauth processes.
        Returns True if port was freed or was already available, False if couldn't free it.
        """
        if self._is_port_available(port):
            return True
        
        LOGGER.warning(f"Port {port} is in use, attempting to free it...")
        
        try:
            # Try to find and kill process using the port
            # Use lsof on macOS/Linux
            result = subprocess.run(
                ['lsof', '-ti', f':{port}'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    try:
                        pid_int = int(pid)
                        LOGGER.info(f"Killing process {pid_int} using port {port}")
                        subprocess.run(['kill', '-9', str(pid_int)], timeout=5, check=False)
                    except (ValueError, subprocess.TimeoutExpired):
                        continue
                
                # Wait a bit for port to be released
                time.sleep(1)
                
                # Check if port is now available
                if self._is_port_available(port):
                    LOGGER.info(f"Successfully freed port {port}")
                    return True
                else:
                    LOGGER.warning(f"Port {port} still in use after kill attempt")
                    return False
            else:
                LOGGER.warning(f"No process found using port {port} (or lsof not available)")
                return False
                
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as e:
            LOGGER.debug(f"Could not free port {port}: {e}")
            return False

    def _find_available_port(self, start_port: int, max_attempts: int = 10) -> Optional[int]:
        """Find an available port starting from start_port."""
        for i in range(max_attempts):
            port = start_port + i
            if self._is_port_available(port):
                return port
        return None

    def build_authorization_url(self, credential: AutomationCredential, state: str) -> str:
        """Construct the YouTube OAuth consent URL for the target channel."""
        scopes = self.config.scopes or [
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube",
            "https://www.googleapis.com/auth/youtube.force-ssl",
        ]

        # Use actual port if server was started, otherwise use configured port
        port = self._actual_port if self._actual_port else self.config.redirect_port

        params = {
            "client_id": self.config.client_id,
            "redirect_uri": f"http://localhost:{port}/callback",
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
        """Launch the HTTP server in a background thread.
        
        Note: We MUST use the configured port because it must match the redirect_uri
        registered in Google OAuth Console. If the port is busy, we attempt to free it
        automatically before raising an error.
        """
        port = self.config.redirect_port
        
        # Try to free port if it's in use (might be from another reauth process)
        if not self._is_port_available(port):
            LOGGER.info(f"Port {port} is in use, attempting to free it...")
            if not self._free_port_if_needed(port):
                LOGGER.warning(f"Could not free port {port}, will try to bind anyway")
        
        try:
            self._actual_port = port
            handler = lambda *args: _OAuthCallbackHandler(self._store_result, *args)  # noqa: E731
            self._server = HTTPServer(("localhost", port), handler)
            thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            thread.start()
            LOGGER.debug("Started OAuth callback server on port %s", port)
            
        except OSError as e:
            # Check if it's "Address already in use" error
            is_address_in_use = (
                e.errno == 98 or  # Linux/macOS errno
                e.errno == 48 or  # macOS alternative errno
                "Address already in use" in str(e) or
                "address already in use" in str(e).lower()
            )
            
            if is_address_in_use:
                # Clean up if server was partially created
                if self._server:
                    try:
                        self._server.server_close()
                    except Exception:
                        pass
                    self._server = None
                self._actual_port = None
                
                # Provide helpful error message with instructions
                error_msg = (
                    f"Port {port} is already in use. This port must be available because "
                    f"it must match the redirect_uri registered in Google OAuth Console "
                    f"(http://localhost:{port}/callback).\n\n"
                    f"To free the port, run:\n"
                    f"  lsof -ti :{port} | xargs kill -9\n\n"
                    f"Or find the process manually:\n"
                    f"  lsof -i :{port}\n"
                    f"  kill -9 <PID>\n\n"
                    f"Then try the reauthorization again."
                )
                LOGGER.error(error_msg)
                raise OSError(error_msg) from e
            else:
                # Different error, re-raise
                LOGGER.error("Failed to start callback server on port %s: %s", port, e)
                raise

    def _shutdown_callback_server(self) -> None:
        """Tear down the callback server if running."""
        if self._server:
            port = self._actual_port if self._actual_port else self.config.redirect_port
            self._server.shutdown()
            self._server.server_close()
            LOGGER.debug("Shutdown OAuth callback server on port %s", port)
        self._server = None
        self._actual_port = None

    def _store_result(self, payload: Dict[str, Optional[str]]) -> None:
        """Store callback payload. Only store if we don't already have a result with a code."""
        # If we already have a result with a code, don't overwrite it
        if self._result and self._result.get("code") and not payload.get("code"):
            LOGGER.debug("Ignoring callback without code, already have code: %s", payload)
            return
        
        LOGGER.info("Storing OAuth callback result: error=%s, has_code=%s, state=%s", 
                    payload.get("error"), "yes" if payload.get("code") else "no",
                    payload.get("state", "unknown"))
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
        # Use actual port if server was started, otherwise use configured port
        port = self._actual_port if self._actual_port else self.config.redirect_port
        data = {
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": f"http://localhost:{port}/callback",
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
            self._actual_port = None
            self._start_callback_server()

            auth_url = self.build_authorization_url(credential, state)
            open_browser(auth_url)
            LOGGER.info("Opened browser for OAuth consent: channel=%s", credential.channel_name)

            outcome = self.wait_for_authorization()

            if outcome.get("error"):
                error_msg = outcome["error"]
                # Include error_description if available for better diagnostics
                if outcome.get("error_description"):
                    error_msg = f"{error_msg}: {outcome['error_description']}"
                LOGGER.error(
                    "OAuth authorization failed for %s. Error: %s, Error description: %s",
                    credential.channel_name,
                    outcome.get("error"),
                    outcome.get("error_description")
                )
                return ReauthResult(
                    channel_name=credential.channel_name,
                    status=ReauthStatus.FAILED,
                    error=error_msg,
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



