# Deployment and persistence

## Docker Compose

Run `docker compose config -q` before deployment and `docker compose up --build`. The MCP binds to `127.0.0.1:5081` on the host by default. Expose it remotely only behind an authenticated trusted network boundary.

Compose uses:

- `./reports:/reports` for downloadable reports and ZIP staging;
- `librecrawl-data:/librecrawl-data:ro` for read-only upstream metadata;
- `audit-snapshots:/snapshots` for portable baselines that survive container recreation.

`AUDIT_SNAPSHOT_OUTPUT_DIR` defaults to `/snapshots` in Compose. To compare against a baseline, place it in that volume and set `AUDIT_SNAPSHOT_BASELINE_PATH` to its container path. `librecrawl_snapshot_export` is the portable download alternative.

External inputs such as server logs and WordPress/render/availability snapshots must be mounted read-only and their configured paths must use container paths. Never mount an entire home directory or credential store.

## Permissions

The container needs write access only to `/reports` and `/snapshots`. Evidence inputs and LibreCrawl data are read-only. On Linux, ensure the bind-mounted directories are writable by the container user before startup. On SELinux hosts, apply the appropriate bind-mount label according to local policy.

On Windows Docker Desktop, use an absolute shared-drive bind path when replacing `./reports`; Windows ACLs must allow Docker Desktop to write the directory. Environment values containing drive-letter paths are host paths only—provider variables must point to their mounted Linux container paths.

## Non-container installation

Use Python 3.11+ in a virtual environment, install `requirements.txt`, configure `REPORTS_DIR`, and start `python server.py`. WeasyPrint requires the platform libraries listed in the Dockerfile. Use `MCP_TRANSPORT=stdio` for client-launched processes or HTTP on a loopback/trusted interface for a service.

## Retention and recovery

Audit sessions remain ephemeral. `librecrawl_audit_zip(auto_cleanup=True)` returns the complete base64 ZIP and deletes server-side session artifacts. Use `auto_cleanup=False` only for a deliberate short-lived preview. Portable snapshots persist independently in the snapshot volume or after export. No audit command writes to the audited website.
