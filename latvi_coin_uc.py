#!/usr/bin/env python3
"""
latvi.space Auto Coin — GraphQL linkvertise bypass
直连 latvi 登录 → publisher.linkvertise.com/graphql 绕过任务 → latvi verify
"""
import time, re, json, os, base64, requests
from datetime import datetime, timezone

BASE = "https://dash.latvi.space"
EMAIL = os.environ.get("LATVI_EMAIL", "btpp03@gmail.com")
PASSWORD = os.environ.get("LATVI_PASSWORD", "Hlm@0649")
MAX_CLAIMS = int(os.environ.get("MAX_CLAIMS", "20"))

# Linkvertise GraphQL
LV_GRAPHQL = "https://publisher.linkvertise.com/graphql"
LV_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Origin": "https://linkvertise.com",
    "Referer": "https://linkvertise.com",
    "Content-Type": "application/json",
}

# GraphQL queries (from linkvertise-bypasser)
GDPC_QUERY = """query getDetailPageContent($linkIdentificationInput: LinkIdentificationInput!, $origin: String, $additional_data: AdditionalDataInput) { getDetailPageContent(linkIdentificationInput: $linkIdentificationInput, origin: $origin, additional_data: $additional_data) { access_token } }"""
CDPC_QUERY = """mutation completeDetailPageContent($linkIdentificationInput: LinkIdentificationInput!, $completeDetailPageContentInput: CompleteDetailPageContentInput!) { completeDetailPageContent(linkIdentificationInput: $linkIdentificationInput, completeDetailPageContentInput: $completeDetailPageContentInput) { TARGET } }"""
GDPT_QUERY = """query getDetailPageTarget($linkIdentificationInput: LinkIdentificationInput!, $token: String!) { getDetailPageTarget(linkIdentificationInput: $linkIdentificationInput, token: $token) { url } }"""

sess = requests.Session()
lv_sess = requests.Session()  # Separate session for linkvertise

def log(m): print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {m}", flush=True)

def direct_get(path, **kw):
    try:
        return sess.get(f"{BASE}{path}", timeout=10, **kw)
    except:
        return sess.get(f"{BASE}{path}", timeout=15, **kw)

def login():
    r = direct_get("/login")
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
    r = direct_get("/home")
    m = re.search(r'([\d.]+)\s*(?:credit|coin)', r.text, re.I)
    return float(m.group(1)) if m else 0.0

def cooldown():
    r = direct_get("/linkvertise")
    m = re.search(r'Claims Today:\s*(\d+)\s*/\s*(\d+)', r.text)
    if m:
        rem = int(m.group(2)) - int(m.group(1))
        log(f"claims: {m.group(1)}/{m.group(2)} ({rem} left)")
        return rem
    return MAX_CLAIMS

def get_campaign():
    """Get linkvertise user_id + post_id + verify URL from latvi /linkvertise/generate"""
    r = direct_get("/linkvertise/generate")
    
    # Extract link-to.net or linkvertise URL: /{user_id}/{post_id}/...
    m = re.search(r'(?:link-to\.net|linkvertise\.com)/(\d+)/([a-z0-9]+)', r.text)
    if not m:
        # Try href
        m2 = re.search(r'href="(https?://[^"]*(?:link-to|linkvertise)[^"]*)"', r.text)
        if m2:
            m = re.search(r'/(?:link-to\.net/|linkvertise\.com/)(\d+)/([a-z0-9]+)', m2.group(1))
    
    if not m:
        return None, None, None
    
    user_id = m.group(1)
    post_id = m.group(2)
    
    # Extract verify URL from base64 r= parameter
    verify_url = None
    m3 = re.search(r'r=([A-Za-z0-9+/=]+)', r.text)
    if m3:
        try:
            decoded = base64.b64decode(m3.group(1)).decode()
            if decoded.startswith("http"):
                verify_url = decoded
        except:
            pass
    
    return user_id, post_id, verify_url

