# coding=utf-8
"""Dialaxy HK Phone Generator"""
import asyncio, json, re, os, logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def save(phones):
    os.makedirs("backups", exist_ok=True)
    with open("backups/phones.json", "w") as f:
        json.dump({"t": datetime.now().isoformat(), "p": phones}, f, indent=2)
    logger.info(f"Saved {len(phones)} phones")

async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=False)
        pg = await b.new_page()
        logger.info("Opening dialaxy.com...")
        await pg.goto("https://dialaxy.com/lookups/phone-number-generator/")
        await pg.wait_for_load_state("networkidle")
        logger.info("Selecting HK...")
        await pg.click('button:has-text("Hong Kong (+852)")')
        await asyncio.sleep(1)
        logger.info("Generating...")
        await pg.click('button:has-text("Generate")')
        await asyncio.sleep(3)
        logger.info("Extracting...")
        txt = await pg.inner_text("body")
        phones = list(set(re.findall(r'\+852[^\d]*(\d{7,8})', txt)))
        logger.info(f"Extracted {len(phones)}: {phones[:5]}")
        if phones: save([f"+852{x}" for x in phones])
        await b.close()

if __name__ == "__main__":
    asyncio.run(main())