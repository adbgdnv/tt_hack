#!/usr/bin/env python3
"""Read-only consistency audit for vibe-debug comments and screenshots."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from review_schema import load_schema, split_legacy, validate  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comments", type=Path, required=True)
    parser.add_argument("--attachments", type=Path, required=True)
    return parser.parse_args()


def load_comments(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ValueError("comments.json must contain an array of objects")
    return data


def audit(comments: list[dict[str, Any]], attachments_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    ids: set[str] = set()
    referenced_files: set[str] = set()
    schema = load_schema()

    for index, comment in enumerate(comments):
        comment_id = str(comment.get("id") or f"record-{index}")
        hard, soft = split_legacy(validate(comment, schema))
        errors.extend(f"{comment_id}: {item}" for item in hard)
        warnings.extend(f"{comment_id}: legacy — {item}" for item in soft)
        if comment_id in ids:
            errors.append(f"{comment_id}: duplicate id")
        ids.add(comment_id)
        if not comment.get("anchor"):
            warnings.append(f"{comment_id}: no anchor (legacy or page-level record)")

        raw_attachments = comment.get("attachments")
        if raw_attachments is None:
            warnings.append(f"{comment_id}: attachments is null (legacy record)")
            raw_attachments = []
        if not isinstance(raw_attachments, list):
            errors.append(f"{comment_id}: attachments must be an array or null")
            continue
        for attachment in raw_attachments:
            if not isinstance(attachment, dict):
                errors.append(f"{comment_id}: attachment must be an object")
                continue
            token = str(attachment.get("token") or "")
            if not token or token not in str(comment.get("text") or ""):
                errors.append(f"{comment_id}: screenshot token missing from text")
            url = str(attachment.get("url") or "")
            filename = url.rsplit("/", 1)[-1]
            if not filename:
                errors.append(f"{comment_id}: attachment URL has no filename")
                continue
            referenced_files.add(filename)
            path = attachments_dir / filename
            if not path.is_file():
                errors.append(f"{comment_id}: attachment file missing: {filename}")
                continue
            expected_size = attachment.get("size")
            if isinstance(expected_size, int) and path.stat().st_size != expected_size:
                errors.append(
                    f"{comment_id}: attachment size mismatch for {filename}: "
                    f"JSON={expected_size}, file={path.stat().st_size}"
                )

    actual_files = (
        {path.name for path in attachments_dir.iterdir() if path.is_file()}
        if attachments_dir.is_dir()
        else set()
    )
    for filename in sorted(actual_files.difference(referenced_files)):
        warnings.append(f"orphan attachment: {filename}")

    statuses = Counter(str(item.get("status") or "missing") for item in comments)
    routes = Counter(str(item.get("route") or "missing") for item in comments)
    authors = Counter(str(item.get("author") or "missing") for item in comments)
    active = sum(item.get("status") not in {"resolved", "wont_fix", "done"} for item in comments)
    return {
        "ok": not errors,
        "comments": len(comments),
        "active": active,
        "statuses": dict(sorted(statuses.items())),
        "routes": dict(sorted(routes.items())),
        "authors": dict(sorted(authors.items())),
        "referencedAttachments": len(referenced_files),
        "storedAttachments": len(actual_files),
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    args = parse_args()
    try:
        result = audit(load_comments(args.comments), args.attachments)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        result = {"ok": False, "errors": [str(error)], "warnings": []}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
