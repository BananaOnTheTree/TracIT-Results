import os
import json
import csv
import math
from collections import defaultdict

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR     = os.path.dirname(os.path.abspath(__file__))
CITYWALK_DIR   = os.path.join(SCRIPT_DIR, "citywalk")
CONREFLECT_DIR = os.path.join(SCRIPT_DIR, "conreflect")

PROJECTS = [
    "hjson-cpp", "json.cpp", "jvar",
    "tinyxml2", "jsonxx", "RSJp-cpp",
    "Jzon", "TinyEXIF", "bitmap",
    "indicators", "polypartition"
]
CONREFLECT_PATHS = {
    "hjson-cpp": os.path.join("hjson-cpp"),
    "json.cpp": os.path.join("json.cpp", "json.cpp"),
    "jvar": os.path.join("jvar"),
    "tinyxml2": os.path.join("tinyxml2", "tinyxml2.cpp"),
    "jsonxx": os.path.join("jsonxx"),
    "RSJp-cpp": os.path.join("RSJp-cpp"),
    "Jzon": os.path.join("Jzon"),
    "TinyEXIF": os.path.join("TinyEXIF"),
    "bitmap": os.path.join("bitmap"),
    "indicators": os.path.join("indicators"),
    "polypartition": os.path.join("polypartition")
}

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_json(path: str):
    with open(path, "rb") as fh:
        return json.loads(fh.read().decode("utf-8", errors="replace"))


def safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def find_citywalk_run(project: str) -> str | None:
    """Return path to the citywalk run directory for the given project."""
    if not os.path.isdir(CITYWALK_DIR):
        return None
    for entry in sorted(os.listdir(CITYWALK_DIR)):
        full = os.path.join(CITYWALK_DIR, entry)
        if not os.path.isdir(full):
            continue
        parts = entry.split("_")
        remainder = "_".join(parts[2:])
        if remainder.startswith(project + "_") or remainder == project:
            return full
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Citywalk token loader
# ─────────────────────────────────────────────────────────────────────────────

def load_citywalk_tokens(project: str) -> dict:
    """
    Returns {
        "per_method": { focal_method: total_tokens, ... },
        "num_methods": int,
        "total_tokens": float,
    }
    Combines root/token_usage.json (generation) and post/token_usage.json (fix).
    """
    run_dir = find_citywalk_run(project)
    if run_dir is None:
        print(f"[WARN] No citywalk run found for: {project}")
        return {"per_method": {}, "num_methods": 0, "total_tokens": 0.0}

    per_method: dict[str, float] = defaultdict(float)

    for rel in ("token_usage.json", os.path.join("post", "token_usage.json")):
        path = os.path.join(run_dir, rel)
        if not os.path.isfile(path):
            print(f"[WARN] Missing: {path}")
            continue
        try:
            entries = load_json(path)
        except Exception as e:
            print(f"[WARN] Could not read {path}: {e}")
            continue
        for entry in entries:
            method = entry.get("focal_method")
            tokens = safe_float(entry.get("total_tokens"))
            if method and tokens is not None:
                per_method[method] += tokens

    total = sum(per_method.values())
    return {
        "per_method": dict(per_method),
        "num_methods": len(per_method),
        "total_tokens": total,
    }


# ─────────────────────────────────────────────────────────────────────────────
# ConReflect token loader
# ─────────────────────────────────────────────────────────────────────────────

def iter_method_dirs(project_path: str):
    """Yield directories that contain at least one non-non_reflect coverage JSON."""
    for root, dirs, files in os.walk(project_path):
        if any(
            f.startswith("coverage_") and f.endswith(".json") and "non_reflect" not in f
            for f in files
        ):
            yield root


def load_conreflect_tokens(project: str) -> dict:
    """
    Returns {
        "num_methods": int,
        "total_tokens": float,
    }
    Reads tokenUsed from coverage_<func>.json for each method directory.
    """
    rel_path = CONREFLECT_PATHS.get(project)
    if rel_path is None:
        print(f"[WARN] No ConReflect path for: {project}")
        return {"num_methods": 0, "total_tokens": 0.0}

    full_path = os.path.join(CONREFLECT_DIR, rel_path)
    if not os.path.isdir(full_path):
        print(f"[WARN] ConReflect path not found: {full_path}")
        return {"num_methods": 0, "total_tokens": 0.0}

    num_methods = 0
    total_tokens = 0.0

    for method_dir in iter_method_dirs(full_path):
        func_name = os.path.basename(method_dir)
        cov_path = os.path.join(method_dir, f"coverage_{func_name}.json")

        if not os.path.isfile(cov_path):
            candidates = [
                f for f in os.listdir(method_dir)
                if f.startswith("coverage_") and "non_reflect" not in f and f.endswith(".json")
            ]
            if not candidates:
                continue
            cov_path = os.path.join(method_dir, candidates[0])

        try:
            raw = open(cov_path, "rb").read()
            if not raw.strip():
                continue
            data = json.loads(raw.decode("utf-8", errors="replace"))
            tok = safe_float(data.get("tokenUsed"))
            if tok is not None:
                num_methods += 1
                total_tokens += tok
        except Exception as e:
            print(f"[WARN] Could not read {cov_path}: {e}")

    return {"num_methods": num_methods, "total_tokens": total_tokens}


