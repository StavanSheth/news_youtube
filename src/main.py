from __future__ import annotations

import argparse
from pathlib import Path

from intelligence.pipeline import run

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate the repository-backed intelligence digest."
    )
    parser.add_argument("--dry-run", action="store_true", help="Avoid Gemini and email delivery.")
    args = parser.parse_args()
    markdown, html = run(Path(__file__).resolve().parents[1], dry_run=args.dry_run)
    print(f"Generated {markdown} and {html}")
