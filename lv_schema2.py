#!/usr/bin/env python3
"""Deep schema introspection"""
import requests, json

LV = "https://publisher.linkvertise.com/graphql"
H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Origin": "https://linkvertise.com",
    "Referer": "https://linkvertise.com",
    "Content-Type": "application/json",
}

# Get PublicLinkIdentificationInput fields + getContent return type + mutations
q = """
{
  inputType: __type(name: "PublicLinkIdentificationInput") {
    inputFields { name type { name kind ofType { name kind } } }
  }
  contentType: __type(name: "getContentResult") {
    fields { name type { name kind ofType { name kind } } }
  }
  taskArg: __type(name: "TaskArgument") {
    inputFields { name type { name kind ofType { name kind } } }
  }
  mutations: __schema {
    mutationType { fields { name args { name type { name kind ofType { name kind } } } } }
  }
  completeType: __type(name: "completeContentResult") {
    fields { name type { name kind ofType { name kind } } }
  }
}
"""

r = requests.post(LV, json={"query": q}, headers=H, timeout=15)
print(f"Status: {r.status_code}")
try:
    d = r.json()
    print(json.dumps(d, indent=2))
except:
    print(r.text[:3000])
