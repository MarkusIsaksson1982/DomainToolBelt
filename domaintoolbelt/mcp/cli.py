from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from domaintoolbelt.core.kernel import build_default_kernel
from domaintoolbelt.domain_packs.registry import build_pack, list_pack_keys
from domaintoolbelt.mcp.server import DomainPackServer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run DomainToolBelt as a local MCP server.")
    parser.add_argument(
        "--domain",
        default="bible_pack",
        choices=list_pack_keys() or ("bible_pack",),
        help="Domain pack to serve.",
    )
    parser.add_argument(
        "--state-dir",
        default=".domaintoolbelt",
        help="Directory for checkpoints and memory.",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="Emit structured trace logs to the state directory.",
    )
    return parser


async def run_stdio_server(domain: str, state_dir: str, enable_tracing: bool = False) -> None:
    root = Path(state_dir)
    pack = build_pack(domain, storage_root=root)
    kernel = build_default_kernel(storage_root=root, enable_tracing=enable_tracing)
    server = DomainPackServer(pack, kernel=kernel, session_root=root / "mcp_sessions")

    while True:
        line = await asyncio.to_thread(sys.stdin.readline)
        if not line:
            break
        raw = line.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
            response = await server.handle(payload)
        except Exception as exc:
            response = {"error": str(exc)}
        print(json.dumps(response), flush=True)


def main() -> None:
    args = build_parser().parse_args()
    asyncio.run(run_stdio_server(args.domain, args.state_dir, enable_tracing=args.trace))


if __name__ == "__main__":
    main()
