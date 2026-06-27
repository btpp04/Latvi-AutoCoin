#!/usr/bin/env python3
"""
latvi.space Auto Coin — SeleniumBase UC (browser) mode
Bypasses Cloudflare on linkvertise via real Chromium browser.
"""
import os, sys, time, re, json, requests
from datetime import datetime
from seleniumbase import Driver

BASE = "https://dash.latvi.space"
EMAIL = os.environ.get("LATVI_EMAIL", "btpp03@gmail.com")
PASSWORD = os.environ.get("LATVI_PASSWORD", "Hlm@0649")
MAX_CLAIMS = int(os.environ.get("MAX_CLAIMS", "20"))

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def init_driver():
    d = Driver(uc=True, headless=True, browser="chrome")
    return d

# ─── login ───────────────────────────────
def login(d):
    d.get(f"{BASE}/login")
    time.sleep(2)
    d.type('input[name="email"]', EMAIL)
    d.type('input[name="password"]', PASSWORD)
    d.click('button[type="submit"]')
    time.sleep(2)
    if "/home" in d.current_url or "home" in d.page_source:
        log("login OK")
        return True
    log(f"login fail: {d.current_url}")
    return False

# ─── daily reward ─────────────────────────
def daily(d):
    d.get(f"{BASE}/daily-rewards")
    try:
        d.click('button:contains("Claim")')
        time.sleep(2)
        log("daily claimed ✅")
    except:
        log("daily ⏰ already claimed or not available")

# ─── cooldown ─────────────────────────────
def cooldown(d):
    d.get(f"{BASE}/linkvertise")
    time.sleep(1)
    body = d.get_page_source()
    m = re.search(r'Claims Today:\s*(\d+)\s*/\s*(\d+)', body)
    if m:
        done, max_ = int(m.group(1)), int(m.group(2))
        rem = max_ - done
        log(f"progress {done}/{max_} ({rem} left)")
        return rem
    log("progress ?/?")
    return MAX_CLAIMS

# ─── balance ──────────────────────────────
def balance(d):
    d.get(f"{BASE}/home")
    body = d.get_page_source()
    m = re.search(r'([\d.]+)\s*(?:credit|coin)', body, re.I)
    return float(m.group(1)) if m else 0.0

# ─── earn ─────────────────────────────────
def earn(d):
    d.get(f"{BASE}/linkvertise")
    time.sleep(2)
    
    try:
        d.click('a:contains("Start Now")')
    except:
        try:
            d.click('button:contains("Start")')
        except:
            log("no start button found")
            return False
    
    log("clicked Start Now, waiting for redirect...")
    time.sleep(3)
    current = d.current_url
    log(f"redirected to: {current[:60]}...")
    
    if "linkvertise" in current:
        log("on linkvertise, completing tasks...")
        for i in range(15):
            time.sleep(2)
            current = d.current_url
            log(f"  check {i+1}: {current[:60]}...")
            if "latvi.space" in current and "verify" in current:
                log(f"✅ verify URL reached!")
                return True
            if "linkvertise" not in current:
                break
    
    if "latvi.space" in d.current_url:
        time.sleep(1)
        log("back on latvi.space")
        if "verify" in d.current_url:
            log(f"✅ verify: {d.current_url[:70]}")
            return True
        body = d.get_page_source()
        if "success" in body.lower() or "credited" in body.lower():
            log("✅ credited!")
            return True
    
    log(f"❌ earn failed, final url: {d.current_url[:60]}")
    return False

# ─── main ─────────────────────────────────
def main():
    log("🚀 latvi auto coin (UC browser)")
    d = init_driver()
    
    try:
        login(d)
        daily(d)
        rem = cooldown(d)
        if rem <= 0:
            log("🎉 done for today")
            return
        
        b0 = balance(d)
        log(f"balance {b0}")
        
        ok_cnt = 0
        for i in range(min(rem, MAX_CLAIMS)):
            log(f"--- #{i+1} ---")
            if earn(d):
                ok_cnt += 1
            else:
                break
            time.sleep(5)
        
        b1 = balance(d)
        log(f"done {ok_cnt} ok {b0} → {b1} (+{b1-b0})")
    finally:
        d.quit()

if __name__ == "__main__":
    main()
