#!/usr/bin/env python3
"""
latvi.space Auto Coin — Pure requests + GOST tunnel (losy approach)
通过 GOST 隧道保持单 IP 访问完整短链流程
"""
import os, sys, re, json, time, base64, logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("latvi")

BASE = "https://dash.latvi.space"
EMAIL = os.environ.get("LATVI_EMAIL", "btpp03@gmail.com")
PASSWORD = os.environ.get("LATVI_PASSWORD", "Hlm@0649")
MAX_CLAIMS = int(os.environ.get("MAX_CLAIMS", "20"))
PROXY = os.environ.get("PROXY", "").strip()

import requests
sess = requests.Session()

# Proxy priority: SOCKS5 direct > GOST tunnel > none
use_proxy = None
proxy_type = "none"

if PROXY:
    # Always try GOST tunnel first (keeps IP consistent)
    try:
        r = requests.get("http://127.0.0.1:8080", timeout=2)
        use_proxy = "http://127.0.0.1:8080"
        proxy_type = "GOST tunnel"
    except:
        use_proxy = PROXY
        proxy_type = "HTTP direct"

if use_proxy:
    # Test if proxy actually works
    try:
        r = requests.get("https://dash.latvi.space/login", proxies={"http": use_proxy, "https": use_proxy}, timeout=10)
        if r.status_code == 200:
            sess.proxies.update({"http": use_proxy, "https": use_proxy})
            log.info(f"Proxy: {proxy_type} ✅")
        else:
            log.warning(f"Proxy {proxy_type} returned HTTP {r.status_code}, falling back to direct")
            use_proxy = None
    except Exception as e:
        log.warning(f"Proxy {proxy_type} failed ({e}), falling back to direct")
        use_proxy = None

sess.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"})


def login():
    r = sess.get(f"{BASE}/login", timeout=15)
    m = re.search(r'name="_token"[^>]*value="([^"]*)"', r.text)
    token = m.group(1) if m else None
    r2 = sess.post(f"{BASE}/login", data={"email": EMAIL, "password": PASSWORD, "_token": token or ""}, timeout=15)
    ok = "/home" in r2.url or "logout" in r2.text.lower()
    log.info(f"{'✅' if ok else '❌'} Login ({r2.status_code})")
    return ok


def get_balance():
    r = sess.get(f"{BASE}/home", timeout=15)
    html = r.text.lower()
    # Try: number near "credit" or "credits"
    m = re.search(r'(\d+[.,]?\d*)\s*credit', html)
    if m: return float(m.group(1).replace(",", ""))
    # Try: standalone number in nav/balance area
    m = re.search(r'>\s*(\d+[.,]\d+)\s*<', html)
    if m: return float(m.group(1).replace(",", ""))
    # Try: number after "balance" text  
    m = re.search(r'balance[^<]*?(\d+[.,]?\d*)', html)
    if m: return float(m.group(1).replace(",", ""))
    return 0


def get_cooldown():
    r = sess.get(f"{BASE}/linkvertise", timeout=15)
    m = re.search(r'Claims Today:\s*(\d+)\s*/\s*(\d+)', r.text)
    if m:
        rem = int(m.group(2)) - int(m.group(1))
        log.info(f"Claims: {m.group(1)}/{m.group(2)} ({rem} left)")
        return rem
    return MAX_CLAIMS


def generate():
    """Get shortlink and extract verify URL."""
    r = sess.get(f"{BASE}/linkvertise/generate", timeout=15)
    if r.status_code != 200:
        return None, None

    link_url, verify_url = None, None

    # Extract link URL
    for p in [r'(https?://link-to\.net/[^\s"\'<>]+)',
              r'(https?://linkvertise\.com/[^\s"\'<>]+)',
              r'href="([^"]*link[^"]*)"',
              r'"url":\s*"([^"]+)"']:
        ms = re.findall(p, r.text)
        for u in ms:
            u = u.rstrip("';,\"")
            if "link-to.net" in u or "linkvertise.com" in u:
                link_url = u
                break
        if link_url:
            break

    # Extract verify URL from r= param (base64)
    m = re.search(r'r=([A-Za-z0-9+/=]+)', link_url or "")
    if m:
        try:
            decoded = base64.b64decode(m.group(1)).decode()
            verify_url = decoded
        except:
            pass

    return link_url, verify_url


