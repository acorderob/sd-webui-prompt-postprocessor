#!/usr/bin/env python3

"""
Converts style files (A1111 CSV or SD.Next JSON) to a PPP-compatible YAML wildcard file.

Usage:
    python convert_styles.py [--format {a1111,sdnext}] <input> <output>

Arguments:
    input   Path to the A1111 styles CSV file, a SD.Next JSON file, or a folder of SD.Next JSON files.
    output  Path to the output YAML wildcard file.

Options:
    --format    Force the input format. If omitted, the format is inferred from the input:
                - a1111  : input is a .csv file
                - sdnext : input is a .json file or a directory
"""

import argparse
import sys
from pathlib import Path

# Allow importing from the parent package when running directly from this folder.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ppp_common import convert_a1111_styles_to_wildcard, convert_sdnext_styles_to_wildcard


def detect_format(inp: Path) -> str:
    if inp.is_dir():
        return "sdnext"
    if inp.suffix.lower() == ".csv":
        return "a1111"
    if inp.suffix.lower() == ".json":
        return "sdnext"
    return ""


def main():
    parser = argparse.ArgumentParser(
        description="Convert A1111 or SD.Next style files to a PPP YAML wildcard file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("input", type=Path, help="Input CSV file (A1111) or JSON file/folder (SD.Next).")
    parser.add_argument("output", type=Path, help="Output YAML wildcard file.")
    parser.add_argument(
        "--format",
        choices=["a1111", "sdnext"],
        default=None,
        help="Force input format. Auto-detected from the input path when not specified.",
    )
    args = parser.parse_args()

    inp: Path = args.input
    out: Path = args.output

    if not inp.exists():
        print(f"Error: input path does not exist: {inp}", file=sys.stderr)
        sys.exit(1)

    if out.suffix.lower() not in (".yaml", ".yml"):
        print(f"Error: output path is not a YAML file: {out}", file=sys.stderr)
        sys.exit(1)

    fmt = args.format or detect_format(inp)
    if not fmt:
        print(
            f"Error: could not detect format from '{inp}'. Use --format to specify it explicitly.",
            file=sys.stderr,
        )
        sys.exit(1)

    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        if fmt == "a1111":
            convert_a1111_styles_to_wildcard(inp, out)
        else:
            convert_sdnext_styles_to_wildcard(inp, out)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Converted '{inp}' ({fmt}) -> '{out}'")


if __name__ == "__main__":
    main()
