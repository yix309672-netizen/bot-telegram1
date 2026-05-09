#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""End-to-end integration test for the converter -> import flow using dynamic import path."""

import asyncio
import importlib.util
import pathlib


def _load_ci_module():
    base = pathlib.Path(__file__).resolve().parents[1]
    path = base / "local-deploy" / "bot-telegram" / "converter_integration.py"
    spec = importlib.util.spec_from_file_location("ci", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    return mod


def test_end_to_end_success():
    ci = _load_ci_module()
    payload = {"backup": {"data": "x"}, "options": {}}

    async def mock_converter(p):
        return {"tdata": "mocked"}

    async def mock_import(c):
        return {"import_id": 1, "status": "ok"}

    ci.to_tdata_from_converter = mock_converter
    ci.post_import = mock_import

    result = asyncio.run(ci.on_backup_complete(payload))
    assert isinstance(result, dict)
    assert "tdata" in result


def test_end_to_end_conversion_failure():
    ci = _load_ci_module()
    payload = {"backup": {"data": "x"}, "options": {}}

    async def mock_converter(p):
        return {"error": "timeout"}

    ci.to_tdata_from_converter = mock_converter

    result = asyncio.run(ci.on_backup_complete(payload))
    assert isinstance(result, dict)