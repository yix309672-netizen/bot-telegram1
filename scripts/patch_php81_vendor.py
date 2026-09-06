#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PHP 8.1 兼容补丁：给 vendor 内实现内部接口的方法批量加 #[\ReturnTypeWillChange]

背景：admin 的 ThinkPHP 6.0 vendor 是 2020 年版本，在 PHP 8.1 下会因
ArrayAccess/JsonSerializable 等接口的 tentative return type 直接 500。
vendor/ 不入库（git 忽略），composer install 重装后需重跑本脚本。

用法：python scripts/patch_php81_vendor.py
"""
import os
import re
import sys

METHODS = ('offsetExists', 'offsetGet', 'offsetSet', 'offsetUnset',
           'getIterator', 'jsonSerialize', 'current', 'next', 'key', 'valid', 'rewind')
PAT = re.compile(r'^(\s*)public function (' + '|'.join(METHODS) + r')\s*\(')
ATTR = '#[\\ReturnTypeWillChange]'


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    vendor = os.path.join(root, 'admin', 'vendor')
    if not os.path.isdir(vendor):
        print(f'vendor 不存在：{vendor}，先跑 composer install')
        return 1
    files = 0
    for dirpath, _, names in os.walk(vendor):
        for n in names:
            if not n.endswith('.php'):
                continue
            p = os.path.join(dirpath, n)
            with open(p, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
            out, changed, i = [], False, 0
            while i < len(lines):
                m = PAT.match(lines[i].rstrip('\n'))
                if m and (i == 0 or ATTR not in lines[i - 1]):
                    out.append(m.group(1) + ATTR + '\n')
                    changed = True
                out.append(lines[i])
                i += 1
            if changed:
                with open(p, 'w', encoding='utf-8', newline='') as f:
                    f.writelines(out)
                files += 1
    print(f'补丁文件数: {files}')
    print('另需手动确认的两处单点补丁（已在当前 vendor 生效，重装后检查）：')
    print('  1. think-orm PDOConnection::getRealSql 内 $value 转 (string)')
    print('  2. think-template Template 第248行 ob_implicit_flush(0) 改 false')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
