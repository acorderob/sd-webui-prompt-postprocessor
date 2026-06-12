#!/usr/bin/env python3

"""
Scans wildcard and extranetwork mapping files for LoRA references and checks
if those LoRAs exist in the specified folders.

Recognized LoRA reference formats:
    <lora:NAME:weight>       Standard A1111/ComfyUI inline LoRA tag.
    <ppp:ext lora NAME ...>  PPP explicit LoRA command (quoted or unquoted name).

LoRA names that contain wildcards or inline choices (e.g. __path__, {a|b}) are
reported as dynamic and skipped - they cannot be resolved statically.

Usage:
    python check_loras.py -l LORA_FOLDER [LORA_FOLDER ...] [options]

Options:
    -w, --wildcards     One or more wildcard folder paths to scan.
    -e, --enmappings    One or more enmapping folder paths to scan.
    -l, --loras         One or more folders to search for LoRA files (required).
    --extensions        LoRA file extensions (default: .safetensors .pt .ckpt .bin).
    --case-sensitive    Enable case-sensitive name matching (default: case-insensitive).
    -v, --verbose       Also list LoRAs that were found.
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from ruamel.yaml import YAML
except ImportError:
    print("Error: ruamel.yaml is required. Install with: pip install ruamel.yaml", file=sys.stderr)
    sys.exit(1)

WILDCARD_EXTENSIONS = {".yaml", ".yml", ".json", ".txt"}
ENMAPPING_EXTENSIONS = {".yaml", ".yml", ".json"}

# Matches <lora:NAME>, <lora:NAME:w>, <lora:NAME:w1:w2>
# The name ends at the first colon or closing >, but may contain spaces.
_RE_LORA_STANDARD = re.compile(r"<lora:([^:>\s][^:>]*?)(?::[^>]*)?>")

# Matches <ppp:ext lora NAME ...> where NAME is single-quoted, double-quoted, or unquoted.
# The unquoted form stops before whitespace, >, or / to avoid capturing the rest of the tag.
_RE_LORA_PPP_EXT = re.compile(r"<ppp:ext\s+lora\s+(?:'([^']*)'|\"([^\"]*)\"|([\w.\-()][^\s>/'\"]*))")


def _read_text(path: Path) -> str | None:
    for encoding in ("utf-8", "cp1252"):
        try:
            return path.read_text(encoding=encoding)
        except (UnicodeDecodeError, OSError):
            continue
    print(f"Warning: could not read file: {path}", file=sys.stderr)
    return None


def _is_dynamic(name: str) -> bool:
    # Names with choice syntax {a|b} or wildcard references __path__ cannot be
    # statically resolved.
    return "{" in name or "}" in name or name.count("__") >= 2


_RE_SD_ESCAPE = re.compile(r"\\(.)")


def _unescape_sd(name: str) -> str:
    # SD prompts escape special characters with a backslash (e.g. \( \) \[ \] \: \\).
    # The actual filename on disk has no escaping, so strip them before lookup.
    return _RE_SD_ESCAPE.sub(r"\1", name)


def _extract_lora_names(text: str) -> list[str]:
    names = []
    for m in _RE_LORA_STANDARD.finditer(text):
        names.append(_unescape_sd(m.group(1).strip()))
    for m in _RE_LORA_PPP_EXT.finditer(text):
        name = m.group(1) or m.group(2) or m.group(3)
        if name:
            names.append(_unescape_sd(name.strip()))
    return names


def _walk_strings_with_path(value, path: str = "") -> list[tuple[str, str]]:
    """Recursively collect (string_value, key_path) pairs from a parsed YAML/JSON structure."""
    if isinstance(value, str):
        return [(value, path)]
    if isinstance(value, list):
        result = []
        for item in value:
            result.extend(_walk_strings_with_path(item, path))
        return result
    if isinstance(value, dict):
        result = []
        for k, v in value.items():
            child_path = f"{path} > {k}" if path else str(k)
            result.extend(_walk_strings_with_path(v, child_path))
        return result
    return []


def scan_wildcard_file(path: Path) -> list[tuple[str, str]]:
    """Return (lora_name, location) pairs found in a wildcard file."""
    text = _read_text(path)
    if text is None:
        return []

    found = []
    suffix = path.suffix.lower()

    if suffix == ".txt":
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            for name in _extract_lora_names(stripped):
                found.append((name, f"line {lineno}"))
        return found

    yaml = YAML(typ="safe")
    try:
        data = yaml.load(text)
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Warning: could not parse {path}: {exc}", file=sys.stderr)
        return []

    for string_val, key_path in _walk_strings_with_path(data):
        for name in _extract_lora_names(string_val):
            found.append((name, key_path))

    return found


def scan_enmapping_file(path: Path) -> list[tuple[str, str]]:
    """Return (lora_name, context_snippet) pairs found in an enmapping file."""
    text = _read_text(path)
    if text is None:
        return []

    yaml = YAML(typ="safe")
    try:
        data = yaml.load(text)
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Warning: could not parse {path}: {exc}", file=sys.stderr)
        return []

    if not isinstance(data, dict):
        return []

    found = []
    lora_section = data.get("lora", {})
    if not isinstance(lora_section, dict):
        return []

    for mapping_key, variants in lora_section.items():
        if not isinstance(variants, list):
            continue
        for variant in variants:
            if not isinstance(variant, dict):
                continue
            name = variant.get("name")
            if name and isinstance(name, str):
                found.append((name.strip(), f"lora > {mapping_key}"))

    return found


def build_lora_index(lora_folders: list[Path], extensions: set[str], case_sensitive: bool) -> set[str]:
    index: set[str] = set()
    for folder in lora_folders:
        if not folder.is_dir():
            print(f"Warning: LoRA folder does not exist or is not a directory: {folder}", file=sys.stderr)
            continue
        for f in folder.rglob("*"):
            if f.is_file() and f.suffix.lower() in extensions:
                stem = f.stem if case_sensitive else f.stem.lower()
                index.add(stem)
    return index


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check that LoRAs referenced in wildcard and enmapping files exist on disk.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "-w", "--wildcards",
        nargs="*", type=Path, default=[], metavar="FOLDER",
        help="Wildcard folder(s) to scan.",
    )
    parser.add_argument(
        "-e", "--enmappings",
        nargs="*", type=Path, default=[], metavar="FOLDER",
        help="Enmapping folder(s) to scan.",
    )
    parser.add_argument(
        "-l", "--loras",
        nargs="+", type=Path, required=True, metavar="FOLDER",
        help="Folder(s) to search for LoRA files.",
    )
    parser.add_argument(
        "--extensions",
        nargs="+", default=[".safetensors", ".pt", ".ckpt", ".bin"], metavar="EXT",
        help="LoRA file extensions to recognize (default: .safetensors .pt .ckpt .bin).",
    )
    parser.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Enable case-sensitive name matching (default: case-insensitive).",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Also list LoRAs that were found.",
    )
    args = parser.parse_args()

    if not args.wildcards and not args.enmappings:
        print("Error: specify at least one --wildcards or --enmappings folder.", file=sys.stderr)
        sys.exit(1)

    extensions = {(ext if ext.startswith(".") else f".{ext}").lower() for ext in args.extensions}

    lora_index = build_lora_index(args.loras, extensions, args.case_sensitive)

    # Keyed by lora name; value is a list of (source_file, context) pairs.
    references: dict[str, list[tuple[str, str]]] = defaultdict(list)

    for folder in args.wildcards:
        if not folder.is_dir():
            print(f"Warning: wildcard folder does not exist: {folder}", file=sys.stderr)
            continue
        for path in sorted(folder.rglob("*")):
            if path.is_file() and path.suffix.lower() in WILDCARD_EXTENSIONS:
                for name, ctx in scan_wildcard_file(path):
                    references[name].append((str(path), ctx))

    for folder in args.enmappings:
        if not folder.is_dir():
            print(f"Warning: enmapping folder does not exist: {folder}", file=sys.stderr)
            continue
        for path in sorted(folder.rglob("*")):
            if path.is_file() and path.suffix.lower() in ENMAPPING_EXTENSIONS:
                for name, ctx in scan_enmapping_file(path):
                    references[name].append((str(path), ctx))

    found_count = 0
    missing_count = 0
    dynamic_count = 0

    for lora_name in sorted(references):
        if _is_dynamic(lora_name):
            dynamic_count += 1
            print(f"SKIPPED (dynamic): {lora_name!r}")
            for source_file, location in references[lora_name]:
                print(f"    {source_file}  [{location}]")
            continue

        lookup = lora_name if args.case_sensitive else lora_name.lower()
        if lookup in lora_index:
            found_count += 1
            if args.verbose:
                print(f"OK:      {lora_name}")
        else:
            missing_count += 1
            print(f"MISSING: {lora_name}")
            for source_file, location in references[lora_name]:
                print(f"    {source_file}  [{location}]")

    total = found_count + missing_count
    parts = [f"{total} LoRA reference(s) checked", f"{missing_count} missing"]
    if dynamic_count:
        parts.append(f"{dynamic_count} dynamic (skipped)")
    print(f"\n{', '.join(parts)}.")

    sys.exit(1 if missing_count > 0 else 0)


if __name__ == "__main__":
    main()
