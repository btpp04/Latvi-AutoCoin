#!/usr/bin/env python3
"""Schema v5 - final details + real call"""
import requests, json

LV = "https://publisher.linkvertise.com/graphql"
H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Origin": "https://linkvertise.com",
    "Referer": "https://linkvertise.com",
    "Content-Type": "application/json",
}

queries = {
    "TaskSet": '{ __type(name: "ContentAccessTaskSet") { fields { name type { name kind ofType { name kind } } } } }',
    "DetailTarget": '{ __type(name: "DetailPageTargetData") { fields { name type { name kind ofType { name kind } } } } }',
    "TaskTypeDef": '{ __type(name: "TaskDefinition") { fields { name type { name kind ofType { name kind } } } } }',
    "TaskType": '{ __type(name: "Task") { fields { name type { name kind ofType { name kind } } } } }',
    "realCall": """query { getContent(input: {userIdAndUrl: {user_id: "1151676", url: "782"}}, origin: "sharing") { __typename ... on ContentAccessTaskSet { __typename } ... on DetailPageTargetData { url } } }""",
    "realCall2": """query { getContent(input: {userIdAndUrl: {user_id: "1151676", url: "782"}}) { __typename } }""",
}

for name, q in queries.items():
    r = requests.post(LV, json={"query": q}, headers=H, timeout=15)
    try:
        d = r.json()
        print(f"\n=== {name} ({r.status_code}) ===")
        print(json.dumps(d, indent=2)[:1500])
    except:
        print(f"\n=== {name} ({r.status_code}) ===")
        print(r.text[:500])
