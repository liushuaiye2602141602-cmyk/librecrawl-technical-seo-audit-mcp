"""Run SEO audit against the local MCP server (bypasses proxy)."""
import httpx
import json
import base64
import time
import sys
import os

# CRITICAL: bypass Windows system proxy for localhost
os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ["no_proxy"] = "127.0.0.1,localhost"

MCP_URL = "http://127.0.0.1:5081/mcp"
HEADERS = {"Accept": "application/json, text/event-stream"}
TARGET = sys.argv[1] if len(sys.argv) > 1 else "https://baolaipackaging.com"

# Use trust_env=False to bypass system proxy
client = httpx.Client(timeout=300, trust_env=False)

# 1. Initialize
print("→ Initializing MCP session...")
resp = client.post(MCP_URL, json={
    "jsonrpc": "2.0", "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "claude-code", "version": "1.0"}
    },
    "id": 1
}, headers=HEADERS)
session_id = resp.headers.get("mcp-session-id", "")
print(f"  Status: {resp.status_code}, Session: {session_id[:30]}...")

if not session_id:
    print(f"  ERROR: No session ID. Headers: {dict(resp.headers)}")
    sys.exit(1)

H = {**HEADERS, "Mcp-Session-Id": session_id}

# 2. Initialized notification
resp = client.post(MCP_URL, json={
    "jsonrpc": "2.0", "method": "notifications/initialized"
}, headers=H)
print(f"  Initialized: {resp.status_code}")

# 3. Start audit
print(f"\n→ Starting audit for {TARGET}...")
resp = client.post(MCP_URL, json={
    "jsonrpc": "2.0", "method": "tools/call",
    "params": {"name": "librecrawl_start_chunked_audit",
               "arguments": {"url": TARGET}},
    "id": 2
}, headers=H)
print(f"  Status: {resp.status_code}")

# Parse SSE
audit_sid = None
for line in resp.text.split("\n"):
    if line.startswith("data:"):
        data = json.loads(line[5:].strip())
        if "result" in data and "content" in data["result"]:
            for c in data["result"]["content"]:
                if c["type"] == "text":
                    info = json.loads(c["text"])
                    audit_sid = info.get("session_id")
                    print(f"  Audit session: {audit_sid}")
                    print(f"  Status: {info.get('status')}")
                    msg = info.get('message', '')
                    if msg:
                        print(f"  Message: {msg[:300]}")
        elif "error" in data:
            print(f"  ERROR: {json.dumps(data['error'], indent=2)}")

if not audit_sid:
    print(f"  FAILED. Raw response: {resp.text[:500]}")
    sys.exit(1)

# 4. Poll until done
print("\n→ Polling status (every 25s)...")
while True:
    time.sleep(25)
    resp = client.post(MCP_URL, json={
        "jsonrpc": "2.0", "method": "tools/call",
        "params": {"name": "librecrawl_audit_status",
                   "arguments": {"session_id": audit_sid}},
        "id": 3
    }, headers=H)

    for line in resp.text.split("\n"):
        if line.startswith("data:"):
            data = json.loads(line[5:].strip())
            if "result" in data and "content" in data["result"]:
                for c in data["result"]["content"]:
                    if c["type"] == "text":
                        info = json.loads(c["text"])
                        s = info.get("status", "?")
                        p = info.get("pages_done", 0)
                        t = info.get("total_pages", "?")
                        p95 = info.get("p95_latency_ms", 0)
                        e = info.get("current_error_rate", 0)
                        print(f"  [{s}] Pages: {p}/{t} | p95: {p95}ms | err: {e}%")

                        if s == "done" or info.get("artifacts_ready"):
                            print("\n✅ Crawl complete! Downloading zip...")
                            resp2 = client.post(MCP_URL, json={
                                "jsonrpc": "2.0", "method": "tools/call",
                                "params": {"name": "librecrawl_audit_zip",
                                           "arguments": {"session_id": audit_sid, "auto_cleanup": True}},
                                "id": 4
                            }, headers=H, timeout=300)

                            for line2 in resp2.text.split("\n"):
                                if line2.startswith("data:"):
                                    r2 = json.loads(line2[5:].strip())
                                    if "result" in r2 and "content" in r2["result"]:
                                        for c2 in r2["result"]["content"]:
                                            if c2["type"] == "text":
                                                z = json.loads(c2["text"])
                                                b64 = z.get("content_base64", "")
                                                fname = z.get("filename", "audit.zip")
                                                if b64:
                                                    raw = base64.b64decode(b64)
                                                    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports", fname)
                                                    os.makedirs(os.path.dirname(out), exist_ok=True)
                                                    with open(out, "wb") as f:
                                                        f.write(raw)
                                                    print(f"  ✅ Saved: reports/{fname} ({len(raw)/1024:.0f} KB)")
                                                    print(f"  Server wiped. Done!")
                            sys.exit(0)
