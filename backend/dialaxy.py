# coding=utf-8
"""Dialaxy 香港号码采集：无头抓取 + 校验 + 存档，可选回写主接口"""
import asyncio
import json
import re
import os
import sys
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 环境变量覆盖默认值，兼容服务器无显示器与 Docker 环境
HEADLESS = os.getenv("DIALAXY_HEADLESS", "true").lower() == "true"
TARGET_URL = os.getenv("DIALAXY_URL", "https://dialaxy.com/lookups/phone-number-generator/")
API_URL = os.getenv("API_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "")


def save(phones):
    # 存档到项目 backups 目录（与后端 BACKUP_DIR 约定一致，方便对账）
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backups")
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "phones.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({"t": datetime.now().isoformat(), "p": phones}, f, indent=2, ensure_ascii=False)
    logger.info(f"已存档 {len(phones)} 个号码 -> {out_file}")


def push_to_api(phones):
    # 把采集到的号码送主接口校验，仅保留有效号（接口不可达则跳过，不阻塞存档）
    if not phones:
        return phones
    try:
        import urllib.request
        req = urllib.request.Request(
            API_URL.rstrip("/") + "/api/phone/validate",
            data=json.dumps({"numbers": phones}).encode("utf-8"),
            headers={"Content-Type": "application/json", **({"X-API-Key": API_KEY} if API_KEY else {})},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
        valid = [r["number"] for r in data.get("data", []) if r.get("is_valid")]
        logger.info(f"主接口校验：有效 {len(valid)} / 共 {len(phones)}")
        return valid
    except Exception as e:
        logger.warning(f"回写主接口失败（已跳过，仅本地存档）: {e}")
        return phones


async def main():
    from playwright.async_api import async_playwright
    browser = None
    try:
        async with async_playwright() as p:
            # 无头模式：服务器/Docker 必备，本地调试可设 DIALAXY_HEADLESS=false
            browser = await p.chromium.launch(headless=HEADLESS)
            pg = await browser.new_page()
            logger.info(f"打开 {TARGET_URL}（无头={HEADLESS}）...")
            await pg.goto(TARGET_URL, timeout=30000)
            await pg.wait_for_load_state("networkidle", timeout=30000)
            logger.info("选择香港区号...")
            await pg.click('button:has-text("Hong Kong (+852)")', timeout=10000)
            await asyncio.sleep(1)
            logger.info("生成号码...")
            await pg.click('button:has-text("Generate")', timeout=10000)
            await asyncio.sleep(3)
            logger.info("提取号码...")
            txt = await pg.inner_text("body")
            phones = sorted(set(f"+852{x}" for x in re.findall(r'\+852[^\d]*(\d{7,8})', txt)))
            logger.info(f"抓取到 {len(phones)} 个：{phones[:5]}")
            if not phones:
                logger.warning("未抓取到号码，直接退出")
                return 1
            valid = await asyncio.to_thread(push_to_api, phones)
            save(valid)
            return 0
    except Exception as e:
        logger.error(f"采集失败: {e}")
        return 1
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
