"""
Compares the model classes listed in the host's supported models file against
the model definitions in ppp_config.yaml.defaults for a given host.

The relative path to the supported models file for each host is read from the
comments preceding the `models:` key in the defaults file.
"""

import argparse
import ast
import re
import sys
from pathlib import Path

import yaml

DEFAULT_CONFIG = Path(__file__).parent.parent / "ppp_config.yaml.defaults"
SUPPORTED_HOSTS = {"comfyui", "reforge", "forge", "forgeneo", "sdnext"}


def parse_host_file_paths(config_text: str) -> dict[str, str]:
    """Extract the host->relative-path mapping from the comments above `models:`."""
    paths: dict[str, str] = {}
    in_block = False

    for line in config_text.splitlines():
        stripped = line.strip()

        if re.match(r"^#\s*Check supported models for each host in:", stripped):
            in_block = True
            continue

        if in_block:
            # Lines like: "#   host: some/relative/path.py"  or "#   host:"
            m = re.match(r"^#\s*(\w+)\s*:\s*(.*)", stripped)
            if m:
                host, rel_path = m.group(1), m.group(2).strip()
                if rel_path:
                    paths[host] = rel_path
            else:
                # First non-matching line ends the block
                if not stripped.startswith("#"):
                    break

    return paths


def extract_pipeline_classes(shared_items_path: Path) -> list[tuple[str, None]]:
    """Parse shared_items.py and return unique diffusers pipeline class names from the pipelines dict."""
    source = shared_items_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(shared_items_path))

    class_names: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "pipelines" for t in node.targets):
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        for value in node.value.values:
            # Match: getattr(diffusers, 'ClassName', None)
            if not isinstance(value, ast.Call):
                continue
            if not (isinstance(value.func, ast.Name) and value.func.id == "getattr"):
                continue
            if len(value.args) < 2:
                continue
            cls_arg = value.args[1]
            if isinstance(cls_arg, ast.Constant) and isinstance(cls_arg.value, str):
                class_names.add(cls_arg.value)

    return [(name, None) for name in sorted(class_names)]


def extract_model_classes(supported_models_path: Path) -> list[tuple[str, str | None]]:
    """Parse a supported_models.py and return (class_name, parent_class) pairs in the `models` list(s)."""
    source = supported_models_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(supported_models_path))

    class_parents = _build_class_parents(tree)
    class_names: list[str] = []

    for node in ast.walk(tree):
        # models = [ClassA, ClassB, ...]
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "models":
                    class_names.extend(_names_from_list(node.value))

        # models += [ClassA, ...]
        elif isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "models":
                class_names.extend(_names_from_list(node.value))

    sentinels = _find_sentinels(class_parents, set(class_names))

    # Only keep classes that ultimately descend from a sentinel base.
    # Display parent is None when the immediate parent is a sentinel (class appears as a root).
    return [
        (name, None if class_parents.get(name) in sentinels else class_parents.get(name))
        for name in class_names
        if _has_base_ancestor(name, class_parents, sentinels)
    ]


def _build_class_parents(tree: ast.AST) -> dict[str, str | None]:
    """Return a mapping of class name -> raw parent name."""
    parents: dict[str, str | None] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        parent: str | None = None
        for base in node.bases:
            if isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name):
                parent = f"{base.value.id}.{base.attr}"
            elif isinstance(base, ast.Name):
                parent = base.id
            break  # only the first base matters
        parents[node.name] = parent
    return parents


def _find_sentinels(parents: dict[str, str | None], model_class_names: set[str]) -> set[str]:
    """Detect root base class names: external refs (dotted) or local classes with no parent not in the models list."""
    sentinels: set[str] = set()
    for parent in parents.values():
        if parent is None:
            continue
        if "." in parent:  # external reference, e.g. supported_models_base.BASE
            sentinels.add(parent)
        elif parent in parents and parents[parent] is None and parent not in model_class_names:
            sentinels.add(parent)  # local class with no parent that is not itself a listed model
    return sentinels


def _has_base_ancestor(name: str, parents: dict[str, str | None], sentinels: set[str]) -> bool:
    visited: set[str] = set()
    current = parents.get(name)
    while current is not None:
        if current in sentinels:
            return True
        if current in visited:
            return False  # cycle guard
        visited.add(current)
        current = parents.get(current)
    return False


def _names_from_list(node: ast.expr) -> list[str]:
    if not isinstance(node, ast.List):
        return []
    return [elt.id for elt in node.elts if isinstance(elt, ast.Name)]


