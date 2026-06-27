#!/usr/bin/env python3
"""
latvi.space Auto Coin
直连 latvi (无需代理) → SOCKS5 走 linkvertise API
"""
import time, re, json, os, subprocess, requests
from datetime import datetime, timezone

BASE = "https://dash.latvi.space"
EMAIL = os.environ.get("LATVI_EMAIL", "btpp03@gmail.com")
PASSWORD = os.environ.get("LATVI_PASSWORD", "Hlm@0649")
MAX_CLAIMS = int(os.environ.get("MAX_CLAIMS", "20"))
LOCAL_PROXY = "http://127.0.0.1:8080"
PROXY_URL = os.environ.get("PROXY_URL", "")

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

def direct_get(path, **kw):
    return sess.get(f"{BASE}{path}", timeout=15, **kw)

def proxy_get(url, **kw):
    return sess.get(url, proxies={"http": LOCAL_PROXY, "https": LOCAL_PROXY}, timeout=20, **kw)

def login():
    """Direct login (latvi has no CF)"""
    r = direct_get("/login")
    m = re.search(r'name="_token"[^>]*value="([^"]*)"', r.text)
    token = m.group(1) if m else None
    
    r2 = sess.post(f"{BASE}/login", data={
        "email": EMAIL, "password": PASSWORD,
        **(("_token", token) if token else {})
    }, timeout=15)
    
    if "/home" in r2.url or "logout" in r2.text.lower():
        log("✅ login"); return True
    log(f"❌ login: {r2.status_code}"); return False

def balance():
    r = direct_get("/home")
    m = re.search(r'([\d.]+)\s*(?:credit|coin)', r.text, re.I)
    return float(m.group(1)) if m else 0.0

def cooldown():
    r = direct_get("/linkvertise")
    m = re.search(r'Claims Today:\s*(\d+)\s*/\s*(\d+)', r.text)
    if m:
        rem = int(m.group(2)) - int(m.group(1))
        log(f"{m.group(1)}/{m.group(2)} ({rem} left)"); return rem
    return MAX_CLAIMS

def earn():
    """Get campaign from latvi, then use proxy for linkvertise API"""
    # 1. Direct: hit /linkvertise to get campaign (latvi redirects through shorteners)
    r = direct_get("/linkvertise")
    
    # Check if we got redirected to a shortener
    if r.status_code == 302 or r.status_code == 301:
        redirect_url = r.headers.get("Location", "")
        log(f"redirect: {redirect_url[:60]}")
        # Follow redirect through proxy
        r2 = proxy_get(redirect_url.replace("https://", "http://", 1) if LOCAL_PROXY.startswith("http") else redirect_url)
        log(f"after redirect: {r2.url[:60]}")
    elif r.status_code == 200:
        # Page has a link/button - extract campaign from page content
        m = re.search(r'linkvertise\.com/(\d+)', r.text)
        if m:
            cid = m.group(1)
            log(f"campaign: {cid}")
        else:
            # Look for shortener URL
            m2 = re.search(r'href="(https?://[^"]*)"', r.text)
            if m2:
                link_url = m2.group(1)
                log(f"link: {link_url[:60]}")
                r2 = proxy_get(link_url)
                log(f"followed: {r2.url[:60]}")
                m3 = re.search(r'linkvertise\.com/(\d+)', r2.text)
                if m3:
                    cid = m3.group(1)
                else:
                    log("❌ no campaign found")
                    return False
            else:
                log("❌ no link in page")
                return False
    
    # Extract campaign ID from URL
    cid = None
    for url in [r.url, r.headers.get("Location", "")]:
        m = re.search(r'linkvertise\.com/(\d+)', url)
        if m: cid = m.group(1); break
    
    if not cid:
        log("❌ could not find campaign"); return False
    
    log(f"campaign: {cid}")
    
    # 2. Proxy: call linkvertise API
    api_url = f"https://linkvertise.com/api/v1/getContent?campaign={cid}"
    
    for attempt in range(3):
        try:
            rapi = proxy_get(api_url)
            log(f"getContent: {rapi.text[:120]}")
            
            if "WaitTask" in rapi.text:
                log("WaitTask ✓")
                time.sleep(14)
                
                rapi2 = proxy_get(api_url)
                log(f"after wait: {rapi2.text[:120]}")
                
                if "DetailPageTargetData" in rapi2.text:
                    try:
                        data = json.loads(rapi2.text)
                        link = data.get("data", {}).get("link", "")
                        if link:
                            log(f"verify: {link[:60]}")
                            rv = direct_get(link.replace(f"{BASE}", ""))
                            log(f"verify {rv.status_code} ✓")
                            return True
                    except: pass
                
                time.sleep(8)
                rapi3 = proxy_get(api_url)
                if "DetailPageTargetData" in rapi3.text:
                    try:
                        data = json.loads(rapi3.text)
                        link = data.get("data", {}).get("link", "")
                        if link:
                            log(f"verify: {link[:60]}")
                            direct_get(link.replace(f"{BASE}", ""))
                            log("✅ credited!"); return True
                    except: pass
            
            if "COMPLETED" in rapi.text or "DetailPageTargetData" in rapi.text:
                try:
                    data = json.loads(rapi.text)
                    link = data.get("data", {}).get("link", "")
                    if link:
                        log(f"verify (immediate): {link[:60]}")
                        direct_get(link.replace(f"{BASE}", ""))
                        log("✅ credited!"); return True
                except: pass
                
        except Exception as e:
            log(f"  attempt {attempt+1}: {str(e)[:60]}")
            time.sleep(5)
    
    # Fallback: check latvi
    r2 = direct_get("/linkvertise")
    if "success" in r2.text.lower():
        log("✅ credited!"); return True
    
    log("❌ failed"); return False

def main():
    log("🚀 latvi (direct login + proxy linkvertise)")
    
    if not PROXY_URL:
        log("❌ no PROXY_URL"); return
    
    ip = start_gost(PROXY_URL)
    if not ip:
        log("❌ GOST failed"); return
    
    if not login(): return
    
    b0 = balance(); log(f"balance: {b0}")
    rem = cooldown()
    if rem <= 0: log("done"); return
    
    ok_cnt = 0
    for i in range(min(rem, MAX_CLAIMS)):
        log(f"--- #{i+1} ---")
        if earn(): ok_cnt += 1
        else: break
        time.sleep(3)
    
    b1 = balance()
    log(f"done {ok_cnt} ok {b0}→{b1} (+{b1-b0})")

if __name__ == "__main__":
    main()
