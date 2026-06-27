#!/usr/bin/env python3
"""
latvi.space Auto Coin
浏览器登录 latvi（无代理，latvi 没有 CF）→ cookies → requests 走 GOST 代理调 linkvertise API
"""
import time, re, json, os, subprocess, requests
from datetime import datetime, timezone
from seleniumbase import Driver

BASE = "https://dash.latvi.space"
EMAIL = os.environ.get("LATVI_EMAIL", "btpp03@gmail.com")
PASSWORD = os.environ.get("LATVI_PASSWORD", "Hlm@0649")
MAX_CLAIMS = int(os.environ.get("MAX_CLAIMS", "20"))
LOCAL_PROXY = "http://127.0.0.1:8080"
PROXY_LIST = [p.strip() for p in os.environ.get("PROXY_LIST", "").split(",") if p.strip()]

sess = requests.Session()

def log(m): print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {m}", flush=True)

def start_gost(proxy_url):
    subprocess.run(["pkill", "-f", "gost"], capture_output=True)
    time.sleep(1)
    cmd = ["nohup", "./gost", "-L", f"http://:8080", "-F", proxy_url]
    with open("gost.log", "a") as f:
        subprocess.Popen(cmd, stdout=f, stderr=f)
    time.sleep(3)
    try:
        r = requests.get("https://api.ipify.org", proxies={"http": LOCAL_PROXY, "https": LOCAL_PROXY}, timeout=10)
        ip = r.text.strip()
        log(f"✅ GOST | IP: {ip}")
        return ip
    except Exception as e:
        log(f"❌ GOST: {e}"); return None

def get_content(campaign, gost=False):
    """Get linkvertise task content"""
    url = f"https://linkvertise.com/api/v1/getContent?campaign={campaign}"
    proxies = {"http": LOCAL_PROXY, "https": LOCAL_PROXY} if gost else None
    try:
        r = sess.get(url, proxies=proxies, timeout=20, allow_redirects=True)
        return r.text, r
    except Exception as e:
        log(f"getContent error: {e}")
        return None, None

def earn_by_requests(gost=False):
    """Earn coins via API calls through proxy"""
    # Get linkvertise URL from latvi
    r = sess.get(f"{BASE}/linkvertise", timeout=15)
    html = r.text
    
    # Extract campaign from the page
    m = re.search(r'linkvertise\.com/(\d+)', html)
    if not m:
        log("❌ no campaign on latvi page")
        return False
    cid = m.group(1)
    log(f"campaign: {cid}")
    
    # Also try to send start request to latvi
    r2 = sess.get(f"{BASE}/linkvertise", timeout=15)
    
    # Get content via API (through proxy)
    body, resp = get_content(cid, gost)
    if body is None:
        log("❌ getContent failed"); return False
    
    log(f"getContent: {body[:100]}")
    
    if "WaitTask" in body:
        log("WaitTask found ✓")
        time.sleep(12)
        
        body2, _ = get_content(cid, gost)
        log(f"after wait: {body2[:100] if body2 else 'None'}")
        
        if body2 and "DetailPageTargetData" in body2:
            try:
                data = json.loads(body2)
                link = data.get("data", {}).get("link", "")
                if link:
                    log(f"verify: {link[:60]}")
                    r3 = sess.get(link, proxies={"http": LOCAL_PROXY, "https": LOCAL_PROXY} if gost else None, timeout=15)
                    log(f"verify status: {r3.status_code}")
                    log("✅ credited!")
                    return True
            except: pass
        
        time.sleep(8)
        body3, _ = get_content(cid, gost)
        log(f"final: {body3[:100] if body3 else 'None'}")
        
        if body3 and "DetailPageTargetData" in body3:
            try:
                data = json.loads(body3)
                link = data.get("data", {}).get("link", "")
                if link:
                    log(f"verify: {link[:60]}")
                    r3 = sess.get(link, proxies={"http": LOCAL_PROXY, "https": LOCAL_PROXY} if gost else None, timeout=15)
                    log("✅ credited!")
                    return True
            except: pass
    
    # Check latvi for success
    r4 = sess.get(f"{BASE}/linkvertise", timeout=15)
    if "success" in r4.text.lower():
        log("✅ credited!")
        return True
    
    log("❌ failed"); return False

def try_proxy(proxy_url, idx, total):
    log(f"\n{'='*40}")
    log(f"代理 [{idx}/{total}]: {proxy_url[:30]}...")
    ip = start_gost(proxy_url)
    if not ip:
        log("⚠️ 代理不可用"); return False
    
    # Browser login to latvi (no proxy)
    d = Driver(uc=True, headless=True, browser="chrome")
    try:
        d.get(f"{BASE}/login"); time.sleep(2)
        d.type('input[name="email"]', EMAIL)
        d.type('input[name="password"]', PASSWORD)
        d.click('button[type="submit"]'); time.sleep(3)
        
        if "/home" not in d.current_url:
            log("❌ browser login failed"); return None
        log("✅ browser login")
        
        # Extract cookies to requests session
        for c in d.get_cookies():
            sess.cookies.set(c['name'], c['value'], domain=c.get('domain', ''))
        log(f"cookies: {len(d.get_cookies())}")
        
        # Check cooldown
        d.get(f"{BASE}/linkvertise"); time.sleep(2)
        html = d.get_page_source()
        m = re.search(r'Claims Today:\s*(\d+)\s*/\s*(\d+)', html)
        if m:
            rem = int(m.group(2)) - int(m.group(1))
            log(f"{m.group(1)}/{m.group(2)} ({rem} left)")
            if rem <= 0: log("done"); return True
        
        # Balance
        m = re.search(r'([\d.]+)\s*(?:credit|coin)', html, re.I)
        b0 = float(m.group(1)) if m else 0.0
        log(f"balance: {b0}")
        
    finally:
        try: d.quit(); except: pass
    
    # Earn via requests (through GOST proxy)
    ok_cnt = 0
    for i in range(min(rem if 'rem' in dir() else MAX_CLAIMS, MAX_CLAIMS)):
        log(f"--- #{i+1} ---")
        if earn_by_requests(gost=True): ok_cnt += 1
        else: break
        time.sleep(3)
    
    # Check final balance
    r = sess.get(f"{BASE}/home", timeout=15)
    m = re.search(r'([\d.]+)\s*(?:credit|coin)', r.text, re.I)
    b1 = float(m.group(1)) if m else 0.0
    log(f"done {ok_cnt} ok {b0}→{b1} (+{b1-b0})")
    return True

def main():
    log("🚀 latvi (browser login + requests earn)")
    if not PROXY_LIST:
        log("❌ no PROXY_LIST"); return
    log(f"共 {len(PROXY_LIST)} 个代理")
    
    for idx, proxy in enumerate(PROXY_LIST, 1):
        result = try_proxy(proxy, idx, len(PROXY_LIST))
        if result is True:
            log("✅ 完成！"); return
        elif result is False:
            log("⚠️ 换代理..."); continue
        else:
            log("⚠️ 失败，停止"); break
    log("❌ 全失败")

if __name__ == "__main__":
    main()
