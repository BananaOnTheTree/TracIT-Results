"""
Ablation Study Table - Refactored (Absolute Counts & Strict Ground Truth)
====================
"""

import csv
import json
import math
import os

# ---------------------------------------------------------------------------
# Configuration & Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
BASE_DIR    = os.path.join(SCRIPT_DIR, "conreflect")
NO_CTX_DIR  = os.path.join(SCRIPT_DIR, "no_context")
NO_COT_DIR  = os.path.join(SCRIPT_DIR, "no_cot")
OUTPUT_DIR  = os.path.join(SCRIPT_DIR, "output")

PROJECTS = {
    "hjson-cpp": os.path.join("hjson-cpp"),
    "json.cpp":  os.path.join("json.cpp", "json.cpp"),
    "jvar":      os.path.join("jvar"),
    "tinyxml2":  os.path.join("tinyxml2", "tinyxml2.cpp"),
    "jsonxx":    os.path.join("jsonxx"),
    "RSJp-cpp":  os.path.join("RSJp-cpp", "RSJparser.tcc"),
    "Jzon":      os.path.join("Jzon", "Jzon.cpp"),
    "TinyEXIF": os.path.join("TinyEXIF"),
    "bitmap": os.path.join("bitmap"),
    "indicators": os.path.join("indicators"),
    "polypartition": os.path.join("polypartition", "polypartition.cpp"),
}

VARIANTS = [
    ("overall",        "Overall"),
    ("no_iteration",   "w/o Iteration"),
    ("non_reflect",    "w/o Reflect"),
    ("no_context",     "w/o Context"),
    ("no_cot",         "w/o CoT"),
]

ANOMALIES = []

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path: str):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return json.load(fh)
    except Exception:
        return None

def to_float(val):
    if val is None: return 0.0
    try:
        f = float(val)
        return 0.0 if math.isnan(f) else f
    except (TypeError, ValueError):
        return 0.0

def log_anomaly(msg: str):
    ANOMALIES.append(msg)

def map_project_functions(project_root: str) -> dict[str, str]:
    mapping = {}
    if not os.path.isdir(project_root): return mapping
    for root, dirs, files in os.walk(project_root):
        if any(f.endswith(".json") for f in files):
            mapping[os.path.basename(root)] = root
    return mapping

def normalize_project_name(name: str) -> str:
    return name.replace("_", "").replace("-", "").lower()

def resolve_project_root(base_dir: str, proj_name: str, rel_path: str | None = None) -> str:
    candidates = []
    if rel_path:
        candidates.append(os.path.join(base_dir, rel_path))
    candidates.append(os.path.join(base_dir, proj_name))

    for path in candidates:
        if os.path.isdir(path):
            return path

    if not os.path.isdir(base_dir):
        return candidates[0]

    target = normalize_project_name(proj_name)
    for entry in os.listdir(base_dir):
        full = os.path.join(base_dir, entry)
        if os.path.isdir(full) and normalize_project_name(entry) == target:
            return full

    return candidates[0]

def calc_pct(cov: int, tot: int, is_branch: bool = False, stmt_tot: int = 0) -> float:
    if tot > 0: return (cov / tot) * 100.0
    if is_branch and stmt_tot > 0: return 100.0
    return 0.0

# ---------------------------------------------------------------------------
# Core Loaders
# ---------------------------------------------------------------------------

def get_absolute_coverage(func_dir: str, file_prefix: str, exclude: str | None):
    if not func_dir or not os.path.isdir(func_dir):
        return 0, 0, 0, 0

    candidates = [f for f in os.listdir(func_dir) if f.startswith(file_prefix) and f.endswith(".json")]
    if exclude:
        candidates = [f for f in candidates if exclude not in f]

    if not candidates:
        return 0, 0, 0, 0

    data = load_json(os.path.join(func_dir, sorted(candidates)[0]))
    if not data:
        return 0, 0, 0, 0

    s_tot = int(data.get("totalStatements", 0) or 0)
    b_tot = int(data.get("totalBranches", 0) or 0)

    stmt_pct = to_float(data.get("stmtCov"))
    if data.get("stmtCov") is None:
        src_s_cov = int(data.get("visitedStatements", 0) or 0)
        stmt_pct = (src_s_cov / s_tot) * 100.0 if s_tot > 0 else 0.0

    branch_pct = to_float(data.get("branchCov"))
    if data.get("branchCov") is None:
        src_b_cov = int(data.get("visitedBranches", 0) or 0)
        branch_pct = (src_b_cov / b_tot) * 100.0 if b_tot > 0 else 0.0

    s_cov = round((stmt_pct / 100.0) * s_tot)
    b_cov = round((branch_pct / 100.0) * b_tot)

    if s_cov == 0:
        b_cov = 0

    return s_cov, s_tot, b_cov, b_tot

