from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from domaintoolbelt.core.events import EventBus
from domaintoolbelt.core.kernel import build_default_kernel
from domaintoolbelt.domain_packs.registry import build_pack, list_pack_keys


def build_parser() -> argparse.ArgumentParser:
    pack_choices = list_pack_keys() or ("bible_pack",)
    parser = argparse.ArgumentParser(description="Run a DomainToolBelt domain pack.")
    parser.add_argument(
        "--domain",
        default="bible_pack",
        choices=pack_choices,
        help="Domain pack to run.",
    )
    request_group = parser.add_mutually_exclusive_group(required=True)
    request_group.add_argument("--query", help="User request to process.")
    request_group.add_argument(
        "--resume",
        metavar="SESSION_ID",
        help="Resume workflow from a saved checkpoint.",
    )
    parser.add_argument(
        "--state-dir",
        default=".domaintoolbelt",
        help="Directory for checkpoints, memory, and traces.",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="Emit structured trace logs to the state directory.",
    )
    parser.add_argument(
        "--trace-dir",
        default="",
        help="Override the trace output directory.",
    )
    parser.add_argument(
        "--ui",
        choices=("plain", "rich"),
        default="plain",
        help="Optional terminal UI mode.",
    )
    return parser


async def _run(
    domain: str,
    state_dir: str,
    query: str | None = None,
    resume: str | None = None,
    enable_tracing: bool = False,
    trace_dir: str | None = None,
    ui_mode: str = "plain",
) -> str:
    root = Path(state_dir)
    pack = build_pack(domain, storage_root=root)
    event_bus = EventBus()
    kernel = build_default_kernel(
        storage_root=root,
        event_bus=event_bus,
        enable_tracing=enable_tracing,
        trace_dir=trace_dir or None,
    )

    if ui_mode == "rich":
        from domaintoolbelt.ui.tui.live_app import RichWorkflowRenderer

        request_label = query or f"Resume session {resume}"
        renderer = RichWorkflowRenderer(request=request_label)
        renderer.attach(event_bus)
        with renderer:
            if resume:
                return await kernel.resume(pack, resume)
            return await kernel.run(pack, str(query))

    if resume:
        return await kernel.resume(pack, resume)
    return await kernel.run(pack, str(query))


def main() -> None:
    args = build_parser().parse_args()
    try:
        answer = asyncio.run(
            _run(
                domain=args.domain,
                state_dir=args.state_dir,
                query=args.query,
                resume=args.resume,
                enable_tracing=args.trace,
                trace_dir=args.trace_dir or None,
                ui_mode=args.ui,
            )
        )
    except ImportError as exc:
        raise SystemExit(str(exc)) from exc
    print(answer)


if __name__ == "__main__":
    main()
