#!/usr/bin/env python3
"""Get raw HTML"""
import requests

r = requests.get("https://linkvertise.com/1151676/262/dynamic?r=test&o=sharing", 
    headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
print(f"Status: {r.status_code}")
print(f"Headers: {dict(r.headers)}")
print(f"\n=== Full HTML ({len(r.text)} chars) ===")
print(r.text[:3000])
