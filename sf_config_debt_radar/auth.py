"""Authentication helpers for SAP SuccessFactors OData v2."""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def build_basic_auth_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def derive_token_url(base_url: str) -> str:
    parsed = urlparse(base_url.rstrip("/"))
    return f"{parsed.scheme}://{parsed.netloc}/oauth/token"


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


@dataclass
class SFClient:
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
        if self.auth_method == "basic":
            if not self.username or not self.password:
                raise ValueError("username and password are required for basic auth")
            self.session.headers.update(
                {
                    "Authorization": build_basic_auth_header(
                        self.username, self.password
                    ),
                    "Accept": "application/json",
                }
            )
        elif self.auth_method == "oauth2":
            if not self.client_id or not self.client_secret:
                raise ValueError("client_id and client_secret are required for oauth2")
            if not self.token_url:
                self.token_url = derive_token_url(self.base_url)
            self.refresh_token()
        else:
            raise ValueError(f"unsupported auth_method: {self.auth_method}")

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
        response = requests.post(
            self.token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "company_id": self.company_id,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        token = payload["access_token"]
        self._token_expiry = time.time() + int(payload.get("expires_in", 3600)) - 60
        self.session.headers.update(
            {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        )

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
