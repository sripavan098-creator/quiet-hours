"""Minimal Ring Partner API client (standard library only).

Implements the documented calls:
  POST https://oauth.ring.com/oauth/token           authorization_code / refresh_token
  GET  https://api.amazonvision.com/v1/devices     device discovery

The event-history call (GET /v1/history/devices/{id}/events) is included with
pass-through query parameters only. Its query options were not readable from
the docs fetched while building this, so they are not guessed here.

The transport is injectable so tests run without network access. Live use
needs real credentials from the Ring Developer Portal, which this repo does
not contain.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable

OAUTH_TOKEN_URL = "https://oauth.ring.com/oauth/token"
API_BASE = os.environ.get("RING_API_BASE", "https://api.amazonvision.com")

Transport = Callable[[urllib.request.Request], tuple[int, bytes]]


def _default_transport(req: urllib.request.Request) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()


class RingAPIError(RuntimeError):
    def __init__(self, status: int, body: bytes):
        super().__init__(f"Ring API returned {status}: {body[:200]!r}")
        self.status = status


@dataclass
class Tokens:
    access_token: str
    refresh_token: str | None = None


class RingClient:
    def __init__(self, client_id: str, client_secret: str, tokens: Tokens,
                 transport: Transport = _default_transport):
        self.client_id = client_id
        self.client_secret = client_secret
        self.tokens = tokens
        self._send = transport

    # ---- OAuth ----------------------------------------------------------
    def exchange_code(self, code: str, code_verifier: str | None = None) -> Tokens:
        form = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        if code_verifier:
            form["code_verifier"] = code_verifier
        self.tokens = self._token_request(form)
        return self.tokens

    def refresh(self) -> Tokens:
        if not self.tokens.refresh_token:
            raise RingAPIError(401, b"no refresh token")
        form = {
            "grant_type": "refresh_token",
            "refresh_token": self.tokens.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        self.tokens = self._token_request(form)
        return self.tokens

    def _token_request(self, form: dict) -> Tokens:
        req = urllib.request.Request(
            OAUTH_TOKEN_URL,
            data=urllib.parse.urlencode(form).encode(),
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        status, body = self._send(req)
        if status != 200:
            raise RingAPIError(status, body)
        data = json.loads(body)
        return Tokens(data["access_token"], data.get("refresh_token"))

    # ---- Partner API -----------------------------------------------------
    def _get(self, path: str, params: dict | None = None, retry_auth: bool = True) -> dict:
        url = API_BASE + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {self.tokens.access_token}",
            "Accept": "application/vnd.api+json",
        })
        status, body = self._send(req)
        if status == 401 and retry_auth and self.tokens.refresh_token:
            self.refresh()
            return self._get(path, params, retry_auth=False)
        if status != 200:
            raise RingAPIError(status, body)
        return json.loads(body)

    def devices(self, include: str | None = None) -> dict:
        params = {"include": include} if include else None
        return self._get("/v1/devices", params)

    def device_events(self, device_id: str, **query) -> dict:
        """Pass-through to GET /v1/history/devices/{id}/events. See module note."""
        return self._get(f"/v1/history/devices/{urllib.parse.quote(device_id, safe='')}/events", query or None)