def _topo_sort_alpha(classes: list[tuple[str, str | None]]) -> list[tuple[str, str | None]]:
    """Sort classes so each parent immediately precedes its children, with alphabetical ordering at every level."""
    class_set = {name for name, _ in classes}
    parent_of = {name: parent for name, parent in classes}

    children_of: dict[str, list[str]] = {name: [] for name, _ in classes}
    roots: list[str] = []
    for name, parent in classes:
        if parent and parent in class_set:
            children_of[parent].append(name)
        else:
            roots.append(name)

    roots.sort()
    for children in children_of.values():
        children.sort()

    result: list[tuple[str, str | None]] = []

    def visit(name: str) -> None:
        result.append((name, parent_of[name]))
        for child in children_of[name]:
            visit(child)

    for root in roots:
        visit(root)

    return result


def build_class_to_model_map(config: dict, host: str) -> dict[str, str]:
    """Return a mapping of class name -> model key for the given host."""
    mapping: dict[str, str] = {}
    models_config = config.get("models", {})

    for model_key, model_data in models_config.items():
        if not isinstance(model_data, dict):
            continue
        detect = model_data.get("detect", {})
        if not isinstance(detect, dict):
            continue
        host_detect = detect.get(host)
        if not isinstance(host_detect, dict):
            continue
        classes = host_detect.get("class", [])
        if isinstance(classes, list):
            for cls in classes:
                mapping[cls] = model_key

    return mapping


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare host model classes against ppp_config.yaml.defaults mappings."
    )
    parser.add_argument(
        "host",
        help="Host kind to compare against (e.g. comfyui, reforge, forge, ...).",
    )
    parser.add_argument(
        "root",
        metavar="ROOT_FOLDER",
        type=Path,
        help="Root folder of the host UI installation.",
    )
    parser.add_argument(
        "--config",
        metavar="CONFIG_FILE",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Path to ppp_config.yaml.defaults (default: {DEFAULT_CONFIG}).",
    )
    args = parser.parse_args()

    root: Path = args.root
    host: str = args.host
    config_path: Path = args.config

    if host not in SUPPORTED_HOSTS:
        parser.error(f"Host '{host}' is not supported by this script. Supported hosts: {', '.join(sorted(SUPPORTED_HOSTS))}")

    if not root.is_dir():
        parser.error(f"ROOT_FOLDER does not exist or is not a directory: {root}")

    if not config_path.exists():
        parser.error(f"Config file not found: {config_path}")

    config_text = config_path.read_text(encoding="utf-8")
    host_paths = parse_host_file_paths(config_text)

    known_hosts = list((yaml.safe_load(config_text).get("hosts") or {}).keys())
    if host not in known_hosts:
        print(f"Warning: '{host}' is not a recognized host. Known hosts: {', '.join(known_hosts)}")

    rel_path = host_paths.get(host)
    if not rel_path:
        print(f"Error: no supported-models file path defined for host '{host}' in {config_path.name}.")
        sys.exit(1)

    supported_models_path = root / rel_path.replace("\\", "/")
    if not supported_models_path.exists():
        print(f"Error: file not found: {supported_models_path}")
        sys.exit(1)

    config = yaml.safe_load(config_text)
    if host == "sdnext":
        model_classes: list[tuple[str, str | None]] = extract_pipeline_classes(supported_models_path)
    else:
        model_classes = extract_model_classes(supported_models_path)
    if not model_classes:
        print("No model classes found in the models list.")
        sys.exit(1)

    model_classes = _topo_sort_alpha(model_classes)

    class_to_model = build_class_to_model_map(config, host)

    class_set = {cls for cls, _ in model_classes}
    parent_of_display = {cls: parent for cls, parent in model_classes}
    depth_cache: dict[str, int] = {}

    def get_depth(name: str) -> int:
        if name not in depth_cache:
            p = parent_of_display.get(name)
            depth_cache[name] = 0 if (not p or p not in class_set) else 1 + get_depth(p)
        return depth_cache[name]

    # Build display labels: "ClassName" or "ClassName (Parent)", indented by depth
    labels = [f"{cls} ({parent})" if parent else cls for cls, parent in model_classes]
    depths = [get_depth(cls) for cls, _ in model_classes]
    col_width = max(d * 2 + len(lbl) for d, lbl in zip(depths, labels))
    missing: list[str] = []

    print(f"Model classes in '{supported_models_path}' vs '{config_path.name}' (host: {host})")
    print("-" * (col_width + 42))

    for (cls, _parent), label, depth in zip(model_classes, labels, depths):
        indented = "  " * depth + label
        model = class_to_model.get(cls)
        if model:
            print(f"{indented:<{col_width}}  ->  {model}")
        else:
            missing.append((cls, _parent))
            print(f"{indented:<{col_width}}  ->  WARNING: not mapped")

    print("-" * (col_width + 42))
    print(f"Total: {len(model_classes)} classes, {len(missing)} unmapped")

    if missing:
        print("\nUnmapped classes:")
        for cls, parent in missing:
            label = f"{cls} ({parent})" if parent else cls
            print(f"  - {label}")


if __name__ == "__main__":
    main()
