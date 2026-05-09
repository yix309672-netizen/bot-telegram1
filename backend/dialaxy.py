"""Dialaxy HK Phone Generator"""
import asyncio, json, re, os
from datetime import datetime

def save(phones):
    os.makedirs("backups", exist_ok=True)
    with open("backups/phones.json", "w") as f:
        json.dump({"t": datetime.now().isoformat(), "p": phones}, f, indent=2)
    print(f"[OK] Saved {len(phones)} phones")

async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=False)
        pg = await b.new_page()
        print("[1] Opening...")
        await pg.goto("https://dialaxy.com/lookups/phone-number-generator/")
        await pg.wait_for_load_state("networkidle")
        print("[2] Selecting HK...")
        await pg.click('button:has-text("Hong Kong (+852)")')
        await asyncio.sleep(1)
        print("[3] Generating...")
        await pg.click('button:has-text("Generate")')
        await asyncio.sleep(3)
        print("[4] Extracting...")
        txt = await pg.inner_text("body")
        phones = list(set(re.findall(r'\+852[^\d]*(\d{7,8})', txt)))
        print(f"[OK] {len(phones)}: {phones[:5]}")
        if phones: save([f"+852{x}" for x in phones])
        await b.close()

if __name__ == "__main__":
    asyncio.run(main())