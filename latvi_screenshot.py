#!/usr/bin/env python3
"""Login, screenshot dashboard, send TG notification."""
import os, sys, re, json
from datetime import datetime, timezone

EMAIL = os.environ.get("LATVI_EMAIL", "btpp03@gmail.com")
PASSWORD = os.environ.get("LATVI_PASSWORD", "Hlm@0649")
PROXY = os.environ.get("PROXY", "").strip()
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "7935239797:AAHuQ9jZt-cNjcgjqQ9HH0JzkSWlD53EttM")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "644320820")

from playwright.sync_api import sync_playwright

def main():
    bal = "?"
    try:
        with open("/tmp/latvi_balance.txt") as f:
            bal = f.read().strip()
    except: pass

    with sync_playwright() as p:
        launch_args = ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        proxy_config = None

        # Parse proxy for Playwright
        if PROXY.startswith("http://") and "@" in PROXY:
            parts = PROXY.replace("http://", "").split("@")
            if len(parts) == 2:
                auth, host = parts
                username, pw = auth.split(":", 1)
                proxy_config = {"server": f"http://{host}", "username": username, "password": pw}

        browser = p.chromium.launch(headless=True, args=launch_args)

        ctx_kwargs = {"viewport": {"width": 1280, "height": 900}}
        if proxy_config:
            ctx_kwargs["proxy"] = proxy_config

        ctx = browser.new_context(**ctx_kwargs)
        page = ctx.new_page()

        # Login
        page.goto("https://dash.latvi.space/login", timeout=30000)
        page.wait_for_timeout(2000)
        page.fill('input[name="email"]', EMAIL)
        page.fill('input[name="password"]', PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_timeout(3000)

        # Go to daily-rewards page
        page.goto("https://dash.latvi.space/daily-rewards", timeout=30000)
        page.wait_for_timeout(3000)
        page.screenshot(path="/tmp/latvi_rewards.png", timeout=15000)

        # Try to get balance from page
        if bal == "?":
            try:
                store_el = page.query_selector("text=Store")
                if store_el:
                    parent = store_el.evaluate("el => el.closest('li')?.innerText || ''")
                    m = re.search(r'(\d+\.?\d*)', parent)
                    if m: bal = m.group(1)
            except: pass

        browser.close()

    # Send TG notification
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    caption = (
        f"🦾 Latvi Auto Coin\n"
        f"📅 {now}\n"
        f"💰 Balance: {bal} credits\n"
        f"👤 btpp03@gmail.com"
    )

    import urllib.request
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
    boundary = "----boundary123"
    data = b""
    data += f"--{boundary}\r\n".encode()
    data += f'Content-Disposition: form-data; name="chat_id"\r\n\r\n'.encode()
    data += f"{TG_CHAT_ID}\r\n".encode()
    data += f"--{boundary}\r\n".encode()
    data += f'Content-Disposition: form-data; name="caption"\r\n\r\n'.encode()
    data += f"{caption}\r\n".encode()
    data += f"--{boundary}\r\n".encode()
    data += f'Content-Disposition: form-data; name="photo"; filename="latvi.png"\r\n'.encode()
    data += b"Content-Type: image/png\r\n\r\n"
    with open("/tmp/latvi_rewards.png", "rb") as f:
        data += f.read()
    data += f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(url, data=data)
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    try:
        r = urllib.request.urlopen(req, timeout=15)
        print(f"TG sent: {r.read().decode()[:100]}")
    except Exception as e:
        print(f"TG error: {e}")

if __name__ == "__main__":
    main()
