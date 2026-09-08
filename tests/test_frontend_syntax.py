# coding=utf-8
"""前端内联JS语法门禁：node存在则全检，不存在则跳过"""
import re
import shutil
import subprocess
import tempfile
import os

import pytest

from backend import display_pages, monitor_console, ops_pages
from backend.main_api import ADMIN_SHELL

PAGES = {
    'phones': display_pages.html_phones,
    'sms': display_pages.html_sms,
    'console': monitor_console.html_console,
    'shell': ADMIN_SHELL,
    'bot': ops_pages.html_bot,
    'phone_tool': ops_pages.html_phone_tool,
    'convert': ops_pages.html_convert,
    'system': ops_pages.html_system,
    'mall': ops_pages.html_mall,
    'desktop': ops_pages.html_desktop,
}

node = shutil.which('node')
pytestmark = pytest.mark.skipif(not node, reason='本机无node，跳过JS语法门禁')


def test_inline_js_syntax():
    for name, html in PAGES.items():
        blocks = [b for b in re.findall(r'<script>(.*?)</script>', html, re.S) if b.strip()]
        assert blocks, name
        for i, js in enumerate(blocks):
            with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as f:
                f.write(js)
                path = f.name
            try:
                r = subprocess.run([node, '--check', path], capture_output=True, text=True, timeout=30)
                assert r.returncode == 0, f'{name}[{i}]: {r.stderr[:300]}'
            finally:
                os.unlink(path)
