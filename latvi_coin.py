#!/usr/bin/env python3
"""latvi.space Auto Coin — full linkvertise task chain"""
import re, os, sys, json, time, base64, requests, urllib.parse
from datetime import datetime

BASE = "https://dash.latvi.space"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
EMAIL = os.environ.get("LATVI_EMAIL", "btpp03@gmail.com")
PASSWORD = os.environ.get("LATVI_PASSWORD", "Hlm@0649")
MAX_CLAIMS = int(os.environ.get("MAX_CLAIMS", "20"))
WAIT_TASK_SEC = int(os.environ.get("WAIT_TASK_SEC", "2"))

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

sess = requests.Session()
sess.headers.update({
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
})

# ─── auth ────────────────────────────────
def login():
    r = sess.get(f"{BASE}/login")
    m = re.search(r'name="_token"\s+value="([^"]+)"', r.text)
    token = m.group(1) if m else ""
    r2 = sess.post(f"{BASE}/login", data={
        "_token": token, "email": EMAIL, "password": PASSWORD, "remember": "on"
    }, allow_redirects=False)
    if "/home" not in (r2.headers.get("Location", "")):
        raise RuntimeError(f"Login failed")
    sess.get(f"{BASE}/home")
    log("login OK")

# ─── daily reward ────────────────────────
def daily():
    r = sess.get(f"{BASE}/daily-rewards")
    m = re.search(r'name="_token"\s+value="([^"]+)"', r.text)
    token = m.group(1) if m else ""
    r2 = sess.post(f"{BASE}/daily-rewards/claim", data={"_token": token},
                    headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"})
    try:
        d = r2.json()
        if d.get("success"):
            log(f"daily ✅ {d.get('message','')}")
            return True
    except:
        pass
    if "already" in r2.text.lower():
        log("daily ⏰ already claimed")
        return True
    return False

# ─── cooldown ────────────────────────────
def cooldown():
    r = sess.get(f"{BASE}/linkvertise")
    for pat in [r'Claims Today:\s*(\d+)\s*/\s*(\d+)', r'(\d+)\s*/\s*20']:
        m = re.search(pat, r.text)
        if m:
            g = m.groups()
            if len(g) == 2:
                done, max_ = int(g[0]), int(g[1])
                rem = max_ - done
                log(f"progress {done}/{max_} ({rem} left)")
                return rem
            done = int(g[0])
            rem = max(0, 20 - done)
            log(f"progress {done}/20 ({rem} left)")
            return rem
    clean = re.sub(r'<[^>]+>', ' ', r.text).strip()
    log(f"progress no match: {clean[:150]}")
    return MAX_CLAIMS

# ─── generate ────────────────────────────
def generate():
    r = sess.get(f"{BASE}/linkvertise/generate")
    m = re.search(r'https://link-to\.net[^"\']*', r.text)
    if not m:
        if "limit" in r.text.lower():
            return "LIMIT", None, None
        log(f"gen no link: {r.text[:100]}")
        return None, None, None
    link_url = m.group(0).replace("';", "")
    # Decode b64 r param
    rm = re.search(r'[?&]r=([^&\s]+)', link_url)
    if rm:
        rp = urllib.parse.unquote(rm.group(1)).replace("-","+").replace("_","/")
        pad = (4 - len(rp) % 4) % 4
        try:
            vu = base64.b64decode(rp + "=" * pad).decode()
            return link_url, vu, link_url
        except:
            pass
    return link_url, None, link_url

# ─── linkvertise task chain ──────────────
def run_linkvertise_chain(link_url, verify_url):
    """
    Simulate the full linkvertise task chain:
    1. GET link-to.net → get wait task
    2. GET linkvertise content → handle WaitTask, AdTask
    3. Extract DetailPageTargetData → get real verify URL
    4. Visit verify URL → get credited
    """
    try:
        # Step 1: Visit link-to.net → follow redirect to linkvertise
        log(f"GET link-to.net...")
        r1 = sess.get(link_url, allow_redirects=True, timeout=30)
        final = r1.url
        
        if "linkvertise" not in final:
            log(f"Not on linkvertise: {final[:60]}")
            return False
        
        # Step 2: getContent - extract from the page
        # The page has embedded JSON data with task info
        data = extract_page_data(r1.text)
        if not data:
            log("No page data found on linkvertise")
            return False
        
        # Step 3: Process task chain
        tasks = data.get("tasks", {})
        log(f"tasks: {json.dumps(tasks)[:80]}...")
        
        # Handle wait task
        if "WaitTask" in str(tasks):
            log("⚡ WaitTask - completing...")
            sess.get(final, timeout=15)  # Refresh to progress
            time.sleep(WAIT_TASK_SEC)
            r2 = sess.get(final, timeout=15)
            data2 = extract_page_data(r2.text)
            if data2:
                log(f"after wait: {json.dumps(data2.get('tasks',{}))[:80]}")
        
        # Handle ad tasks (multiple rounds)
        for ad_round in range(10):
            r3 = sess.get(final, timeout=15)
            data3 = extract_page_data(r3.text)
            if not data3:
                break
            
            tasks3 = data3.get("tasks", {})
            log(f"round {ad_round+1}: tasks={json.dumps(tasks3)[:80]}")
            
            # Check if we got the verify URL
            dptd = data3.get("DetailPageTargetData") or data3.get("detailPageTargetData")
            if dptd:
                log(f"✅ DetailPageTargetData found!")
                return visit_verify(dptd, verify_url)
            
            # Check for AdTask
            if "AdTask" in str(tasks3):
                # Complete ad task by visiting
                log(f"🎬 ad {ad_round+1}")
                time.sleep(2)
                continue
            elif "WaitTask" in str(tasks3):
                log("WaitTask still pending, waiting...")
                time.sleep(WAIT_TASK_SEC)
                continue
            else:
                # No more tasks to process, try refreshing
                log("No tasks to process")
                break
        
        # Fallback: try direct verify
        log("Task chain exhausted, trying direct verify")
        return visit_verify(None, verify_url)
        
    except Exception as e:
        log(f"chain error: {e}")
        return False

def extract_page_data(html):
    """Extract JSON data from linkvertise page"""
    # Try various data formats
    for pat in [
        r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
        r'window\.__DATA__\s*=\s*({.*?});',
        r'window\.__LINKVERTISE_DATA__\s*=\s*({.*?});',
        r'<script[^>]*id="__NEXT_DATA__"[^>]*>({.*?})</script>',
        r'data\s*=\s*({.*?tasks.*?});',
        r'<div[^>]*id="data"[^>]*>({.*?})</div>',
        r'pageData\s*=\s*({.*?});',
    ]:
        m = re.search(pat, html, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except:
                pass
    
    # Try to find any JSON blob with tasks
    for m in re.finditer(r'({[^}]*"tasks"[^}]*})', html):
        try:
            return json.loads(m.group(1))
        except:
            continue
    
    # Last resort: look for DetailPageTargetData URL pattern
    m = re.search(r'https://dash\.latvi\.space/linkvertise/verify/\d+[^"\'<\s]*', html)
    if m:
        return {"DetailPageTargetData": m.group(0)}
    
    return None

def visit_verify(dptd_url, fallback_url):
    """Visit the verify URL on latvi.space"""
    url = dptd_url or fallback_url
    if not url:
        log("No verify URL")
        return False
    
    if not url.startswith("https://dash.latvi.space"):
        log(f"verify URL not on latvi: {url[:60]}")
        return False
    
    log(f"verify: {url[:70]}...")
    r = sess.get(url, headers={"Referer": "https://linkvertise.com/"}, 
                  allow_redirects=True, timeout=15)
    
    if r.status_code == 200:
        log(f"verify ✅ HTTP 200")
        return True
    elif r.status_code == 403:
        log(f"verify ❌ 403")
        return False
    else:
        log(f"verify HTTP {r.status_code}")
        return r.status_code == 200

# ─── balance ─────────────────────────────
def balance():
    r = sess.get(f"{BASE}/home")
    m = re.search(r'([\d.]+)\s*(?:credit|coin)', r.text, re.I)
    return float(m.group(1)) if m else 0.0

# ─── main ────────────────────────────────
def main():
    log("🚀 latvi auto coin (full chain)")
    login()
    
    daily()
    
    rem = cooldown()
    if rem <= 0:
        log("🎉 done for today")
        return
    
    b0 = balance()
    log(f"balance {b0}")
    
    ok_cnt = 0
    for i in range(min(rem, MAX_CLAIMS)):
        log(f"--- #{i+1} ---")
        link, verify, _ = generate()
        if not link or link == "LIMIT":
            break
        
        if run_linkvertise_chain(link, verify):
            ok_cnt += 1
        else:
            log("earn failed")
            break
        
        time.sleep(3)
    
    b1 = balance()
    log(f"done {ok_cnt} ok {b0} → {b1} (+{b1-b0})")

if __name__ == "__main__":
    main()
