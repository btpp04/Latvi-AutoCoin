#!/usr/bin/env python3
"""
latvi.space Auto Coin — GOST 代理 + SeleniumBase UC 浏览器完整流程
同步自 freecloud 的成功方案 (多代理自动切换)
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

def wait_for_cf(d, timeout=60):
    """Handle Cloudflare challenge"""
    log("等待页面加载（可能包含 CF 验证）...")
    start = time.time()
    while time.time() - start < timeout:
        page = d.get_page_source().lower()
        # CF still active
        if "checking your browser" in page or "just a moment" in page or "cf-challenge" in page:
            log(f"  CF 验证中... ({int(time.time()-start)}s)")
            try: d.uc_gui_click_captcha(); time.sleep(3)
            except: time.sleep(2)
        else:
            return True
    return False

def login(d):
    d.get(f"{BASE}/login"); time.sleep(2)
    wait_for_cf(d)
    
    # Try several times to find the form
    for attempt in range(3):
        try:
            d.type('input[name="email"]', EMAIL)
            d.type('input[name="password"]', PASSWORD)
            d.click('button[type="submit"]')
            time.sleep(3)
            if "/home" in d.current_url or "dashboard" in d.current_url:
                log("✅ login"); return True
        except Exception as e:
            log(f"  login attempt {attempt+1}: {str(e)[:60]}")
            time.sleep(3)
    
    # Fallback: try uc_open_with_reconnect
    try:
        d.uc_open_with_reconnect(f"{BASE}/login", 30)
        time.sleep(3)
        if d.is_element_visible('iframe[src*="cloudflare"]'):
            d.uc_gui_click_captcha(); time.sleep(5)
        d.type('input[name="email"]', EMAIL)
        d.type('input[name="password"]', PASSWORD)
        d.click('button[type="submit"]'); time.sleep(3)
        if "/home" in d.current_url:
            log("✅ login (uc reconnect)"); return True
    except: pass
    
    log(f"❌ login: {d.current_url}")
    return False

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

def earn(d):
    d.get(f"{BASE}/linkvertise"); time.sleep(2)
    try: d.click('a:contains("Start Now")')
    except:
        try: d.click('button:contains("Start")')
        except: log("❌ no start"); return False

    time.sleep(8)
    current = d.current_url
    log(f"redirected: {current[:60]}...")
    
    if "linkvertise" not in current and "link-to" not in current:
        log("❌ not on linkvertise"); return False

    m = re.search(r'(\d+)', current)
    if not m: log("❌ no campaign"); return False
    cid = m.group(1)
    log(f"campaign: {cid}")

    log("waiting for task chain (up to 110s)...")
    start = time.time()
    while time.time() - start < 110:
        time.sleep(5)
        
        if "latvi.space" in d.current_url:
            body = d.get_page_source()
            if "success" in body.lower() or "credited" in body.lower():
                log("✅ credited!"); return True
            log("back on latvi"); return True

        # Try API via browser navigation
        api_url = f"https://linkvertise.com/api/v1/getContent?campaign={cid}"
        d.get(api_url); time.sleep(2)
        body = d.get_page_source()
        log(f"API: {body[:80]}")
        
        if "DetailPageTargetData" in body:
            try:
                data = json.loads(body)
                link = data.get("data", {}).get("link", "")
                if link:
                    log(f"verify: {link[:60]}")
                    d.get(link); time.sleep(3)
                    log("✅ credited!"); return True
            except: pass
        
        # Go back to linkvertise
        d.get(current); time.sleep(2)
        elapsed = int(time.time() - start)
        log(f"  waiting ({elapsed}s)")

    log(f"❌ timeout"); return False

def try_proxy(proxy_url, idx, total):
    log(f"\n{'='*40}")
    log(f"代理 [{idx}/{total}]: {proxy_url[:30]}...")
    ip = start_gost(proxy_url)
    if not ip:
        log("⚠️ 代理不可用"); return False

    d = Driver(uc=True, headless=True, proxy=LOCAL_PROXY, browser="chrome")
    try:
        if not login(d): return None

        b0 = balance(d)
        log(f"balance: {b0}")

        rem = cooldown(d)
        if rem <= 0:
            log("done for today"); return True

        ok_cnt = 0
        for i in range(min(rem, MAX_CLAIMS)):
            log(f"--- #{i+1} ---")
            if earn(d): ok_cnt += 1
            else: break
            time.sleep(3)

        b1 = balance(d)
        log(f"done {ok_cnt} ok {b0}→{b1} (+{b1-b0})")
        return True
    finally:
        try: d.quit()
        except: pass

def main():
    log("🚀 latvi (GOST + proxy)")
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
