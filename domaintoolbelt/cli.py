from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from domaintoolbelt.core.kernel import build_default_kernel
from domaintoolbelt.domain_packs.bible_pack import BiblePack


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a DomainToolBelt domain pack.")
    parser.add_argument(
        "--domain",
        default="bible_pack",
        choices=("bible_pack",),
        help="Domain pack to run.",
    )
    parser.add_argument("--query", required=True, help="User request to process.")
    parser.add_argument(
        "--state-dir",
        default=".domaintoolbelt",
        help="Directory for checkpoints and memory.",
    )
    return parser


async def _run(domain: str, query: str, state_dir: str) -> str:
    root = Path(state_dir)
    if domain != "bible_pack":
        raise ValueError(f"Unsupported domain pack: {domain}")

    pack = BiblePack(storage_root=root)
    kernel = build_default_kernel(storage_root=root)
    return await kernel.run(pack, query)


def main() -> None:
    args = build_parser().parse_args()
    answer = asyncio.run(_run(args.domain, args.query, args.state_dir))
    print(answer)


if __name__ == "__main__":
    main()
