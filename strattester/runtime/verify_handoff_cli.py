"""Validate a Strattester science handoff before copying it to a Grid node.

Usage: python -m strattester.runtime.verify_handoff_cli PATH_TO_MANIFEST
This command is read-only and returns nonzero on invalid or missing payloads.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from .grid_handoff import verify_handoff


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        data = verify_handoff(args.manifest)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps({"ok": True, "schema": data["schema"], "source": data["source"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
