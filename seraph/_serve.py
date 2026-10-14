"""CLI entry point for seraph-serve."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Start the SERAPH governance sidecar server.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host.")
    parser.add_argument("--port", type=int, default=8000, help="Bind port.")
    parser.add_argument("--reload", action="store_true", help="Auto-reload on code changes.")
    args = parser.parse_args(argv)

    try:
        import uvicorn
    except ImportError:
        print(
            "seraph-serve requires uvicorn.\n"
            "Install with: pip install 'seraph-governance[serve]'",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"[SERAPH] Governance sidecar starting on {args.host}:{args.port}")
    uvicorn.run(
        "seraph.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
