"""CLI entry point for Florida Litigator Weekly Update.

Provides subcommands: preview (C08), with placeholders for future
commands (registry, fetch, analyze, produce, publish, schedule).

Args:
    preview --fixture PATH    Path to synthetic fixture JSON file.
    preview --state-root PATH Directory for SQLite state/database.
    preview --output PATH     Directory for output HTML/Markdown files.
    preview --observed-at UTC Optional observation timestamp.

Example:
    flwu preview --fixture fixtures/synthetic-source.json \
                 --state-root /tmp/flwu_state \
                 --output /tmp/flwu_output
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns exit code 0 on success, 1 on failure."""
    parser = argparse.ArgumentParser(
        prog="flwu",
        description="Florida Litigator Weekly Update — automated legal research pipeline.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # preview subcommand (C08)
    preview_parser = subparsers.add_parser(
        "preview",
        help="Run a synthetic fixture and produce a preview HTML report.",
    )
    preview_parser.add_argument(
        "--fixture", required=True, dest="fixture_path",
        help="Path to synthetic fixture JSON file.",
    )
    preview_parser.add_argument(
        "--state-root", required=True, dest="state_root",
        help="Directory for SQLite state/database.",
    )
    preview_parser.add_argument(
        "--output", required=True, dest="output_path",
        help="Directory for output HTML files.",
    )
    preview_parser.add_argument(
        "--observed-at", default=None, dest="observed_at",
        help="ISO-8601 observation timestamp (default: current UTC).",
    )
    preview_parser.add_argument(
        "--mode", default="fixture", choices=["fixture", "production"],
        help="Pipeline mode. Preview defaults to fixture.",
    )
    preview_parser.add_argument(
        "--window-start", default=None,
        help="Report window start date (YYYY-MM-DD).",
    )
    preview_parser.add_argument(
        "--window-end", default=None,
        help="Report window end date (YYYY-MM-DD).",
    )

    # Future subcommand placeholders (C34, C37, C39, C40)
    subparsers.add_parser("registry", help="Manage source registries (future).")
    subparsers.add_parser("fetch", help="Acquire source data (future).")
    subparsers.add_parser("analyze", help="Run analysis jobs (future).")
    subparsers.add_parser("produce", help="Produce a report (future).")
    subparsers.add_parser("publish", help="Publish to GitHub Pages (future).")
    subparsers.add_parser("schedule", help="Schedule recurring runs (future).")

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "preview":
        return _handle_preview(args)

    # Future commands: print placeholder and return 0
    # Implementation will be added in later cards
    print(f"Command 'flwu {args.command}' is not yet implemented.", file=sys.stderr)
    return 1


def _handle_preview(args: argparse.Namespace) -> int:
    """Handle the preview subcommand."""
    from flwu.fixture_pipeline import run_fixture, PipelineError

    fixture_path = Path(args.fixture_path)
    if not fixture_path.is_file():
        print(f"Error: fixture file not found: {fixture_path}", file=sys.stderr)
        return 1

    try:
        state_root = Path(args.state_root)
        output_dir = Path(args.output_path)

        issue = run_fixture(
            input_path=fixture_path,
            state_root=state_root,
            output_dir=output_dir,
            observed_at=args.observed_at,
            window_start=args.window_start,
            window_end=args.window_end,
        )

        print(f"Preview generated: {issue.get('issue_id', 'unknown')}")
        print(f"  Mode: {issue.get('mode', 'N/A')}")
        print(f"  Window: {issue.get('window_start', '')} to {issue.get('window_end', '')}")
        print(f"  Cutoff: {issue.get('cutoff_utc', 'N/A')}")
        print(f"  Output: {output_dir}")

        # Show categories summary
        categories = issue.get("categories", {})
        for section_name, section_records in categories.items():
            print(f"  {section_name}: {len(section_records)} records")

        return 0

    except PipelineError as e:
        print(f"Pipeline error [{e.code}]: {e.message}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1