# ─────────────────────────────────────────────────────────────────────────────
# Build comparison
# ─────────────────────────────────────────────────────────────────────────────

def build_comparison() -> dict:
    result = {}

    cw_all_methods = 0
    cw_all_tokens  = 0.0
    cr_all_methods = 0
    cr_all_tokens  = 0.0

    for proj in PROJECTS:
        cw = load_citywalk_tokens(proj)
        cr = load_conreflect_tokens(proj)

        cw_all_methods += cw["num_methods"]
        cw_all_tokens  += cw["total_tokens"]
        cr_all_methods += cr["num_methods"]
        cr_all_tokens  += cr["total_tokens"]

        result[proj] = {"citywalk": cw, "conreflect": cr}

        print(f"  {proj:12s}  "
              f"Citywalk: {cw['num_methods']:3d} methods, {cw['total_tokens']:>12,.0f} tokens  |  "
              f"ConReflect: {cr['num_methods']:3d} methods, {cr['total_tokens']:>12,.0f} tokens")

    result["Overall"] = {
        "citywalk":   {"num_methods": cw_all_methods, "total_tokens": cw_all_tokens},
        "conreflect": {"num_methods": cr_all_methods, "total_tokens": cr_all_tokens},
    }
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Formatting helpers
# ─────────────────────────────────────────────────────────────────────────────

def fmt_avg(total: float, count: int) -> str:
    if count == 0:
        return "N/A"
    return f"{total / count:,.1f}"


def fmt_total(total: float) -> str:
    return f"{total:,.0f}"


# ─────────────────────────────────────────────────────────────────────────────
# Table printer
# ─────────────────────────────────────────────────────────────────────────────

def print_table(comparison: dict):
    col_order = PROJECTS + ["Overall"]
    col_w     = 18
    label_w   = 22
    total_w   = label_w + col_w * len(col_order)

    print(f"\n{'═' * total_w}")
    print("  Average Token Usage per Method – Citywalk vs ConReflect")
    print(f"{'═' * total_w}")
    print(f"{'':>{label_w}}" + "".join(f"{c:>{col_w}}" for c in col_order))
    print("─" * total_w)

    # ── Avg Tokens / Method ──
    for tool, tag in [("citywalk", "Citywalk"), ("conreflect", "ConReflect")]:
        row = f"{f'Avg Tokens / Method ({tag})':<{label_w}}"
        for proj in col_order:
            d = comparison[proj][tool]
            row += f"{fmt_avg(d['total_tokens'], d['num_methods']):>{col_w}}"
        print(row)

    # ── Delta ──
    print("─" * total_w)
    row = f"{'Δ (CR − CW)':<{label_w}}"
    for proj in col_order:
        cw = comparison[proj]["citywalk"]
        cr = comparison[proj]["conreflect"]
        if cw["num_methods"] > 0 and cr["num_methods"] > 0:
            cw_avg = cw["total_tokens"] / cw["num_methods"]
            cr_avg = cr["total_tokens"] / cr["num_methods"]
            delta  = cr_avg - cw_avg
            sign   = "+" if delta >= 0 else ""
            cell   = f"{sign}{delta:,.1f}"
        else:
            cell = "N/A"
        row += f"{cell:>{col_w}}"
    print(row)

    print("─" * total_w)



# ─────────────────────────────────────────────────────────────────────────────
# CSV export
# ─────────────────────────────────────────────────────────────────────────────

def export_csv(output_file: str, comparison: dict):
    col_order = PROJECTS + ["Overall"]

    rows = [
        ["Metric"] + col_order,
    ]

    for tool, tag in [("citywalk", "Citywalk"), ("conreflect", "ConReflect")]:
        row = [f"Avg Tokens / Method ({tag})"]
        for proj in col_order:
            d = comparison[proj][tool]
            row.append(fmt_avg(d["total_tokens"], d["num_methods"]))
        rows.append(row)

    # Delta row
    delta_row = ["Δ (ConReflect − Citywalk)"]
    for proj in col_order:
        cw = comparison[proj]["citywalk"]
        cr = comparison[proj]["conreflect"]
        if cw["num_methods"] > 0 and cr["num_methods"] > 0:
            delta = (cr["total_tokens"] / cr["num_methods"]) - (cw["total_tokens"] / cw["num_methods"])
            sign  = "+" if delta >= 0 else ""
            delta_row.append(f"{sign}{delta:,.1f}")
        else:
            delta_row.append("N/A")
    rows.append(delta_row)


    with open(output_file, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerows(rows)

    print(f"\nCSV saved to: {output_file}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Citywalk  dir : {CITYWALK_DIR}")
    print(f"ConReflect dir: {CONREFLECT_DIR}\n")

    comparison = build_comparison()

    print_table(comparison)

    output_dir = os.path.join(SCRIPT_DIR, "output")
    os.makedirs(output_dir, exist_ok=True)

    export_csv(
        os.path.join(output_dir, "avg_token_usage_comparison.csv"),
        comparison,
    )

    print("\nDone.")

