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

    directory_parser = subparsers.add_parser("directory", help="Import the reviewed judicial directory and render its appendix.")
    directory_parser.add_argument("--database", required=True, type=Path)
    directory_parser.add_argument("--output", required=True, type=Path)

    preview_parser.add_argument("--directory-db", type=Path, default=None, help="Read the current reviewed directory snapshot from this SQLite database.")

    # Future subcommand placeholders (C34, C37, C39, C40)
    subparsers.add_parser("registry", help="Manage source registries (future).")
    subparsers.add_parser("fetch", help="Acquire source data (future).")
    subparsers.add_parser("analyze", help="Run analysis jobs (future).")
    subparsers.add_parser("produce", help="Produce a report (future).")
    site = subparsers.add_parser("site", help="Export reviewed history or build the date-range website.")
    site.add_argument("action", choices=["export", "build"])
    site.add_argument("--archive", type=Path, required=True)
    site.add_argument("--database", type=Path)
    site.add_argument("--capture-id")
    site.add_argument("--output", type=Path)
    site.add_argument("--preview", action="store_true", help="Allow synthetic/unpublished data; never use for public deployment")
    publish = subparsers.add_parser("publish", help="Build a validated production Pages artifact; deployment uses GitHub Actions.")
    publish.add_argument("--archive", type=Path, default=Path("website/updates"))
    publish.add_argument("--output", type=Path, required=True)
    subparsers.add_parser("schedule", help="Schedule recurring runs (future).")

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command in ("site", "publish"):
        from flwu.publication import export_capture
        from flwu.site import build_site
        import sqlite3
        try:
            if args.command == "site" and args.action == "export":
                if not args.database or not args.capture_id:
                    raise ValueError("export requires --database and --capture-id")
                result = export_capture(args.database, args.capture_id, args.archive, preview=args.preview)
            else:
                if not args.output:
                    raise ValueError("build requires --output (a new directory)")
                result = build_site(args.archive, args.output, preview=getattr(args, "preview", False))
            print(result)
            return 0
        except (ValueError, OSError, KeyError, TypeError, sqlite3.Error) as exc:
            print(f"Website error: {exc}", file=sys.stderr)
            return 1

    if args.command == "directory":
        from flwu.directory import load_directory, import_directory, read_directory
        from flwu.directory_render import render_directory
        from flwu.state import open_db, migrate
        import json
        args.database.parent.mkdir(parents=True, exist_ok=True)
        args.output.mkdir(parents=True, exist_ok=True)
        conn = open_db(args.database)
        try:
            migrate(conn)
            result = import_directory(conn, load_directory())
            data = read_directory(conn)
            (args.output / "judicial-directory.html").write_text(render_directory(data), encoding="utf-8")
            (args.output / "judicial-directory.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
            print(json.dumps(result))
        finally:
            conn.close()
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

        directory = None
        if args.directory_db:
            import sqlite3
            from flwu.directory import read_directory
            conn = sqlite3.connect(args.directory_db.resolve().as_uri() + "?mode=ro", uri=True)
            try:
                directory = read_directory(conn)
            finally:
                conn.close()

        issue = run_fixture(
            input_path=fixture_path,
            directory=directory,
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
