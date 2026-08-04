#!/usr/bin/env python3
"""Local-source intake for the DilChat Guna authority workflow (Section 5).

Records a *sanitized* provenance metadata block for a lawfully-held local source
copy (a purchased/library/archival edition) WITHOUT copying the source into the
repository and WITHOUT leaking the local filesystem path. It computes the file's
SHA-256 so a reviewer can later prove the exact bytes that were adjudicated.

What it does:
- reads a local source file (path supplied on the command line, never committed);
- computes its SHA-256 and byte size;
- records ONLY the basename, hash, size, edition identity, acquisition method,
  and access date;
- prints a sanitized JSON metadata record to stdout (or ``--out``).

What it deliberately does NOT do:
- it does not copy, move, or embed the source file anywhere in the repo;
- it does not write or echo the absolute/local path (only the basename is kept);
- it does not mark anything FROZEN — freezing is a human reviewer decision made
  against ``GUNA_SOURCE_MANIFEST.json`` after the text is verified.

This is intake/provenance tooling only. It contains NO Guna scoring logic and
produces NO adjudication.

Usage:
  python scripts/source_intake.py \
      --file /path/to/lawful/copy.pdf \
      --source-id MC-NORMATIVE \
      --edition "Muhurta Chintamani, Girish Chand Sharma tr., Sagar Publications, 1996" \
      --acquisition-method "purchased_ebook" \
      --access-date 2026-08-04 \
      [--out record.json]

The emitted record is intended for human review before any manifest update; the
script never mutates the committed manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

# Only these coarse acquisition methods are accepted, mirroring Section 4's
# "acceptable access" list. Anything else is rejected so an unlawful/insufficient
# source (search snippet, unsourced table, AI text) cannot be recorded as intake.
ACCEPTED_METHODS = {
    "purchased_physical",
    "purchased_ebook",
    "library_access",
    "lawful_archive_access",
    "user_provided_excerpt",
    "professional_transcription",
}

CHUNK = 1 << 20


def _sha256_and_size(path: str) -> tuple[str, int]:
    h = hashlib.sha256()
    size = 0
    with open(path, "rb") as fh:
        while True:
            block = fh.read(CHUNK)
            if not block:
                break
            size += len(block)
            h.update(block)
    return h.hexdigest(), size


def build_record(*, file_path: str, source_id: str, edition: str,
                 acquisition_method: str, access_date: str) -> dict:
    if acquisition_method not in ACCEPTED_METHODS:
        raise ValueError(
            f"acquisition_method {acquisition_method!r} is not an accepted lawful "
            f"access method (allowed: {sorted(ACCEPTED_METHODS)})"
        )
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"source file not found: {file_path}")
    digest, size = _sha256_and_size(file_path)
    # Sanitized: only the basename is retained; the local path is intentionally
    # dropped so it can never leak into a committed record.
    return {
        "record_type": "dilchat_guna_source_intake",
        "record_version": 1,
        "source_id": source_id,
        "edition_identity": edition,
        "acquisition_method": acquisition_method,
        "access_date": access_date,
        "file_basename": os.path.basename(file_path),
        "file_sha256": digest,
        "file_size_bytes": size,
        "local_path": "OMITTED — local source paths are never recorded",
        "copied_into_repo": False,
        "freeze_status": "ACQUIRED_PENDING_TEXT_VERIFICATION",
        "note": (
            "Provenance only. The source file is NOT committed. A qualified "
            "reviewer must verify the text/pagination before any rule is frozen; "
            "this record does not itself freeze any source or approve any rule."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Sanitized local-source intake (no repo copy).")
    p.add_argument("--file", required=True,
                   help="path to the lawful local source copy (never committed)")
    p.add_argument("--source-id", required=True)
    p.add_argument("--edition", required=True)
    p.add_argument("--acquisition-method", required=True)
    p.add_argument("--access-date", required=True, help="YYYY-MM-DD")
    p.add_argument("--out", default=None, help="write the sanitized record here (default: stdout)")
    args = p.parse_args(argv)

    try:
        record = build_record(
            file_path=args.file,
            source_id=args.source_id,
            edition=args.edition,
            acquisition_method=args.acquisition_method,
            access_date=args.access_date,
        )
    except (ValueError, FileNotFoundError) as exc:
        print(f"intake error: {exc}", file=sys.stderr)
        return 2

    text = json.dumps(record, indent=2) + "\n"
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(text)
        print(f"wrote sanitized intake record -> {args.out} (source file NOT copied)")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
