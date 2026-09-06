#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 hk_numbers_*.txt 批量导入号码：走主接口 /api/phone/import（自动去重与校验）"""
import glob
import json
import os
import urllib.request

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.getenv("API_KEY", "")
DESKTOP = os.getenv("IMPORT_DIR", r'C:\Users\39712\Desktop')
BATCH = 500


def post_import(numbers):
    # 调主接口导入一批，返回统计
    data = json.dumps({"numbers": numbers}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    req = urllib.request.Request(API_URL + "/api/phone/import", data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def main():
    files = sorted(glob.glob(os.path.join(DESKTOP, 'hk_numbers_*.txt')))
    if not files:
        print(f"未找到号码文件：{DESKTOP}\\hk_numbers_*.txt")
        return 1
    total_imp = total_dup = total_inv = 0
    for f in files:
        with open(f, 'r', encoding='utf-8') as fh:
            numbers = [line.strip() for line in fh if line.strip()]
        print(f"文件 {os.path.basename(f)}：{len(numbers)} 个，开始导入...")
        for i in range(0, len(numbers), BATCH):
            try:
                r = post_import(numbers[i:i + BATCH])
            except Exception as e:
                print(f"  批次失败（已跳过 {min(i + BATCH, len(numbers)) - i} 个）: {e}")
                continue
            total_imp += r.get("imported", 0)
            total_dup += r.get("skipped_dup", 0)
            total_inv += len(r.get("skipped_invalid", []))
    print(f"导入完成：新增 {total_imp}，重复跳过 {total_dup}，非法跳过 {total_inv}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
