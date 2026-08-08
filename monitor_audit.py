"""Monitor an existing SEO audit session and download results when done."""
import httpx
import json
import base64
import time
import sys
import os

os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ["no_proxy"] = "127.0.0.1,localhost"

MCP_URL = "http://127.0.0.1:5081/mcp"
HEADERS = {"Accept": "application/json, text/event-stream"}
AUDIT_SID = sys.argv[1] if len(sys.argv) > 1 else "0c60a66f7fc743b3"
OUT_DIR = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")

client = httpx.Client(timeout=300, trust_env=False)

# Initialize
print("Connecting to MCP...")
resp = client.post(MCP_URL, json={
    "jsonrpc": "2.0", "method": "initialize",
    "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "claude-code", "version": "1.0"}},
    "id": 1
}, headers=HEADERS)
session_id = resp.headers.get("mcp-session-id", "")
print(f"  MCP session: {session_id[:20]}...")
H = {**HEADERS, "Mcp-Session-Id": session_id}

resp = client.post(MCP_URL, json={"jsonrpc": "2.0", "method": "notifications/initialized"}, headers=H)

# Monitor
print(f"\nMonitoring audit session: {AUDIT_SID}")
print(f"  (polling every 25s)...\n")

while True:
    time.sleep(25)
    resp = client.post(MCP_URL, json={
        "jsonrpc": "2.0", "method": "tools/call",
        "params": {"name": "librecrawl_audit_status", "arguments": {"session_id": AUDIT_SID}},
        "id": 2
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
                        t = info.get("total_max_pages", "?")
                        p95 = info.get("p95_latency_ms", 0) or 0
                        e = info.get("current_error_rate", 0) or 0
                        art = " READY" if info.get("artifacts_ready") else ""
                        print(f"  [{s:10s}] Pages: {p}/{t} | p95: {p95}ms | err: {e:.1%}{art}")

                        if s == "done" or info.get("artifacts_ready"):
                            print("\nAudit complete! Downloading zip...")
                            resp2 = client.post(MCP_URL, json={
                                "jsonrpc": "2.0", "method": "tools/call",
                                "params": {"name": "librecrawl_audit_zip",
                                           "arguments": {"session_id": AUDIT_SID, "auto_cleanup": True}},
                                "id": 3
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
                                                    os.makedirs(OUT_DIR, exist_ok=True)
                                                    out = os.path.join(OUT_DIR, fname)
                                                    with open(out, "wb") as f:
                                                        f.write(raw)
                                                    print(f"  Saved: {out} ({len(raw)/1024:.0f} KB)")
                                                    print(f"  Server wiped. Done!")
                                                else:
                                                    print("  WARNING: No base64 data in response")
                            sys.exit(0)
            elif "error" in data:
                print(f"  ERROR: {json.dumps(data['error'])[:200]}")
