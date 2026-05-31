import csv
import json
import math
import os
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")

PROJECTS = [
    "hjson-cpp", "json.cpp", "jvar",
    "tinyxml2", "jsonxx", "RSJp-cpp",
    "Jzon", "TinyEXIF", "bitmap",
    "indicators", "polypartition",
]

# Include all non-citywalk tool roots used in this workspace.
TOOLS: list[tuple[str, str]] = [
    ("conreflect", "ConReflect"),
    ("coverup", "CoverUp"),
    ("gpt4_1nano", "GPT-4.1-Nano"),
    ("deepseek_v3_2", "DeepSeek-V3.2"),
    ("haiku4_5", "Haiku-4.5"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_name(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def safe_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        out = float(value)
        return None if math.isnan(out) else out
    except (TypeError, ValueError):
        return None


def load_json(path: str):
    with open(path, "rb") as fh:
        return json.loads(fh.read().decode("utf-8", errors="replace"))


def find_project_root(tool_dir: str, project: str) -> Optional[str]:
    if not os.path.isdir(tool_dir):
        return None

    target = normalize_name(project)
    exact_matches = []
    fuzzy_matches = []

    for entry in os.listdir(tool_dir):
        full = os.path.join(tool_dir, entry)
        if not os.path.isdir(full):
            continue
        norm_entry = normalize_name(entry)
        if norm_entry == target:
            exact_matches.append(full)
        elif target in norm_entry or norm_entry in target:
            fuzzy_matches.append(full)

    if exact_matches:
        return sorted(exact_matches)[0]
    if fuzzy_matches:
        return sorted(fuzzy_matches)[0]
    return None


def iter_method_dirs(project_root: str):
    for root, _dirs, files in os.walk(project_root):
        if any(
            f.startswith("coverage_") and f.endswith(".json") and "non_reflect" not in f
            for f in files
        ):
            yield root


def resolve_coverage_path(method_dir: str) -> Optional[str]:
    func_name = os.path.basename(method_dir)
    default = os.path.join(method_dir, f"coverage_{func_name}.json")
    if os.path.isfile(default):
        return default

    candidates = [
        f for f in os.listdir(method_dir)
        if f.startswith("coverage_") and f.endswith(".json") and "non_reflect" not in f
    ]
    if not candidates:
        return None
    return os.path.join(method_dir, sorted(candidates)[0])


def fmt_avg(total: float, count: int) -> str:
    if count == 0:
        return "N/A"
    return f"{(total / count):,.2f}"


# ---------------------------------------------------------------------------
# Core loaders
# ---------------------------------------------------------------------------

def load_tool_project_metrics(tool_key: str, project: str) -> dict:
    tool_dir = os.path.join(SCRIPT_DIR, tool_key)
    project_root = find_project_root(tool_dir, project)

    if project_root is None:
        return {
            "token_methods": 0,
            "runtime_methods": 0,
            "total_tokens": 0.0,
            "total_runtime": 0.0,
        }

    token_methods = 0
    runtime_methods = 0
    total_tokens = 0.0
    total_runtime = 0.0

    for method_dir in iter_method_dirs(project_root):
        cov_path = resolve_coverage_path(method_dir)
        if cov_path is None:
            continue

        try:
            data = load_json(cov_path)
        except Exception as exc:
            print(f"[WARN] Could not read {cov_path}: {exc}")
            continue

        token_used = safe_float(data.get("tokenUsed"))
        time_used = safe_float(data.get("timeUsed"))

        if token_used is not None:
            token_methods += 1
            total_tokens += token_used
        if time_used is not None:
            runtime_methods += 1
            total_runtime += time_used

    return {
        "token_methods": token_methods,
        "runtime_methods": runtime_methods,
        "total_tokens": total_tokens,
        "total_runtime": total_runtime,
    }


def build_comparison() -> dict:
    comparison = {}

    for tool_key, _tool_label in TOOLS:
        comparison[tool_key] = {}
        all_token_methods = 0
        all_runtime_methods = 0
        all_tokens = 0.0
        all_runtime = 0.0

        for project in PROJECTS:
            metrics = load_tool_project_metrics(tool_key, project)
            comparison[tool_key][project] = metrics

            all_token_methods += metrics["token_methods"]
            all_runtime_methods += metrics["runtime_methods"]
            all_tokens += metrics["total_tokens"]
            all_runtime += metrics["total_runtime"]

        comparison[tool_key]["Overall"] = {
            "token_methods": all_token_methods,
            "runtime_methods": all_runtime_methods,
            "total_tokens": all_tokens,
            "total_runtime": all_runtime,
        }

    return comparison


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_table(comparison: dict):
    columns = PROJECTS + ["Overall"]
    label_width = 34
    col_width = 14
    total_width = label_width + col_width * len(columns)

    print("\n" + "=" * total_width)
    print("Average Runtime + Token Usage per Method (Non-Citywalk Tools)")
    print("=" * total_width)
    print(f"{'':<{label_width}}" + "".join(f"{c:>{col_width}}" for c in columns))
    print("-" * total_width)

    for tool_key, tool_label in TOOLS:
        runtime_row = f"Avg Runtime / Method ({tool_label})"
        token_row = f"Avg Tokens / Method ({tool_label})"

        runtime_line = f"{runtime_row:<{label_width}}"
        token_line = f"{token_row:<{label_width}}"

        for project in columns:
            metrics = comparison[tool_key][project]
            runtime_line += f"{fmt_avg(metrics['total_runtime'], metrics['runtime_methods']):>{col_width}}"
            token_line += f"{fmt_avg(metrics['total_tokens'], metrics['token_methods']):>{col_width}}"

        print(runtime_line)
        print(token_line)
        print("-" * total_width)


def export_csv(path: str, comparison: dict):
    columns = PROJECTS + ["Overall"]
    rows = [["Metric"] + columns]

    for tool_key, tool_label in TOOLS:
        runtime_row = [f"Avg Runtime / Method ({tool_label})"]
        token_row = [f"Avg Tokens / Method ({tool_label})"]

        for project in columns:
            metrics = comparison[tool_key][project]
            runtime_row.append(fmt_avg(metrics["total_runtime"], metrics["runtime_methods"]))
            token_row.append(fmt_avg(metrics["total_tokens"], metrics["token_methods"]))

        rows.append(runtime_row)
        rows.append(token_row)

    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerows(rows)

    print(f"CSV saved to: {path}")


if __name__ == "__main__":
    print("Building non-citywalk runtime/token comparison...")
    data = build_comparison()

    print_table(data)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_csv = os.path.join(OUTPUT_DIR, "avg_runtime_and_token_non_citywalk.csv")
    export_csv(out_csv, data)

    print("Done.")

