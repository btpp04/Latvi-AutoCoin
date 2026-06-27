#!/usr/bin/env python3
"""
latvi.space Auto Coin — Browser + JS XHR hybrid
UC browser bypasses CF, then JS fetch calls linkvertise API in-browser
"""
import os, sys, time, re, json
from datetime import datetime, timezone
from seleniumbase import Driver

BASE = "https://dash.latvi.space"
EMAIL = os.environ.get("LATVI_EMAIL", "btpp03@gmail.com")
PASSWORD = os.environ.get("LATVI_PASSWORD", "Hlm@0649")
MAX_CLAIMS = int(os.environ.get("MAX_CLAIMS", "20"))

def log(m): print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {m}", flush=True)
def ok(m): log(f"✅ {m}")
def er(m): log(f"❌ {m}")

def init_driver():
    return Driver(uc=True, headless=True, browser="chrome")

def login(d):
    d.get(f"{BASE}/login"); time.sleep(2)
    d.type('input[name="email"]', EMAIL)
    d.type('input[name="password"]', PASSWORD)
    d.click('button[type="submit"]'); time.sleep(2)
    if "/home" in d.current_url: ok("login"); return True
    er(f"login: {d.current_url}"); return False

def daily(d):
    d.get(f"{BASE}/daily-rewards")
    try: d.click('button:contains("Claim")'); time.sleep(2); ok("daily")
    except: pass

def cooldown(d):
    d.get(f"{BASE}/linkvertise"); time.sleep(1)
    m = re.search(r'Claims Today:\s*(\d+)\s*/\s*(\d+)', d.get_page_source())
    if m:
        rem = int(m.group(2)) - int(m.group(1))
        log(f"{m.group(1)}/{m.group(2)} ({rem} left)"); return rem
    return MAX_CLAIMS

def balance(d):
    d.get(f"{BASE}/home"); time.sleep(1)
    m = re.search(r'([\d.]+)\s*(?:credit|coin)', d.get_page_source(), re.I)
    return float(m.group(1)) if m else 0.0

def js_fetch(d, url):
    """Execute fetch in browser context (has CF cookies/headers)"""
    return d.execute_script(f"""
        return fetch("{url}", {{
            headers: {{"User-Agent": navigator.userAgent}}
        }}).then(r => r.text()).catch(e => "FETCH_ERR:" + e.message);
    """)

def earn(d):
    d.get(f"{BASE}/linkvertise"); time.sleep(2)
    try: d.click('a:contains("Start Now")')
    except:
        try: d.click('button:contains("Start")')
        except: er("no start btn"); return False
    
    # Wait for redirect to linkvertise
    time.sleep(5)
    current = d.current_url
    log(f"on: {current[:60]}...")
    
    if "linkvertise" not in current:
        er("not on linkvertise"); return False
    
    # Extract campaign ID
    m = re.search(r'linkvertise\.com/(\d+)', current)
    if not m: er("no campaign"); return False
    cid = m.group(1)
    ok(f"campaign {cid}")
    
    # Use JS fetch to call linkvertise API (browser context = real CF cookies)
    r = js_fetch(d, f"https://linkvertise.com/api/v1/getContent?campaign={cid}")
    log(f"getContent: {r[:200]}")
    
    if "WaitTask" in r:
        ok("WaitTask found")
        try:
            data = json.loads(r)
            log(f"tasks: {json.dumps(data)[:200]}")
        except: pass
        
        # Wait for WaitTask
        time.sleep(12)
        
        # Check task status
        r2 = js_fetch(d, f"https://linkvertise.com/api/v1/getContent?campaign={cid}")
        log(f"after wait: {r2[:200]}")
        
        # If premium, wait and check again
        time.sleep(8)
        r3 = js_fetch(d, f"https://linkvertise.com/api/v1/getContent?campaign={cid}")
        log(f"after premium: {r3[:200]}")
        
        if "DetailPageTargetData" in r3:
            try:
                data = json.loads(r3)
                link = data.get("data", {}).get("link", "")
                log(f"✅ verify URL: {link[:80]}")
                # Visit verify URL from browser
                d.get(link); time.sleep(3)
                ok("credited!")
                return True
            except: pass
    
    # Check if page has auto-redirected back to latvi
    time.sleep(3)
    if "latvi.space" in d.current_url:
        body = d.get_page_source()
        if "success" in body.lower() or "credited" in body.lower():
            ok("credited!"); return True
    
    er("chain failed"); return False

def main():
    ok("🚀 latvi JS-XHR")
    d = init_driver()
    try:
        login(d)
        daily(d)
        rem = cooldown(d)
        if rem <= 0: ok("done"); return
        
        b0 = balance(d); ok(f"balance {b0}")
        ok_cnt = 0
        for i in range(min(rem, MAX_CLAIMS)):
            log(f"--- #{i+1} ---")
            if earn(d): ok_cnt += 1
            else: break
            time.sleep(5)
        
        b1 = balance(d)
        ok(f"done {ok_cnt} ok {b0} → {b1} (+{b1-b0})")
    finally:
        try: d.quit(); except: pass

if __name__ == "__main__":
    main()