def get_log_coverage(func_dir: str):
    if not func_dir or not os.path.isdir(func_dir):
        return 0, 0, 0, 0

    cov_candidates = [
        f for f in os.listdir(func_dir)
        if f.startswith("coverage_") and "non_reflect" not in f and f.endswith(".json")
    ]
    if not cov_candidates:
        return 0, 0, 0, 0

    cov_data = load_json(os.path.join(func_dir, sorted(cov_candidates)[0])) or {}
    s_tot = int(cov_data.get("totalStatements", 0) or 0)
    b_tot = int(cov_data.get("totalBranches", 0) or 0)

    candidates = [f for f in os.listdir(func_dir) if f.endswith("_ai_0_logs.json")]
    if not candidates:
        return 0, s_tot, 0, b_tot

    data = load_json(os.path.join(func_dir, candidates[0]))
    if not data:
        return 0, s_tot, 0, b_tot

    if isinstance(data, dict) and data.get("compile_error"):
        return 0, s_tot, 0, b_tot
    if isinstance(data, list) and any(e.get("compile_error") for e in data if isinstance(e, dict)):
        return 0, s_tot, 0, b_tot

    s_cov = round((to_float(data.get("statementCoverage")) / 100.0) * s_tot)
    b_cov = round((to_float(data.get("branchCoverage")) / 100.0) * b_tot)

    if s_cov == 0:
        b_cov = 0
    return s_cov, s_tot, b_cov, b_tot

# ---------------------------------------------------------------------------
# Data Building (Strict Master Ground Truth)
# ---------------------------------------------------------------------------

def build_ablation_data():
    master_gt = {}
    stats = {var_key: {proj: {"s_cov": 0, "s_tot": 0, "b_cov": 0, "b_tot": 0} for proj in PROJECTS} for var_key, _ in VARIANTS}

    for proj_name, rel_path in PROJECTS.items():
        base_path = resolve_project_root(BASE_DIR, proj_name, rel_path)
        no_ctx_path = resolve_project_root(NO_CTX_DIR, proj_name)
        no_cot_path = resolve_project_root(NO_COT_DIR, proj_name)

        map_base = map_project_functions(base_path)
        map_no_ctx = map_project_functions(no_ctx_path)
        map_no_cot = map_project_functions(no_cot_path)

        master_gt[proj_name] = {}

        # Use union of methods across all ablations; each variant contributes with its own totals.
        all_funcs = set(map_base.keys()) | set(map_no_ctx.keys()) | set(map_no_cot.keys())

        for func_name in sorted(all_funcs):
            for var_key, _ in VARIANTS:
                s_cov, s_tot, b_cov, b_tot = 0, 0, 0, 0

                if var_key == "overall":
                    s_cov, s_tot, b_cov, b_tot = get_absolute_coverage(map_base.get(func_name), "coverage_", "non_reflect")
                elif var_key == "non_reflect":
                    s_cov, s_tot, b_cov, b_tot = get_absolute_coverage(map_base.get(func_name), "coverage_non_reflect_", None)
                elif var_key == "no_iteration":
                    s_cov, s_tot, b_cov, b_tot = get_log_coverage(map_base.get(func_name))
                elif var_key == "no_context":
                    s_cov, s_tot, b_cov, b_tot = get_absolute_coverage(map_no_ctx.get(func_name), "coverage_", "non_reflect")
                elif var_key == "no_cot":
                    s_cov, s_tot, b_cov, b_tot = get_absolute_coverage(map_no_cot.get(func_name), "coverage_", "non_reflect")

                stats[var_key][proj_name]["s_cov"] += s_cov
                stats[var_key][proj_name]["s_tot"] += s_tot
                stats[var_key][proj_name]["b_cov"] += b_cov
                stats[var_key][proj_name]["b_tot"] += b_tot

    return stats, master_gt

# ---------------------------------------------------------------------------
# Printers & Exporters
# ---------------------------------------------------------------------------

def get_overall_total(stats, var_key):
    t_scov = sum(stats[var_key][p]["s_cov"] for p in PROJECTS)
    t_stot = sum(stats[var_key][p]["s_tot"] for p in PROJECTS)
    t_bcov = sum(stats[var_key][p]["b_cov"] for p in PROJECTS)
    t_btot = sum(stats[var_key][p]["b_tot"] for p in PROJECTS)
    return t_scov, t_stot, t_bcov, t_btot

