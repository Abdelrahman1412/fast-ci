#!/usr/bin/env python3
"""Print one hash for everything that shapes the migrated test database.

The hash is the cache key for the database dump, and it is also written into
the dump itself, so a restored dump can prove it matches the code it is
restored for. Include every input: the migration files, the code that applies
them, and the Postgres major version. Leaving one out is how a cache serves a
stale schema.

    fingerprint.py --root backend 'migrations/**' app/migrate.py --salt pg17
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path


def fingerprint(root: Path, patterns: list[str], salt: str = "") -> tuple[str, list[Path]]:
    files: set[Path] = set()
    for pattern in patterns:
        matched = [p for p in root.glob(pattern) if p.is_file()]
        if not matched:
            raise SystemExit(f"fingerprint: pattern {pattern!r} matched no files under {root}")
        files.update(matched)
    digest = hashlib.sha256(salt.encode())
    ordered = sorted(files, key=lambda p: p.relative_to(root).as_posix())
    for path in ordered:
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:20], ordered


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("patterns", nargs="+", help="glob patterns relative to --root")
    parser.add_argument("--root", default=".", type=Path)
    parser.add_argument("--salt", default="", help="extra input, e.g. the Postgres major version")
    parser.add_argument("--list", action="store_true", help="also list the files that went into the hash")
    args = parser.parse_args(argv)
    value, files = fingerprint(args.root, args.patterns, args.salt)
    if args.list:
        for path in files:
            print(f"  {path.relative_to(args.root).as_posix()}", file=sys.stderr)
    print(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
