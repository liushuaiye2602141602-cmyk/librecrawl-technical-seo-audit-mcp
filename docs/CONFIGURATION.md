# Configuration

Everything is configured through environment variables. All are optional — the defaults work for a standard local setup. Set them via your shell, `docker compose`, or the `env` block of your MCP client config.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `LIBRECRAWL_URL` | `http://127.0.0.1:5080` | Full base URL of the LibreCrawl backend. Set this to reach a backend on another host or container (Docker Compose sets `http://librecrawl:5000`). Takes precedence over `LIBRECRAWL_PORT`. |
| `LIBRECRAWL_PORT` | `5080` | Backend port. Used only to build the default URL when `LIBRECRAWL_URL` is not set. |
| `MCP_HOST` | `127.0.0.1` | Bind address for the HTTP transport. Keep loopback on a shared host; set `0.0.0.0` inside a container (Compose does this). |
| `MCP_PORT` | `5081` | Port the MCP server listens on (HTTP transport). |
| `MCP_TRANSPORT` | `http` | `http` for streamable HTTP (long-lived service), or `stdio` for client-launched processes. |
| `REPORTS_DIR` | `~/librecrawl-reports` | Directory where audit zips are written. Docker mounts this to `./reports`. |
| `LIBRECRAWL_UPSTREAM_DB` | `~/.librecrawl/upstream/users.db` | Path to LibreCrawl's SQLite file, used for orphan-page and cleanup checks. If the file isn't reachable, those specific checks skip gracefully — the core audit is unaffected. |
| `PAGESPEED_API_KEY` | unset | Google PageSpeed Insights API key. Enables the `librecrawl_pagespeed*` tools and raises PSI rate limits (25k/day). |
| `MASTER_AUDIT_V3_ENABLED` | `false` | Master gate for the 80-rule V3 pipeline. |
| `MASTER_AUDIT_GSC_ENABLED` | `true` | Enables the GSC provider when V3 is enabled and credentials are present. |
| `GSC_ACCESS_TOKEN` | unset | Short-lived OAuth 2.0 bearer token with Search Console read-only access. Never use the PageSpeed API key here. |
| `GSC_SITE_URL` | unset | Exact Search Console property: a URL-prefix property including its trailing slash, or `sc-domain:example.com`. |
| `GSC_INSPECTION_LIMIT` | `20` | Deterministic per-audit URL Inspection sample; bounded to 100. |
| `GSC_ANALYTICS_MAX_ROWS` | `50000` | Maximum Search Analytics rows per 28-day window; each API page is bounded to 25,000. |
| `MASTER_AUDIT_SEMRUSH_ENABLED` | `true` | Enables the Semrush provider when V3 and a v4 key are present. |
| `SEMRUSH_API_KEY` | unset | Semrush API v4 key used only in the `Authorization` header. |
| `SEMRUSH_TARGET` | audit hostname | Optional explicit root-domain target. |
| `SEMRUSH_LOST_LINK_LIMIT` | `100` | Lost-link result limit, bounded to 500 to control paid API units. |

## Transports

### HTTP (default)

The server runs a streamable-HTTP endpoint at `http://<MCP_HOST>:<MCP_PORT>/mcp`. Use this when the MCP is a persistent service (Docker, PM2, systemd, a VPS). Clients that speak stdio only (Claude Desktop/Code) connect through `mcp-remote`:

```json
{
  "mcpServers": {
    "librecrawl": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://127.0.0.1:5081/mcp"]
    }
  }
}
```

To expose the endpoint beyond localhost, set `MCP_HOST=0.0.0.0` **and** put it behind a reverse proxy with authentication — the server itself does not add auth.

### stdio

Set `MCP_TRANSPORT=stdio` and let the client launch `server.py` directly. The backend URL still comes from `LIBRECRAWL_URL`:

```json
{
  "mcpServers": {
    "librecrawl": {
      "command": "python",
      "args": ["/absolute/path/to/server.py"],
      "env": { "MCP_TRANSPORT": "stdio", "LIBRECRAWL_URL": "http://127.0.0.1:5080" }
    }
  }
}
```

## Docker Compose

`docker-compose.yml` sets container-appropriate values automatically:

```yaml
environment:
  - MCP_TRANSPORT=http
  - MCP_HOST=0.0.0.0
  - MCP_PORT=5081
  - LIBRECRAWL_URL=http://librecrawl:5000
  - REPORTS_DIR=/reports
  - LIBRECRAWL_UPSTREAM_DB=/librecrawl-data/users.db
  - PAGESPEED_API_KEY=${PAGESPEED_API_KEY:-}
  - MASTER_AUDIT_V3_ENABLED=${MASTER_AUDIT_V3_ENABLED:-false}
  - MASTER_AUDIT_GSC_ENABLED=${MASTER_AUDIT_GSC_ENABLED:-true}
  - GSC_ACCESS_TOKEN=${GSC_ACCESS_TOKEN:-}
  - GSC_SITE_URL=${GSC_SITE_URL:-}
```

Put credentials in a local `.env` next to `docker-compose.yml` (copy `.env.example`). GSC private data requires OAuth 2.0; an API key is insufficient. Access tokens are short-lived, so production deployments should inject a refreshed token through their secret manager. The MCP port is published on loopback only (`127.0.0.1:5081`); change the port mapping deliberately to expose it elsewhere.
