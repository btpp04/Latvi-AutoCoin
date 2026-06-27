#!/usr/bin/env python3
"""
latvi.space Auto Coin — SeleniumBase UC 完整流程 (slime方法)
在真实浏览器里完成：登录 → 生成链接 → linkvertise(过CF + 完成任务) → verify
"""
import os, sys, time, re
from datetime import datetime, timezone
from seleniumbase import Driver

BASE = "https://dash.latvi.space"
EMAIL = os.environ.get("LATVI_EMAIL", "btpp03@gmail.com")
PASSWORD = os.environ.get("LATVI_PASSWORD", "Hlm@0649")
MAX_CLAIMS = int(os.environ.get("MAX_CLAIMS", "20"))

def log(m): print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {m}", flush=True)
def ok(m): log(f"✅ {m}")
def er(m): log(f"❌ {m}")

def init():
    return Driver(uc=True, headless=True, browser="chrome")

def login(drv):
    drv.get(f"{BASE}/login"); time.sleep(2)
    drv.type('input[name="email"]', EMAIL)
    drv.type('input[name="password"]', PASSWORD)
    drv.click('button[type="submit"]'); time.sleep(2)
    if "/home" in drv.current_url: ok("login"); return True
    er(f"login: {drv.current_url}"); return False

def daily(drv):
    drv.get(f"{BASE}/daily-rewards")
    try: drv.click('button:contains("Claim")'); time.sleep(2); ok("daily")
    except: pass

def cooldown(drv):
    drv.get(f"{BASE}/linkvertise"); time.sleep(1)
    m = re.search(r'Claims Today:\s*(\d+)\s*/\s*(\d+)', drv.get_page_source())
    if m:
        rem = int(m.group(2)) - int(m.group(1))
        log(f"{m.group(1)}/{m.group(2)} ({rem} left)"); return rem
    return MAX_CLAIMS

def balance(drv):
    drv.get(f"{BASE}/home"); time.sleep(1)
    m = re.search(r'([\d.]+)\s*(?:credit|coin)', drv.get_page_source(), re.I)
    return float(m.group(1)) if m else 0.0

def earn(drv):
    # Go to linkvertise page and click Start
    drv.get(f"{BASE}/linkvertise"); time.sleep(2)
    try: drv.click('a:contains("Start Now")')
    except:
        try: drv.click('button:contains("Start")')
        except: er("no start btn"); return False

    log("waiting for linkvertise chain...")

    # Wait up to 90s for the full chain to complete
    start = time.time()
    while time.time() - start < 110:
        time.sleep(3)
        current = drv.current_url

        # Back on latvi.space = done!
        if "latvi.space" in current:
            time.sleep(2)
            body = drv.get_page_source()
            if "verify" in current or "success" in body.lower():
                ok("verify reached!"); return True
            if "linkvertise" not in drv.page_source.lower():
                ok("back on latvi"); return True
            log(f"  on latvi, no verify yet")

        # Still on linkvertise - check what's on the page
        if "linkvertise" in current:
            elapsed = int(time.time() - start)
            if elapsed % 15 == 0:
                log(f"  still on linkvertise ({elapsed}s)")

    er(f"timeout on linkvertise: {drv.current_url[:60]}")
    return False

def main():
    ok("🚀 latvi (slime method)")
    drv = init()
    try:
        login(drv)
        daily(drv)
        rem = cooldown(drv)
        if rem <= 0: ok("done for today"); return

        b0 = balance(drv); ok(f"balance {b0}")
        ok_cnt = 0
        for i in range(min(rem, MAX_CLAIMS)):
            log(f"--- #{i+1} ---")
            if earn(drv): ok_cnt += 1
            else: break
            time.sleep(3)

        b1 = balance(drv)
        ok(f"done {ok_cnt} ok {b0} → {b1} (+{b1-b0})")
    finally:
        try: drv.quit()
        except: pass

if __name__ == "__main__":
    main()
