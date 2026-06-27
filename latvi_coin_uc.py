#!/usr/bin/env python3
"""
latvi.space Auto Coin — SeleniumBase UC mode
直接用浏览器访问 linkvertise，UC 模式过 CF
"""
import time, re, json, os, base64, requests
from datetime import datetime, timezone

BASE = "https://dash.latvi.space"
EMAIL = os.environ.get("LATVI_EMAIL", "btpp03@gmail.com")
PASSWORD = os.environ.get("LATVI_PASSWORD", "Hlm@0649")
MAX_CLAIMS = int(os.environ.get("MAX_CLAIMS", "20"))

sess = requests.Session()

def log(m): print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {m}", flush=True)

def login():
    r = sess.get(f"{BASE}/login", timeout=10)
    m = re.search(r'name="_token"[^>]*value="([^"]*)"', r.text)
    token = m.group(1) if m else None
    data = {"email": EMAIL, "password": PASSWORD}
    if token:
        data["_token"] = token
    r2 = sess.post(f"{BASE}/login", data=data, timeout=15)
    if "/home" in r2.url or "logout" in r2.text.lower():
        log("✅ login")
        return True
    log(f"❌ login: {r2.status_code}")
    return False

def balance():
    r = sess.get(f"{BASE}/home", timeout=10)
    m = re.search(r'([\d.]+)\s*(?:credit|coin)', r.text, re.I)
    return float(m.group(1)) if m else 0.0

def cooldown():
    r = sess.get(f"{BASE}/linkvertise", timeout=10)
    m = re.search(r'Claims Today:\s*(\d+)\s*/\s*(\d+)', r.text)
    if m:
        rem = int(m.group(2)) - int(m.group(1))
        log(f"claims: {m.group(1)}/{m.group(2)} ({rem} left)")
        return rem
    return MAX_CLAIMS

def get_link():
    """Get linkvertise link + verify URL from latvi /linkvertise/generate"""
    r = sess.get(f"{BASE}/linkvertise/generate", timeout=10)
    
    # Extract full link-to.net URL
    m = re.search(r'(https?://link-to\.net/[^\s"\']+)', r.text)
    if not m:
        m = re.search(r'(https?://linkvertise\.com/[^\s"\']+)', r.text)
    
    link_url = m.group(1).rstrip("';") if m else None
    
    # Extract verify URL from base64
    verify_url = None
    m2 = re.search(r'r=([A-Za-z0-9+/=]+)', r.text)
    if m2:
        try:
            decoded = base64.b64decode(m2.group(1)).decode()
            if decoded.startswith("http"):
                verify_url = decoded
        except:
            pass
    
    return link_url, verify_url

def run_browser(link_url, verify_url):
    """Use SeleniumBase UC to visit linkvertise and wait for redirect"""
    from seleniumbase import SB
    
    with SB(uc=True, test=True, headless=True) as sb:
        log(f"opening: {link_url[:60]}...")
        sb.open(link_url)
        sb.sleep(5)
        
        # Check current URL
        current = sb.get_current_url()
        log(f"after 5s: {current[:80]}")
        
        sb.sleep(8)  # Wait for SPA to render
        
        # Take screenshot for debugging
        try:
            sb.save_screenshot("lv_page.png")
            log("screenshot saved")
        except:
            pass
        
        # Get page source for debugging
        try:
            html = sb.get_page_source()
            log(f"page HTML: {len(html)} chars")
            # Look for buttons/links
            btns = sb.find_elements("button")
            log(f"buttons found: {len(btns)}")
            for btn in btns[:10]:
                try:
                    txt = btn.text.strip()
                    if txt:
                        log(f"  btn: '{txt}'")
                except:
                    pass
            links = sb.find_elements("a")
            log(f"links found: {len(links)}")
            for link in links[:10]:
                try:
                    txt = link.text.strip()
                    href = link.get_attribute("href") or ""
                    if txt and len(txt) < 50:
                        log(f"  link: '{txt}' → {href[:60]}")
                except:
                    pass
        except Exception as e:
            log(f"page source error: {str(e)[:60]}")
        
        # Wait for redirect (max 120s)
        for i in range(24):
            sb.sleep(5)
            current = sb.get_current_url()
            log(f"  {(i+1)*5}s: {current[:80]}")
            
            if "latvi.space" in current or "verify" in current:
                log("✅ redirected to latvi!")
                return True
            
            # Try clicking any visible button
            try:
                btns = sb.find_elements("button")
                for btn in btns:
                    if btn.is_displayed():
                        txt = btn.text.lower()
                        if any(k in txt for k in ["continue", "free", "next", "skip", "claim", "start", "download", "go"]):
                            log(f"  clicking: '{btn.text}'")
                            sb.click(btn)
                            sb.sleep(3)
                            break
            except:
                pass
        
        # After waiting, try the verify URL directly
        if verify_url:
            log(f"trying verify: {verify_url[:60]}...")
            # Get cookies from browser session
            cookies = sb.get_cookies()
            for c in cookies:
                sess.cookies.set(c['name'], c['value'])
            
            r = sess.get(verify_url, timeout=15)
            log(f"verify [{r.status_code}]")
            return r.status_code == 200
        
        return False

def main():
    log("🚀 latvi (SeleniumBase UC)")
    
    if not login():
        return
    
    b0 = balance()
    log(f"balance: {b0}")
    
    rem = cooldown()
    if rem <= 0:
        log("no claims left today")
        return
    
    ok = 0
    for i in range(min(rem, MAX_CLAIMS)):
        log(f"--- #{i+1} ---")
        link_url, verify_url = get_link()
        if not link_url:
            log("❌ no link found")
            break
        log(f"link: {link_url[:60]}...")
        
        if run_browser(link_url, verify_url):
            ok += 1
            log("✅ credited!")
        else:
            log("❌ failed")
        time.sleep(3)
    
    b1 = balance()
    log(f"done: {ok} ok, {b0}→{b1} (+{b1-b0})")

if __name__ == "__main__":
    main()
