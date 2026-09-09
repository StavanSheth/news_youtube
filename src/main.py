from __future__ import annotations

import argparse
from pathlib import Path

from intelligence.production import run

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate the repository-backed intelligence digest."
    )
    parser.add_argument("--dry-run", action="store_true", help="Avoid Gemini and email delivery.")
    parser.add_argument("--fixture", type=Path, help="Use a deterministic JSON corpus instead of live sources.")
    args = parser.parse_args()
    markdown, html = run(Path(__file__).resolve().parents[1], dry_run=args.dry_run, fixture_path=args.fixture)
    print(f"Generated {markdown} and {html}")
