"""Stdio MCP entry: python -m mcp_server  (from backend/)."""
from __future__ import annotations

import asyncio
import json
import sys

from services.mcp_protocol import handle_mcp


async def _loop() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        reply = await handle_mcp(message)
        sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(_loop())
