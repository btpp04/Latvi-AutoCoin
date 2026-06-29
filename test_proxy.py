#!/usr/bin/env python3
"""Quick test: does linkvertise load through proxy in a real browser?"""
import os, sys, logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("lv-test")

PROXY = os.environ.get("PROXY", "").strip()
link_url = sys.argv[1] if len(sys.argv) > 1 else "https://linkvertise.com"

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    ctx_kwargs = {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "viewport": {"width": 1280, "height": 800}
    }
    if PROXY:
        ctx_kwargs["proxy"] = {"server": PROXY}
        log.info(f"Using proxy: {PROXY[:50]}")
    ctx = browser.new_context(**ctx_kwargs)
    page = ctx.new_page()
    
    log.info(f"Navigating to: {link_url[:60]}")
    try:
        page.goto(link_url, wait_until="domcontentloaded", timeout=30000)
        log.info(f"URL after goto: {page.url}")
        log.info(f"Page title: {page.title()}")
        status_code = page.evaluate("() => document.readyState")
        log.info(f"ReadyState: {status_code}")
        content_len = len(page.content())
        log.info(f"Content length: {content_len}")
        
        # Take screenshot
        page.screenshot(path="/tmp/lv_test_screenshot.png")
        log.info("Screenshot saved")
        
        # Check for key patterns
        content = page.content()[:3000]
        if "403" in content or "Access Denied" in content:
            log.warning("⚠️ 403 / Access Denied detected")
        elif "linkvertise" in page.url and "verify" not in page.url:
            log.info("✅ linkvertise.com loaded")
        else:
            log.info(f"→ redirect/other: {page.url[:80]}")
            
    except Exception as e:
        log.error(f"Error: {str(e)[:100]}")
    
    browser.close()
