#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for converter_client.to_tdata wrapper using mocked httpx AsyncClient."""
import asyncio
import json
import os
import sys

import httpx

ROOT = os.path.dirname(os.path.dirname(__file__))
LIB_PATH = os.path.normpath(os.path.join(ROOT, "lib"))
if LIB_PATH not in sys.path:
    sys.path.insert(0, LIB_PATH)

from lib.converter_client import to_tdata


class _DummyResp:
    def __init__(self, data, status_code=200, json_ok=True):
        self._data = data
        self.status_code = status_code
        self._json_ok = json_ok
        self.text = json.dumps(data) if isinstance(data, dict) else str(data)
    def json(self):
        if self._json_ok:
            return self._data
        raise ValueError("Invalid JSON")
    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("HTTP error", request=None, response=self)


class _DummyClient:
    def __init__(self, resp=None, raise_on_post=None):
        self._resp = resp or _DummyResp({"ok": True})
        self._raise_on_post = raise_on_post
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        return False
    async def post(self, url, json=None):
        if self._raise_on_post:
            raise self._raise_on_post
        return self._resp


def test_to_tdata_success(monkeypatch):
    payload = {"backup": {"data": "x"}}
    resp = _DummyResp({"status": "ok", "tdata": "dummy"})

    class Client(_DummyClient):
        def __init__(self):
            super().__init__(resp=resp)

    monkeypatch.setattr("lib.converter_client.httpx.AsyncClient", lambda timeout=None: Client())
    result = asyncio.run(to_tdata(payload))
    assert result == {"status": "ok", "tdata": "dummy"}


def test_to_tdata_timeout(monkeypatch):
    payload = {"backup": {"data": "x"}}

    class Client(_DummyClient):
        async def post(self, url, json=None):
            raise httpx.TimeoutException("timeout")

    monkeypatch.setattr("lib.converter_client.httpx.AsyncClient", lambda timeout=None: Client())
    result = asyncio.run(to_tdata(payload))
    assert result.get("error") == "timeout"


def test_to_tdata_http_error(monkeypatch):
    payload = {"backup": {"data": "x"}}

    class Client(_DummyClient):
        async def post(self, url, json=None):
            class FakeResp:
                status_code = 404
                text = "Not Found"
            raise httpx.HTTPStatusError("Not Found", request=None, response=FakeResp())

    monkeypatch.setattr("lib.converter_client.httpx.AsyncClient", lambda timeout=None: Client())
    result = asyncio.run(to_tdata(payload))
    assert result.get("error") == "http_error"
    assert result.get("status") == 404


def test_to_tdata_invalid_json(monkeypatch):
    payload = {"backup": {"data": "x"}}

    class Client(_DummyClient):
        async def post(self, url, json=None):
            resp = _DummyResp({"invalid": "json"}, json_ok=False)
            return resp

    monkeypatch.setattr("lib.converter_client.httpx.AsyncClient", lambda timeout=None: Client())
    result = asyncio.run(to_tdata(payload))
    assert result.get("error") == "invalid_response"
