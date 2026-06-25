"""Authentication helpers for SAP SuccessFactors OData v2.

Auth logic is now delegated to the sapsf_shared SDK
(sapsf_shared.auth.AuthConfig / build_requests_auth).

The thin helpers below (build_basic_auth_header, derive_token_url) are kept
for backward compatibility with existing tests and any external callers.
"""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from sapsf_shared.auth import AuthConfig, build_requests_auth


# ── Thin compatibility helpers (keep existing test surface) ───────────────


def build_basic_auth_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def derive_token_url(base_url: str) -> str:
    parsed = urlparse(base_url.rstrip("/"))
    return f"{parsed.scheme}://{parsed.netloc}/oauth/token"


# ── Internal session factory ──────────────────────────────────────────────


def _session_with_retries() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST", "HEAD"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=8)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"Connection": "close"})
    return session


# ── OData client ──────────────────────────────────────────────────────────


@dataclass
class SFClient:
    """Minimal OData v2 client.  Auth is handled via sapsf_shared.AuthConfig."""

    base_url: str
    auth_method: str = "basic"
    username: str = ""
    password: str = ""
    client_id: str = ""
    client_secret: str = ""
    company_id: str = ""
    token_url: str = ""

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        self.session = _session_with_retries()
        self._token_expiry = 0.0

        # Map local fields onto the shared AuthConfig.
        # Note: local uses auth_method; SDK uses auth_type - same values.
        auth_cfg = AuthConfig(
            base_url=self.base_url,
            auth_type=self.auth_method,
            username=self.username,
            password=self.password,
            client_id=self.client_id,
            client_secret=self.client_secret,
            company_id=self.company_id,
            token_url=self.token_url or "",
        )
        auth_cfg.validate()
        self._auth_cfg = auth_cfg

        auth_obj, cert = build_requests_auth(auth_cfg)
        self.session.auth = auth_obj
        if cert:
            self.session.cert = cert
        self.session.headers.update({"Accept": "application/json"})

        # Pre-record expiry for oauth2 so ensure_token works
        if self.auth_method == "oauth2":
            self._token_expiry = time.time() + 3540  # 59 min optimistic default

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "SFClient":
        sf = config.get("sf", config)
        return cls(
            base_url=sf.get("base_url", ""),
            auth_method=sf.get("auth_method", "basic"),
            username=sf.get("username", ""),
            password=sf.get("password", ""),
            client_id=sf.get("client_id", ""),
            client_secret=sf.get("client_secret", ""),
            company_id=sf.get("company_id", ""),
            token_url=sf.get("token_url", ""),
        )

    def refresh_token(self) -> None:
        """Re-fetch an OAuth2 token and update the session."""
        from sapsf_shared.auth import OAuth2Auth, _BearerAuth  # type: ignore[attr-defined]

        token = OAuth2Auth.fetch_token(self._auth_cfg, force_refresh=True)
        self.session.auth = _BearerAuth(token)
        self._token_expiry = time.time() + 3540

    def ensure_token(self) -> None:
        if self.auth_method == "oauth2" and time.time() >= self._token_expiry:
            self.refresh_token()

    def get(
        self, path: str, *, accept: str = "application/json", timeout: int = 60
    ) -> requests.Response:
        self.ensure_token()
        url = path if path.startswith("http") else f"{self.base_url}/{path.lstrip('/')}"
        headers = dict(self.session.headers)
        headers["Accept"] = accept
        return self.session.get(url, headers=headers, timeout=timeout)

    def get_text(
        self, path: str, *, accept: str = "application/json", timeout: int = 60
    ) -> str:
        response = self.get(path, accept=accept, timeout=timeout)
        response.raise_for_status()
        return response.text

    def get_json(self, path: str, *, timeout: int = 60) -> dict[str, Any]:
        response = self.get(path, accept="application/json", timeout=timeout)
        response.raise_for_status()
        return response.json()

    def count(self, entity: str, filter_expr: str | None = None) -> int | None:
        path = f"{entity}/$count"
        if filter_expr:
            path = f"{path}?$filter={filter_expr}"
        try:
            text = self.get_text(path, timeout=45).strip()
            return int(text)
        except Exception:
            return None

    def test_connection(self) -> tuple[bool, str]:
        for entity in ("EmpJob", "PerPerson", "User"):
            value = self.count(entity)
            if value is not None:
                return True, f"Connected via {entity}. Count: {value}"
        return (
            False,
            "Could not read EmpJob, PerPerson, or User count. Check credentials and RBP permissions.",
        )
