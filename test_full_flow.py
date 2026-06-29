#!/usr/bin/env python3
"""Test latvi full flow through talordata proxy"""
import os, sys, re, json, logging, urllib.request

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("lv-test")

BASE = "https://dash.latvi.space"
EMAIL = os.environ.get("LATVI_EMAIL")
PASSWORD = os.environ.get("LATVI_PASSWORD")
PROXY = os.environ.get("PROXY", "").strip()

import requests as rq
sess = rq.Session()
if PROXY:
    sess.proxies = {"http": PROXY, "https": PROXY}
    log.info(f"Proxy: {PROXY[:50]}...")

sess.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})

# IP check
try:
    r = sess.get("https://ipinfo.talordata.com", timeout=10)
    d = r.json()
    log.info(f"IP: {d['ip']} | {d['isp']} | {d['hosting']}")
except Exception as e:
    log.warning(f"IP check: {e}")

# Login
log.info(f"Logging in as {EMAIL}...")
r = sess.get(f"{BASE}/login", timeout=15)
m = re.search(r'name="_token"[^>]*value="([^"]*)"', r.text)
token = m.group(1) if m else None
log.info(f"Token: {token[:15] if token else 'none'}")

r2 = sess.post(f"{BASE}/login", data={"email": EMAIL, "password": PASSWORD, "_token": token or ""}, timeout=15)
log.info(f"Login: HTTP {r2.status_code} | URL: {r2.url[:60]}")
if "/login" in r2.url:
    log.error("❌ Login FAILED - still on login page")
    sys.exit(1)
log.info("✅ Logged in!")

# Get coins page
r = sess.get(f"{BASE}/home", timeout=15)
m = re.search(r'([\d.]+)\s*(?:credit|coin)', r.text, re.I)
bal = float(m.group(1)) if m else 0
log.info(f"Balance: {bal}")

# Generate link
r = sess.get(f"{BASE}/linkvertise/generate", timeout=15)
log.info(f"Generate: HTTP {r.status_code}")
log.info(f"Generate URL: {r.url[:80]}")
if r.status_code != 200:
    log.error(f"❌ Generate failed! Response: {r.text[:300]}")
    sys.exit(1)

# Extract link-to.net URL
link_url = None
for p in [r'(https?://link-to\.net/[^\s"\'<>]+)', r'(https?://linkvertise\.com/[^\s"\'<>]+)']:
    m = re.search(p, r.text)
    if m:
        link_url = m.group(1).rstrip("';,\"")
        break
log.info(f"Link URL: {link_url or 'NOT FOUND'}")

if not link_url:
    # Check response for any URL
    for pat in [r'href="([^"]*)"', r"href='([^']*)'", r'url":\s*"([^"]+)"', r'"redirect":"([^"]+)"']:
        ms = re.findall(pat, r.text)
        if ms:
            log.info(f"Found URLs: {ms[:5]}")
    log.error("❌ No link URL found")
    sys.exit(1)

# Follow the redirect chain through proxy
log.info(f"Following redirect chain from {link_url[:60]}...")
max_redirects = 15
url = link_url
for i in range(max_redirects):
    try:
        r = sess.get(url, timeout=30, allow_redirects=False)
        log.info(f"  #{i}: HTTP {r.status_code} | {len(r.content)}b | {r.url[:80]}")
        
        if r.status_code in (301, 302, 303, 307, 308):
            url = r.headers.get("Location", "")
            if not url:
                log.warning("  No Location header!")
                break
            log.info(f"  → {url[:80]}")
        elif r.status_code == 200:
            body = r.text[:500]
            if "Access Denied" in body or "403" in body[:200]:
                log.warning(f"  ❌ Access Denied/403 at step {i}")
            elif "linkvertise" in r.url:
                log.info(f"  ✅ Reached linkvertise!")
            else:
                log.info(f"  ✅ HTTP 200 - reached destination")
            break
        elif r.status_code == 403:
            log.warning(f"  ❌ 403 Forbidden")
            break
        else:
            log.info(f"  Status {r.status_code}")
            break
    except Exception as e:
        log.error(f"  ❌ Error: {str(e)[:100]}")
        break

log.info("=== Test Complete ===")