def bypass_linkvertise(user_id, post_id):
    """Bypass linkvertise using GraphQL API (3-step flow)"""
    post_str = f"https://linkvertise.com/{user_id}/{post_id}"
    
    # Step 1: Get access token
    payload1 = {
        "operationName": "getDetailPageContent",
        "variables": {
            "linkIdentificationInput": {
                "userIdAndUrl": {
                    "user_id": user_id,
                    "url": post_id
                }
            },
            "origin": "sharing",
            "additional_data": {
                "taboola": {
                    "user_id": "fallbackUserId",
                    "url": post_str
                }
            }
        },
        "query": GDPC_QUERY
    }
    
    r1 = lv_sess.post(LV_GRAPHQL, json=payload1, headers=LV_HEADERS, timeout=15)
    log(f"step1 [{r1.status_code}]: {r1.text[:120]}")
    
    if r1.status_code != 200:
        return None
    
    try:
        data1 = r1.json()
    except:
        log(f"  step1 not JSON")
        return None
    
    if "errors" in data1:
        for e in data1["errors"]:
            log(f"  GraphQL error: {e.get('message','')}")
        return None
    
    access_token = data1.get("data", {}).get("getDetailPageContent", {}).get("access_token")
    if not access_token:
        log("  no access_token")
        return None
    
    log(f"  access_token: {access_token[:20]}...")
    
    # Step 2: Complete detail page content (get TARGET/post_token)
    payload2 = {
        "operationName": "completeDetailPageContent",
        "variables": {
            "linkIdentificationInput": {
                "userIdAndUrl": {
                    "user_id": user_id,
                    "url": post_id
                }
            },
            "completeDetailPageContentInput": {
                "access_token": access_token
            }
        },
        "query": CDPC_QUERY
    }
    
    r2 = lv_sess.post(LV_GRAPHQL, json=payload2, headers=LV_HEADERS, timeout=15)
    log(f"step2 [{r2.status_code}]: {r2.text[:120]}")
    
    if r2.status_code != 200:
        return None
    
    try:
        data2 = r2.json()
    except:
        return None
    
    post_token = data2.get("data", {}).get("completeDetailPageContent", {}).get("TARGET")
    if not post_token:
        log("  no TARGET")
        return None
    
    log(f"  post_token: {post_token[:20]}...")
    
    # Step 3: Get detail page target (final URL)
    payload3 = {
        "operationName": "getDetailPageTarget",
        "variables": {
            "linkIdentificationInput": {
                "userIdAndUrl": {
                    "user_id": user_id,
                    "url": post_id
                }
            },
            "token": post_token
        },
        "query": GDPT_QUERY
    }
    
    r3 = lv_sess.post(LV_GRAPHQL, json=payload3, headers=LV_HEADERS, timeout=15)
    log(f"step3 [{r3.status_code}]: {r3.text[:120]}")
    
    if r3.status_code != 200:
        return None
    
    try:
        data3 = r3.json()
    except:
        return None
    
    target_url = data3.get("data", {}).get("getDetailPageTarget", {}).get("url")
    return target_url

def verify(verify_url):
    """Hit latvi verify URL to claim credits"""
    try:
        path = verify_url.replace(BASE, "")
        rv = direct_get(path)
        log(f"verify [{rv.status_code}]")
        if rv.status_code == 200:
            return True
        return False
    except Exception as e:
        log(f"verify error: {str(e)[:60]}")
        return False

def main():
    log("🚀 latvi (GraphQL bypass)")
    
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
        uid, pid, vurl = get_campaign()
        if not uid:
            log("❌ no campaign found")
            break
        log(f"campaign: {uid}/{pid}")
        
        # Try GraphQL bypass first
        target = bypass_linkvertise(uid, pid)
        
        # If bypass gave us a URL, use it; otherwise use the verify URL from generate
        if target and target.startswith("http"):
            log(f"bypass URL: {target[:60]}...")
            # The bypass URL might be the same as verify URL, or different
            if "verify" in target:
                if verify(target):
                    ok += 1
            else:
                # Visit the bypass URL, which should redirect to latvi verify
                try:
                    r = sess.get(target, timeout=15, allow_redirects=True)
                    log(f"follow [{r.status_code}] → {r.url[:60]}")
                    if "verify" in r.url:
                        ok += 1
                except:
                    pass
        elif vurl:
            # Fallback: try direct verify
            if verify(vurl):
                ok += 1
        else:
            log("❌ no URL to verify")
        
        time.sleep(3)
    
    b1 = balance()
    log(f"done: {ok} ok, {b0}→{b1} (+{b1-b0})")

if __name__ == "__main__":
    main()
