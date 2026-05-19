"""Content-profile management CLI.

Subcommands:
- ``list``          show every available profile under ``app/bot/content/``
- ``new <slug>``    scaffold a new profile by cloning ``default/`` into ``<slug>/``
- ``validate <slug>``  load the profile through ``ContentService`` and report errors
- ``diff <a> <b>``  list per-file size differences between two profiles (cheap sanity check)

Examples
--------
    python -m app.scripts.profiles list
    python -m app.scripts.profiles new my_client_garage --from auto_service
    python -m app.scripts.profiles validate my_client_garage
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from app.services.content import ContentService

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "bot" / "content"
PROFILE_FILES = ("brand.yaml", "config.yaml", "categories.yaml", "faq.yaml", "texts.yaml")


def _ok(msg: str) -> None:
    print(f"✓ {msg}")


def _fail(msg: str) -> None:
    print(f"✗ {msg}", file=sys.stderr)


def cmd_list(_args: argparse.Namespace) -> int:
    if not CONTENT_ROOT.exists():
        _fail(f"content root missing: {CONTENT_ROOT}")
        return 1
    profiles = sorted(p.name for p in CONTENT_ROOT.iterdir() if p.is_dir())
    if not profiles:
        print("(no profiles)")
        return 0
    print("Available profiles (CONTENT_PROFILE):")
    for name in profiles:
        # Annotate with company name if loadable; otherwise show the error briefly.
        try:
            bundle = ContentService.load(CONTENT_ROOT / name)
            print(f"  - {name:20s}  {bundle.brand.company_name}")
        except Exception as exc:  # noqa: BLE001 — surface any load error
            print(f"  - {name:20s}  [INVALID: {type(exc).__name__}]")
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    slug: str = args.slug
    source: str = args.source
    target = CONTENT_ROOT / slug
    if target.exists():
        _fail(f"profile {slug!r} already exists at {target}")
        return 1
    src = CONTENT_ROOT / source
    if not src.is_dir():
        _fail(f"source profile {source!r} not found at {src}")
        return 1

    shutil.copytree(src, target)
    # Strip any compiled / cache files just in case.
    for junk in target.rglob("__pycache__"):
        shutil.rmtree(junk, ignore_errors=True)
    _ok(f"created profile {slug!r} from {source!r}")

    # Best-effort sanity check immediately after copy.
    try:
        bundle = ContentService.load(target)
        _ok(f"loads cleanly: company={bundle.brand.company_name!r}")
    except Exception as exc:  # noqa: BLE001
        _fail(f"new profile failed to load: {type(exc).__name__}: {exc}")
        return 2

    print()
    print(f"Edit YAML files in {target}, then set CONTENT_PROFILE={slug} in .env.")
    print("Files to edit:")
    for fname in PROFILE_FILES:
        print(f"  - {target}/{fname}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    slug: str = args.slug
    path = CONTENT_ROOT / slug
    if not path.is_dir():
        _fail(f"profile {slug!r} not found at {path}")
        return 1
    try:
        bundle = ContentService.load(path)
    except Exception as exc:  # noqa: BLE001
        _fail(f"{slug}: {type(exc).__name__}: {exc}")
        return 2
    cats = [c.slug for c in bundle.categories]
    _ok(f"{slug}: brand={bundle.brand.company_name!r}")
    _ok(f"{slug}: {len(cats)} categories: {', '.join(cats)}")
    _ok(f"{slug}: {len(bundle.faq)} FAQ entries")
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    a: str = args.profile_a
    b: str = args.profile_b
    pa, pb = CONTENT_ROOT / a, CONTENT_ROOT / b
    if not pa.is_dir() or not pb.is_dir():
        _fail(f"one of profiles missing: {pa}, {pb}")
        return 1
    print(f"{'file':<20} {a:>14} {b:>14}")
    for fname in PROFILE_FILES:
        sa = (pa / fname).stat().st_size if (pa / fname).exists() else 0
        sb = (pb / fname).stat().st_size if (pb / fname).exists() else 0
        marker = "" if sa == sb else "  ←"
        print(f"{fname:<20} {sa:>14} {sb:>14}{marker}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="profiles",
        description="Manage content profiles (brand/texts/faq/categories/config) for the bot.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list all profiles").set_defaults(func=cmd_list)

    new = sub.add_parser("new", help="create a new profile by cloning an existing one")
    new.add_argument("slug", help="slug of the new profile (lowercase, _ allowed)")
    new.add_argument(
        "--from",
        dest="source",
        default="default",
        help="source profile to clone (default: 'default')",
    )
    new.set_defaults(func=cmd_new)

    val = sub.add_parser("validate", help="load and validate a profile")
    val.add_argument("slug")
    val.set_defaults(func=cmd_validate)

    diff = sub.add_parser("diff", help="list per-file size diff between two profiles")
    diff.add_argument("profile_a")
    diff.add_argument("profile_b")
    diff.set_defaults(func=cmd_diff)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