def claim(link_url, verify_url):
    """Follow redirect chain and attempt verify."""
    try:
        # 1. link-to.net → redirect to linkvertise
        r = sess.get(link_url, timeout=30, allow_redirects=False)
        if r.status_code not in (301, 302, 303, 307, 308):
            log.warning(f"link-to.net: HTTP {r.status_code} (not a redirect)")
            return False

        target = r.headers.get("Location", "")
        log.info(f"→ {target[:60]}")

        # 2. Visit linkvertise page
        r2 = sess.get(target, timeout=30, allow_redirects=True)
        log.info(f"linkvertise: HTTP {r2.status_code} | {len(r2.content)}b")

        if r2.status_code != 200:
            return False

        # 3. Wait briefly for any async redirect
        time.sleep(3)

        # 4. Try to find redirect URL from the page
        body = r2.text
        redirect_url = None

        # Common JS/link redirect patterns
        for pat in [r'window\.location(?:\.href)?\s*=\s*["\']([^"\']+)',
                    r'location\.href\s*=\s*["\']([^"\']+)',
                    r'<meta[^>]*url=([^"\'>\s]+)',
                    r'href="([^"]*verify[^"]*)"',
                    r'success_url["\']:\s*["\']([^"\']+)',
                    r'"redirect":\s*"([^"]+)"',
                    r'"link":\s*"([^"]+)"',
                    r'"url":\s*"([^"]+)"',
                    r'document\.location\s*=\s*["\']([^"\']+)']:
            m = re.search(pat, body, re.I)
            if m:
                t = m.group(1).replace("\\/", "/")
                # Decode any HTML entities
                t = t.replace("&amp;", "&").replace("&#x2F;", "/")
                if "latvi" in t.lower() or "verify" in t.lower() or "success" in t.lower():
                    redirect_url = t
                    log.info(f"Redirect found: {t[:60]}")
                    break

        # 5. Call verify URL (either found redirect or the r= param version)
        call_url = redirect_url or verify_url
        if not call_url:
            log.warning("No verify URL available")
            return False

        r3 = sess.get(call_url, timeout=30, allow_redirects=True)
        log.info(f"Verify: HTTP {r3.status_code} | {r3.url[:60]}")
        body3 = r3.text.lower()

        if r3.status_code == 200:
            if "success" in body3 or "coin" in body3:
                log.info("✅ +1 coin!")
                return True
            elif "already" in body3:
                log.info("⏭ Already claimed")
                return True
            elif "invalid" in body3:
                log.warning("Invalid verify")
                return False
            else:
                log.info(f"Response: {r3.text[:150]}")
                return True  # Might still have worked
        else:
            log.warning(f"Verify: HTTP {r3.status_code}")
            return False

    except Exception as e:
        log.error(f"Error: {str(e)[:100]}")
        return False


def send_tg(msg: str):
    """Send Telegram notification."""
    bot_token = os.environ.get("TG_BOT_TOKEN", "")
    chat_id = os.environ.get("TG_CHAT_ID", "")
    if not bot_token or not chat_id:
        log.info("TG notification skipped (no bot token/chat ID)")
        return
    try:
        r = requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}, timeout=15)
        log.info(f"TG sent ({r.status_code})")
    except Exception as e:
        log.warning(f"TG failed: {e}")

def daily_reward():
    """Claim daily reward (works without linkvertise)."""
    try:
        # Get fresh CSRF token from daily-rewards page
        r = sess.get(f"{BASE}/daily-rewards", timeout=15)
        m = re.search(r'name="_token"[^>]*value="([^"]*)"', r.text)
        token = m.group(1) if m else None
        if not token:
            log.warning("No CSRF token for daily reward")
            return False

        # Check streak info
        streak = re.search(r'id="streakCount"[^>]*>(\d+)<', r.text)
        timer = re.search(r'let secondsRemaining = (\d+)', r.text)
        if timer:
            secs = int(timer.group(1))
            if secs > 0:
                log.info(f"Daily reward: next in {secs//3600}h {(secs%3600)//60}m (streak: {streak.group(1) if streak else '?'})")
                return False

        log.info(f"Daily reward: claiming (streak: {streak.group(1) if streak else '?'})...")
        headers = {
            "Content-Type": "application/json",
            "X-CSRF-TOKEN": token,
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{BASE}/daily-rewards",
        }
        r2 = sess.post(f"{BASE}/daily-rewards/claim", json={}, headers=headers, timeout=15)
        data = r2.json()
        log.info(f"  ✅ {data.get('message', data.get('reward', str(data)))}")
        return True
    except Exception as e:
        log.warning(f"Daily reward: {e}")
        return False

def main():
    log.info("=== Latvi Auto Coin ===")

    if not login():
        return

    bal = get_balance()
    log.info(f"Balance: {bal}")

    # Save balance for TG notification
    bal = get_balance()
    with open("/tmp/latvi_balance.txt", "w") as f:
        f.write(f"{bal}")

    # Step 1: Daily reward (works through proxy, no linkvertise)
    reward_ok = daily_reward()
    bal_now = get_balance()
    tg_msg = (
        f"<b>🏝 Latvi 签到</b>\n"
        f"<b>Repo:</b> btpp04/Latvi-AutoCoin\n"
        f"<b>余额:</b> {bal_now} Credits\n"
    )
    send_tg(tg_msg)

    # Step 2: Linkvertise coins (needs clean IP, skip when no proxy)
    if not use_proxy:
        log.info("No proxy available, skipping linkvertise coins")
        bal2 = get_balance()
        send_tg(f"<b>🏝 Latvi 签到</b>\n<b>Repo:</b> btpp04/Latvi-AutoCoin\n<b>余额:</b> {bal2} Credits\n(linkvertise 跳过 - 代理不可用)")
        with open("/tmp/latvi_balance.txt", "w") as f:
            f.write(f"{bal2}")
        print(f"=== Done: proxy off | {bal} -> {bal2} ===")
        return
    remaining = get_cooldown()
    if remaining <= 0:
        log.info("No linkvertise claims left today")
        bal2 = get_balance()
        with open("/tmp/latvi_balance.txt", "w") as f:
            f.write(f"{bal2}")
        log.info(f"=== Done | {bal} → {bal2} ===")
        return

    success = 0
    for i in range(min(remaining, MAX_CLAIMS)):
        log.info(f"--- #{i+1} ---")
        link_url, verify_url = generate()
        if not link_url:
            log.warning("No link generated")
            time.sleep(5)
            continue

        if claim(link_url, verify_url):
            success += 1
            time.sleep(3)
        else:
            time.sleep(10)

    bal2 = get_balance()
    with open("/tmp/latvi_balance.txt", "w") as f:
        f.write(f"{bal2}")
    log.info(f"=== Done: {success}/{min(remaining, MAX_CLAIMS)} | {bal} → {bal2} ===")


if __name__ == "__main__":
    main()