def build_tables(stats):
    col_names = list(PROJECTS.keys()) + ["Overall"]

    for metric, is_branch in [("stmt", False), ("branch", True)]:
        print(f"\n{'='*80}")
        print(f"  Ablation Study – {'Branch' if is_branch else 'Statement'} Coverage (%) - Absolute Weighted")
        print(f"{'='*80}")

        header = f"{'Configuration':<20}" + "".join(f"{c:>12}" for c in col_names)
        print(header)
        print("-" * len(header))

        base_pct = {}
        for proj in PROJECTS:
            d = stats["overall"][proj]
            cov = d["b_cov"] if is_branch else d["s_cov"]
            tot = d["b_tot"] if is_branch else d["s_tot"]
            base_pct[proj] = calc_pct(cov, tot, is_branch, d["s_tot"])

        t_scov, t_stot, t_bcov, t_btot = get_overall_total(stats, "overall")
        t_cov, t_tot = (t_bcov, t_btot) if is_branch else (t_scov, t_stot)
        base_pct["Overall"] = calc_pct(t_cov, t_tot, is_branch, t_stot)

        for var_key, row_label in VARIANTS:
            row_vals = []
            is_delta = (var_key != "overall")

            for proj in PROJECTS:
                d = stats[var_key][proj]
                cov = d["b_cov"] if is_branch else d["s_cov"]
                tot = d["b_tot"] if is_branch else d["s_tot"]
                pct = calc_pct(cov, tot, is_branch, d["s_tot"])

                if is_delta:
                    delta = pct - base_pct[proj]
                    row_vals.append(f"{delta:>+11.2f}%")
                else:
                    row_vals.append(f"{pct:>11.2f}%")

            t_scov, t_stot, t_bcov, t_btot = get_overall_total(stats, var_key)
            t_cov, t_tot = (t_bcov, t_btot) if is_branch else (t_scov, t_stot)
            overall_pct = calc_pct(t_cov, t_tot, is_branch, t_stot)

            if is_delta:
                delta = overall_pct - base_pct["Overall"]
                row_vals.append(f"{delta:>+11.2f}%")
            else:
                row_vals.append(f"{overall_pct:>11.2f}%")

            print(f"{row_label:<20}" + "".join(row_vals))

def export_csv(stats, output_file: str):
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        col_names = list(PROJECTS.keys()) + ["Overall"]

        for metric, is_branch in [("stmt", False), ("branch", True)]:
            writer.writerow([f"{'Branch' if is_branch else 'Statement'} Coverage (%)"] + col_names)

            base_pct = {}
            for proj in PROJECTS:
                d = stats["overall"][proj]
                cov, tot = (d["b_cov"], d["b_tot"]) if is_branch else (d["s_cov"], d["s_tot"])
                base_pct[proj] = calc_pct(cov, tot, is_branch, d["s_tot"])

            t_scov, t_stot, t_bcov, t_btot = get_overall_total(stats, "overall")
            t_cov, t_tot = (t_bcov, t_btot) if is_branch else (t_scov, t_stot)
            base_pct["Overall"] = calc_pct(t_cov, t_tot, is_branch, t_stot)

            for var_key, row_label in VARIANTS:
                is_delta = (var_key != "overall")
                cells = [row_label]

                for proj in PROJECTS:
                    d = stats[var_key][proj]
                    cov, tot = (d["b_cov"], d["b_tot"]) if is_branch else (d["s_cov"], d["s_tot"])
                    pct = calc_pct(cov, tot, is_branch, d["s_tot"])

                    if is_delta:
                        cells.append(f"{(pct - base_pct[proj]):.2f}")
                    else:
                        cells.append(f"{pct:.2f}")

                t_scov, t_stot, t_bcov, t_btot = get_overall_total(stats, var_key)
                t_cov, t_tot = (t_bcov, t_btot) if is_branch else (t_scov, t_stot)
                overall_pct = calc_pct(t_cov, t_tot, is_branch, t_stot)

                if is_delta:
                    cells.append(f"{(overall_pct - base_pct['Overall']):.2f}")
                else:
                    cells.append(f"{overall_pct:.2f}")

                writer.writerow(cells)
            writer.writerow([])
    print(f"\n  CSV saved to: {output_file}")

# ---------------------------------------------------------------------------
# Method Diff Logic
# ---------------------------------------------------------------------------

def log_method_diffs(master_gt, output_csv: str):
    rows = []
    for proj_name, rel_path in PROJECTS.items():
        base_path = os.path.join(BASE_DIR, rel_path)
        no_ctx_path = os.path.join(NO_CTX_DIR, rel_path)

        map_base = map_project_functions(base_path)
        map_no_ctx = map_project_functions(no_ctx_path)

        only_base = sorted(set(map_base.keys()) - set(map_no_ctx.keys()))
        only_no_ctx = sorted(set(map_no_ctx.keys()) - set(map_base.keys()))

        for func in only_base:
            rows.append({"project": proj_name, "method": func, "present_in": "conreflect", "missing_in": "no_context"})
        for func in only_no_ctx:
            rows.append({"project": proj_name, "method": func, "present_in": "no_context", "missing_in": "conreflect"})

    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["project", "method", "present_in", "missing_in"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Method diff CSV -> {output_csv} ({len(rows)} rows)")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Building ablation data...")
    stats, master_gt = build_ablation_data()

    # log_method_diffs(master_gt, os.path.join(OUTPUT_DIR, "ablation_no_context_method_diff.csv"))

    build_tables(stats)

    export_csv(stats, os.path.join(OUTPUT_DIR, "ablation_study.csv"))
    print("\nDone.")
