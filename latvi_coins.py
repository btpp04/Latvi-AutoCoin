#!/usr/bin/env python3
"""
latvi.space Auto Coin — 每日领币模式 (linkvertise 已确认无法脚本化, 移除)
每天领 daily reward (+5 credits), 报告余额.

环境变量:
  LATVI_EMAIL
  LATVI_PASSWORD
  PROXY         (可选, socks5/http, 走代理访问; 不传则直连)
  TG_BOT_TOKEN (可选)
  TG_CHAT_ID   (可选)
"""

import os, re, time, logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("latvi")

BASE = "https://dash.latvi.space"
EMAIL = os.environ.get("LATVI_EMAIL", "btpp03@gmail.com")
PASSWORD = os.environ.get("LATVI_PASSWORD", "Hlm@0649")
PROXY = os.environ.get("PROXY", "").strip()

import requests
sess = requests.Session()
sess.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"})

# Proxy setup
use_proxy = None
proxy_type = "none"
if PROXY:
    if PROXY.startswith("socks5://"):
        try:
            import socks  # noqa
            use_proxy = PROXY
            proxy_type = "SOCKS5 direct"
        except ImportError:
            log.warning("PySocks missing, SOCKS proxy disabled")
    elif PROXY.startswith("http://") or PROXY.startswith("https://"):
        use_proxy = PROXY
        proxy_type = "HTTP direct"
if use_proxy:
    sess.proxies.update({"http": use_proxy, "https": use_proxy})
    log.info(f"Proxy: {proxy_type} ✅")


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
    m = re.search(r'(\d+[.,]?\d*)\s*credit', html)
    if m:
        return float(m.group(1).replace(",", ""))
    m = re.search(r'>\s*(\d+[.,]\d+)\s*<', html)
    if m:
        return float(m.group(1).replace(",", ""))
    m = re.search(r'balance[^<]*?(\d+[.,]?\d*)', html)
    if m:
        return float(m.group(1).replace(",", ""))
    return 0


def daily_reward():
    """Claim daily reward (+5). Returns True if claimed, False if not yet available."""
    try:
        r = sess.get(f"{BASE}/daily-rewards", timeout=15)
        m = re.search(r'name="_token"[^>]*value="([^"]*)"', r.text)
        token = m.group(1) if m else None
        if not token:
            log.warning("No CSRF token for daily reward")
            return False

        streak = re.search(r'id="streakCount"[^>]*>(\d+)<', r.text)
        timer = re.search(r'let secondsRemaining = (\d+)', r.text)
        if timer:
            secs = int(timer.group(1))
            if secs > 0:
                h, mnt = divmod(secs, 3600)
                log.info(f"Daily reward: 下次可领 {h}h {mnt//60}m (streak: {streak.group(1) if streak else '?'})")
                return False

        log.info(f"Daily reward: 领取中 (streak: {streak.group(1) if streak else '?'})...")
        headers = {
            "Content-Type": "application/json",
            "X-CSRF-TOKEN": token,
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{BASE}/daily-rewards",
        }
        r2 = sess.post(f"{BASE}/daily-rewards/claim", json={}, headers=headers, timeout=15)
        try:
            data = r2.json()
            log.info(f"  ✅ {data.get('message', data.get('reward', str(data)))}")
        except Exception:
            log.info(f"  ✅ claim 响应: {r2.status_code}")
        return True
    except Exception as e:
        log.warning(f"Daily reward: {e}")
        return False


def send_tg(msg: str):
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


def main():
    log.info("=== Latvi Auto Coin (每日领币模式) ===")
    if not login():
        return
    bal = get_balance()
    log.info(f"余额: {bal}")
    reward_ok = daily_reward()
    bal2 = get_balance()
    repo = os.environ.get("GITHUB_REPOSITORY", "btpp04/Latvi-AutoCoin")
    msg = (
        f"<b>🏝 Latvi 签到</b>\n"
        f"<b>📦 Repo:</b> {repo}\n"
        f"<b>💰 余额:</b> {bal2} Credits\n"
        f"<b>🪙 每日领币:</b> {'✅ 已领取' if reward_ok else '⏳ 未到时间/已领'}\n"
    )
    log.info(msg)
    send_tg(msg)
    log.info(f"=== Done | {bal} → {bal2} ===")


if __name__ == "__main__":
    main()
