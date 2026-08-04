"""Run the Plane Remote MCP gateway."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "plane_mcp_gateway.app:app",
        host="0.0.0.0",
        port=int(os.getenv("MCP_PORT", "8211")),
        proxy_headers=True,
        forwarded_allow_ips=os.getenv("MCP_FORWARDED_ALLOW_IPS", "127.0.0.1"),
        access_log=False,
    )


if __name__ == "__main__":
    main()
