#!/usr/bin/env python3
"""
latvi.space Auto Coin — 浏览器直连 linkvertise API
先用 UC 过 Cloudflare，然后用 driver.get() 直接调 API
"""
import os, sys, time, re, json
from datetime import datetime, timezone
from seleniumbase import Driver

BASE = "https://dash.latvi.space"
EMAIL = os.environ.get("LATVI_EMAIL", "btpp03@gmail.com")
PASSWORD = os.environ.get("LATVI_PASSWORD", "Hlm@0649")
MAX_CLAIMS = int(os.environ.get("MAX_CLAIMS", "20"))

def log(m): print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {m}", flush=True)

def init():
    return Driver(uc=True, headless=True, browser="chrome")

def login(d):
    d.get(f"{BASE}/login"); time.sleep(2)
    d.type('input[name="email"]', EMAIL)
    d.type('input[name="password"]', PASSWORD)
    d.click('button[type="submit"]'); time.sleep(2)
    if "/home" in d.current_url: log("✅ login"); return True
    log(f"❌ login: {d.current_url}"); return False

def balance(d):
    d.get(f"{BASE}/home"); time.sleep(1)
    m = re.search(r'([\d.]+)\s*(?:credit|coin)', d.get_page_source(), re.I)
    return float(m.group(1)) if m else 0.0

def cooldown(d):
    d.get(f"{BASE}/linkvertise"); time.sleep(1)
    m = re.search(r'Claims Today:\s*(\d+)\s*/\s*(\d+)', d.get_page_source())
    if m:
        rem = int(m.group(2)) - int(m.group(1))
        log(f"{m.group(1)}/{m.group(2)} ({rem} left)"); return rem
    return MAX_CLAIMS

def get_api(d, url):
    """Navigate browser to API URL and return body text"""
    d.get(url); time.sleep(2)
    return d.get_page_source()

def earn(d):
    # 1. Go to linkvertise generate page
    d.get(f"{BASE}/linkvertise"); time.sleep(2)
    try: d.click('a:contains("Start Now")')
    except:
        try: d.click('button:contains("Start")')
        except: log("❌ no start"); return False

    # 2. Wait for redirect to linkvertise (UC bypasses CF)
    time.sleep(5)
    current = d.current_url
    log(f" redirected: {current[:60]}...")
    if "linkvertise" not in current:
        log("❌ not on linkvertise"); return False

    # Extract campaign
    m = re.search(r'linkvertise\.com/(\d+)', current)
    if not m: log("❌ no campaign"); return False
    cid = m.group(1)
    log(f" campaign: {cid}")

    # 3. Navigate browser to API — same cookies/session as the CF-bypassed page
    api_url = f"https://linkvertise.com/api/v1/getContent?campaign={cid}"
    body = get_api(d, api_url)
    log(f" getContent: {body[:200]}")
    
    if "WaitTask" in body:
        log(" WaitTask found ✓")
        time.sleep(14)
        
        body2 = get_api(d, api_url)
        log(f" after wait: {body2[:200]}")
        
        if "DetailPageTargetData" in body2:
            try:
                data = json.loads(body2)
                link = data.get("data", {}).get("link", "")
                log(f" verify URL: {link[:80]}")
                d.get(link); time.sleep(3)
                log("✅ credited!"); return True
            except:
                log(f" parse error: {body2[:100]}")
        
        time.sleep(8)
        body3 = get_api(d, api_url)
        log(f" final check: {body3[:200]}")
        
        if "DetailPageTargetData" in body3:
            try:
                data = json.loads(body3)
                link = data.get("data", {}).get("link", "")
                log(f" verify URL: {link[:80]}")
                d.get(link); time.sleep(3)
                log("✅ credited!"); return True
            except: pass
    
    # Fallback: go back to latvi and check
    d.get(f"{BASE}/linkvertise"); time.sleep(2)
    body = d.get_page_source()
    if "success" in body.lower():
        log("✅ credited!"); return True
    
    log("❌ failed"); return False

def main():
    log("🚀 latvi (browser API)")
    d = init()
    try:
        login(d)
        rem = cooldown(d)
        if rem <= 0: log("done"); return
        
        b0 = balance(d); log(f"balance {b0}")
        ok_cnt = 0
        for i in range(min(rem, MAX_CLAIMS)):
            log(f"--- #{i+1} ---")
            if earn(d): ok_cnt += 1
            else: break
            time.sleep(3)
        
        b1 = balance(d)
        log(f"done {ok_cnt} ok {b0} → {b1} (+{b1-b0})")
    finally:
        try: d.quit(); except: pass

if __name__ == "__main__":
    main()
