"""Run the optical and electrical analyses from the bundled instrument data."""

import argparse
from pathlib import Path
import subprocess
import sys


ANALYSIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = ANALYSIS_DIR.parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "results" / "replication",
        help="Directory for generated figures, CSV, and JSON files.",
    )
    output_dir = parser.parse_args().output_dir.resolve()
    commands = [
        ("absorbance.py", []),
        ("iv.py", []),
        ("detector.py", ["--raw", "--iv-summary", str(output_dir / "iv_summary.json")]),
    ]
    for script, arguments in commands:
        result = subprocess.run(
            [sys.executable, str(ANALYSIS_DIR / script), "--output-dir", str(output_dir), *arguments],
            check=False,
        )
        if result.returncode:
            print(f"Analysis stopped at {script}.", file=sys.stderr)
            return result.returncode
    print(f"Figures and numerical results: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
