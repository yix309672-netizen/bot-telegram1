#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Telegram 多号切换器：停客户端 → 备份当前 → 换号 tdata → 拉起
tdata 来源优先级：bot/sessions/<号>/tdata（完整）→ backups/<号>/tdata_*.zip（最新）
用法：python scripts/switch_telegram.py [--list] [phone]
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPDATA = os.environ.get('APPDATA', '')
TG_DIR = os.path.join(APPDATA, 'Telegram Desktop')
TG_TDATA = os.path.join(TG_DIR, 'tdata')
TG_EXE = os.path.join(TG_DIR, 'Telegram.exe')
BACKUP_DIR = os.path.join(ROOT, 'backups')
SESSIONS_DIR = os.path.join(ROOT, 'bot', 'sessions')


def list_phones():
    # 所有有备份的号码：会话文件夹 + 备份子目录 + tdata包名前缀
    phones = set()
    for base in (SESSIONS_DIR, BACKUP_DIR):
        if os.path.isdir(base):
            for n in os.listdir(base):
                if n.startswith('+') or n.isdigit():
                    phones.add(n)
    return sorted(phones)


def find_tdata(phone):
    # 返回 (kind, path)：kind=dir|zip
    d = os.path.join(SESSIONS_DIR, phone, 'tdata')
    if os.path.isdir(d) and os.listdir(d):
        return 'dir', d
    zdir = os.path.join(BACKUP_DIR, phone)
    if os.path.isdir(zdir):
        zips = sorted(glob.glob(os.path.join(zdir, 'tdata_*.zip')))
        if zips:
            return 'zip', zips[-1]
    zips = sorted(glob.glob(os.path.join(BACKUP_DIR, 'tdata_*.zip')))
    return ('zip', zips[-1]) if zips else (None, None)


def stop_client():
    r = subprocess.run(['taskkill', '/F', '/IM', 'Telegram.exe'],
                       capture_output=True, text=True)
    time.sleep(3)
    return r.returncode


def backup_current():
    if not os.path.isdir(TG_TDATA):
        return None
    ts = time.strftime('%Y%m%d%H%M%S')
    out = os.path.join(BACKUP_DIR, f'live_backup_{ts}.zip')
    os.makedirs(BACKUP_DIR, exist_ok=True)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(TG_TDATA):
            for f in files:
                full = os.path.join(root, f)
                z.write(full, os.path.relpath(full, TG_TDATA))
    return out


def switch(phone):
    kind, src = find_tdata(phone)
    if not kind:
        return False, f'找不到 {phone} 的 tdata（先验证并转换）'
    stop_client()
    bak = backup_current()
    if os.path.isdir(TG_TDATA):
        shutil.rmtree(TG_TDATA, ignore_errors=True)
    os.makedirs(TG_TDATA, exist_ok=True)
    if kind == 'dir':
        for item in os.listdir(src):
            s = os.path.join(src, item)
            d = os.path.join(TG_TDATA, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, ignore=shutil.ignore_patterns('emoji'))
            else:
                shutil.copy2(s, d)
    else:
        with zipfile.ZipFile(src) as z:
            z.extractall(TG_TDATA)
    subprocess.Popen([TG_EXE], close_fds=True)
    return True, f'已切到 {phone}（当前已备份：{os.path.basename(bak) if bak else "无"}）'


def main():
    if len(sys.argv) < 2 or sys.argv[1] == '--list':
        print('可用号码：')
        for p in list_phones():
            kind, _ = find_tdata(p)
            print(f'  {p}（{"完整tdata" if kind == "dir" else "转换包" if kind else "无数据"}）')
        return 0
    ok, msg = switch(sys.argv[1])
    print(msg)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
