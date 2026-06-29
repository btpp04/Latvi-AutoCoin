#!/usr/bin/env python3
"""
latvi.space Auto Coin — Pure requests through GOST + talordata proxy
Losy 思路：短链跳转绕过 linkvertise IP 检查
"""
import os, sys, re, json, time, base64, logging, urllib.request, urllib.parse
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("latvi")

BASE = "https://dash.latvi.space"
EMAIL = os.environ.get("LATVI_EMAIL", "btpp03@gmail.com")
PASSWORD = os.environ.get("LATVI_PASSWORD", "Hlm@0649")
PROXY = os.environ.get("PROXY", "").strip()
MAX_CLAIMS = int(os.environ.get("MAX_CLAIMS", "20"))

import requests
sess = requests.Session()
if PROXY:
    sess.proxies = {"http": PROXY, "https": PROXY}
    log.info(f"Proxy set")

sess.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"})


def login():
    r = sess.get(f"{BASE}/login", timeout=15)
    m = re.search(r'name="_token"[^>]*value="([^"]*)"', r.text)
    token = m.group(1) if m else None
    r2 = sess.post(f"{BASE}/login", data={"email": EMAIL, "password": PASSWORD, "_token": token or ""}, timeout=15)
    if "/home" in r2.url or "logout" in r2.text.lower():
        log.info("✅ Logged in")
        return True
    log.error(f"❌ Login failed: {r2.status_code}")
    return False

def get_balance():
    r = sess.get(f"{BASE}/home", timeout=15)
    m = re.search(r'([\d.]+)\s*(?:credit|coin)', r.text, re.I)
    return float(m.group(1)) if m else 0

def get_cooldown():
    r = sess.get(f"{BASE}/linkvertise", timeout=15)
    m = re.search(r'Claims Today:\s*(\d+)\s*/\s*(\d+)', r.text)
    if m:
        rem = int(m.group(2)) - int(m.group(1))
        log.info(f"Claims: {m.group(1)}/{m.group(2)} ({rem} left)")
        return rem
    return MAX_CLAIMS

def generate_link():
    """Get link-to.net URL with embedded verify URL."""
    r = sess.get(f"{BASE}/linkvertise/generate", timeout=15)
    if r.status_code != 200:
        log.error(f"Generate failed: HTTP {r.status_code}")
        return None, None
    
    # Extract link-to.net URL
    link_url = None
    for p in [r'(https?://link-to\.net/[^\s"\'<>]+)', r'(https?://linkvertise\.com/[^\s"\'<>]+)']:
        m = re.search(p, r.text)
        if m:
            link_url = m.group(1).rstrip("';,\"")
            break
    
    if not link_url:
        log.error("No link URL found")
        return None, None
    
    # Extract verify URL from r= parameter (base64 encoded)
    verify_url = None
    m = re.search(r'r=([A-Za-z0-9+/=]+)', link_url)
    if m:
        try:
            decoded = base64.b64decode(m.group(1)).decode()
            verify_url = decoded
            log.info(f"Verify URL extracted from r= parameter")
        except:
            pass
    
    return link_url, verify_url

def do_claim(link_url, verify_url):
    """
    1. Follow link-to.net redirect → linkvertise.com
    2. Extract the redirect destination from linkvertise page
    3. Call verify URL
    """
    # Step 1: Follow redirect through proxy
    log.info(f"Following shortlink...")
    try:
        r = sess.get(link_url, timeout=30, allow_redirects=False)
        log.info(f"link-to.net: HTTP {r.status_code}")
        if r.status_code in (301, 302, 303, 307, 308):
            target = r.headers.get("Location", "")
            log.info(f"Redirect → {target[:60]}")
            
            # Step 2: Visit linkvertise
            r2 = sess.get(target, timeout=30, allow_redirects=True)
            log.info(f"linkvertise: HTTP {r2.status_code} | {len(r2.content)}b")
            
            if r2.status_code != 200:
                log.warning(f"linkvertise returned {r2.status_code}")
                return False
            
            # Step 3: Try to find the actual redirect URL from the page
            # linkvertise pages have JS that redirects to the verify URL after ads
            # We need to find where it redirects to
            final_url = r2.url
            
            # Look for any redirect URL in the response
            # The linkvertise page usually contains a meta refresh or data URL
            verify_target = None
            body = r2.text
            
            # Check for common patterns
            patterns = [
                r'window\.location\s*=\s*["\']([^"\']+)',
                r'window\.location\.href\s*=\s*["\']([^"\']+)',
                r'location\.href\s*=\s*["\']([^"\']+)',
                r'<meta[^>]*url=([^"\']+)',
                r'"url":\s*"([^"]+verify[^"]+)"',
                r'"success_url":\s*"([^"]+)"',
            ]
            for pat in patterns:
                m2 = re.search(pat, body)
                if m2:
                    t = m2.group(1).replace("\\/", "/")
                    if "latvi" in t.lower() or "verify" in t.lower() or "success" in t.lower():
                        verify_target = t
                        break
            
            if not verify_target and verify_url:
                # If we have the verify URL from the r= param, just call it
                # This might work if linkvertise accepted the visit
                log.info("No redirect found in page, using verify URL from r= param")
                verify_target = verify_url
            
            if verify_target:
                log.info(f"Calling verify: {verify_target[:60]}")
                r3 = sess.get(verify_target, timeout=30, allow_redirects=True)
                log.info(f"Verify: HTTP {r3.status_code} | URL: {r3.url[:60]}")
                if r3.status_code == 200:
                    body_lower = r3.text.lower()
                    if "success" in body_lower or "coin" in body_lower:
                        log.info("✅ Claim SUCCESS!")
                        return True
                    else:
                        log.info(f"Verify response (first 200 chars): {r3.text[:200]}")
                        return True
                else:
                    log.warning(f"Verify failed: HTTP {r3.status_code}")
                    return False
            else:
                log.warning("No verify target found")
                return False
        else:
            log.warning(f"link-to.net unexpected status: {r.status_code}")
            return False
    except Exception as e:
        log.error(f"Claim error: {str(e)[:100]}")
        return False

def main():
    log.info("=== Latvi Auto Coin ===")
    
    if not login():
        return
    
    balance_before = get_balance()
    log.info(f"Balance: {balance_before}")
    
    remaining = get_cooldown()
    if remaining <= 0:
        log.info("No claims available today")
        return
    
    claims = 0
    for i in range(min(remaining, MAX_CLAIMS)):
        log.info(f"\n--- Claim #{i+1} ---")
        link_url, verify_url = generate_link()
        if not link_url:
            log.warning("Failed to get link")
            break
        
        if do_claim(link_url, verify_url):
            claims += 1
            time.sleep(5)
        else:
            log.warning("Claim failed, may need to cool down")
            time.sleep(10)
    
    balance_after = get_balance()
    log.info(f"\n=== Done: {claims} claims | Balance: {balance_before} → {balance_after} ===")

if __name__ == "__main__":
    main()
