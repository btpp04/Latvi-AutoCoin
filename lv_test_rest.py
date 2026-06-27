#!/usr/bin/env python3
"""Test REST API + check if CF blocks from GitHub Actions"""
import requests, json

H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Origin": "https://linkvertise.com",
    "Referer": "https://linkvertise.com",
}

# Test 1: REST API v1
print("=== REST API v1 ===")
r = requests.get("https://linkvertise.com/api/v1/getContent?campaign=1151676", headers=H, timeout=10)
print(f"Status: {r.status_code}")
print(f"Content-Type: {r.headers.get('content-type','')}")
print(r.text[:300])

# Test 2: REST API v1 with specific path  
print("\n=== REST API v1 (user/post) ===")
r2 = requests.get("https://linkvertise.com/api/v1/getContent/1151676/262", headers=H, timeout=10)
print(f"Status: {r2.status_code}")
print(r2.text[:300])

# Test 3: Check publisher.linkvertise.com
print("\n=== Publisher GraphQL ===")
r3 = requests.post("https://publisher.linkvertise.com/graphql", 
    json={"query": '{ getContent(input: {userIdAndUrl: {user_id: "1151676", url: "262"}}) { __typename } }'},
    headers={**H, "Content-Type": "application/json"}, timeout=10)
print(f"Status: {r3.status_code}")
print(r3.text[:300])

# Test 4: link-to.net redirect
print("\n=== link-to.net ===")
r4 = requests.get("https://link-to.net/1151676/262/dynamic?r=test", headers=H, timeout=10, allow_redirects=False)
print(f"Status: {r4.status_code}")
print(f"Location: {r4.headers.get('location','')}")
