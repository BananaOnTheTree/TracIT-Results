import os
import json
import math

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "conreflect")

PROJECTS = {
    "hjson-cpp": os.path.join("hjson-cpp"),
    "json.cpp":  os.path.join("json.cpp"),
    "jvar":      os.path.join("jvar"),
    "tinyxml2":  os.path.join("tinyxml2"),
    "jsonxx":    os.path.join("jsonxx"),
    "rjsp":      os.path.join("RSJp-cpp"),
    "jzon":      os.path.join("jzon"),
    "TinyEXIF": os.path.join("TinyEXIF"),
    "bitmap": os.path.join("bitmap"),
    "indicators": os.path.join("indicators"),
    "polypartition": os.path.join("polypartition"),
}

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_json(path: str):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return json.load(fh)


def safe_float(val):
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def iter_function_dirs(project_path: str):
    """
    Walk exactly two levels: project_path / <file_dir> / <method_dir>
    Yields each method_dir that contains a coverage_*.json file.
    """
    for file_dir in os.scandir(project_path):
        if not file_dir.is_dir():
            continue
        for method_dir in os.scandir(file_dir.path):
            if not method_dir.is_dir():
                continue
            files = os.listdir(method_dir.path)
            if any(f.startswith("coverage_") and f.endswith(".json") for f in files):
                yield method_dir.path


def fmt_frac(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "0 / 0  (N/A)"
    pct = 100.0 * numerator / denominator
    return f"{numerator} / {denominator}  ({pct:.1f}%)"


# ─────────────────────────────────────────────────────────────────────────────
# Method-level logic
# ─────────────────────────────────────────────────────────────────────────────

def method_used_reflect(func_dir: str) -> bool:
    for fname in os.listdir(func_dir):
        if not fname.endswith("_logs.json"):
            continue
        try:
            data = load_json(os.path.join(func_dir, fname))
            if data.get("testCaseStatus") == "failed":
                continue
            if (data.get("reflectIteration", 0) or 0) > 0:
                return True
        except Exception:
            continue
    return False


def method_reflect_success(func_dir: str) -> bool:
    """
    A method succeeded in reflection if:
      overall stmtCov or branchCov > non_reflect stmtCov or branchCov.
    """
    func_name = os.path.basename(func_dir)
    cov_file         = os.path.join(func_dir, f"coverage_{func_name}.json")
    non_reflect_file = os.path.join(func_dir, f"coverage_non_reflect_{func_name}.json")

    if not os.path.isfile(cov_file) or not os.path.isfile(non_reflect_file):
        return False
    try:
        cov    = load_json(cov_file)
        nonref = load_json(non_reflect_file)
        sc = safe_float(cov.get("stmtCov"));   sn = safe_float(nonref.get("stmtCov"))
        total_br    = cov.get("totalBranches")
        nr_total_br = nonref.get("totalBranches")
        raw_bc = safe_float(cov.get("branchCov")); raw_bn = safe_float(nonref.get("branchCov"))
        bc = 100.0 if (total_br == 0) else raw_bc
        bn = 100.0 if (nr_total_br == 0) else raw_bn
        EPSILON = 1e-6
        if sc is not None and sn is not None and (sc - sn) > EPSILON:
            return True
        if bc is not None and bn is not None and (bc - bn) > EPSILON:
            return True
    except Exception:
        pass
    return False


def collect_method_level(project_path: str):
    """
    Returns: total_methods, used_reflect, reflect_success, failed_names
    """
    total_methods = used_reflect = reflect_success = 0
    failed_names = []

    for func_dir in iter_function_dirs(project_path):
        func_name = os.path.basename(func_dir)
        logs = [f for f in os.listdir(func_dir) if f.endswith("_logs.json")]
        if not logs:
            continue

        total_methods += 1

        if not method_used_reflect(func_dir):
            continue

        used_reflect += 1
        if method_reflect_success(func_dir):
            reflect_success += 1
        else:
            failed_names.append(func_name)

    return total_methods, used_reflect, reflect_success, failed_names


# ─────────────────────────────────────────────────────────────────────────────
# Table builder
# ─────────────────────────────────────────────────────────────────────────────

def collect_all_stats():
    stats = {}
    for proj_name, rel_path in PROJECTS.items():
        full_path = os.path.join(BASE_DIR, rel_path)
        if not os.path.isdir(full_path):
            print(f"[WARN] Project path not found: {full_path}")
            stats[proj_name] = (0, 0, 0, [])
            continue
        t, u, s, failed = collect_method_level(full_path)
        stats[proj_name] = (t, u, s, failed)
        print(f"  {proj_name}: {t} methods, {u} used reflection, {s} succeeded")
    return stats


def build_table():
    stats = collect_all_stats()

    total_t = sum(v[0] for v in stats.values())
    total_u = sum(v[1] for v in stats.values())
    total_s = sum(v[2] for v in stats.values())

    col_names = list(PROJECTS.keys()) + ["Overall"]
    col_w = 24

    print(f"\n{'═' * (28 + col_w * len(col_names))}")
    print(f"  Reflection Success Rate  [Method Level]")
    print(f"{'═' * (28 + col_w * len(col_names))}")

    header = f"{'Metric':<28}" + "".join(f"{c:>{col_w}}" for c in col_names)
    print(header)
    print("─" * len(header))

    row1 = f"{'Used Reflection':<28}"
    for proj_name, (t, u, s, _) in stats.items():
        row1 += f"{fmt_frac(u, t):>{col_w}}"
    row1 += f"{fmt_frac(total_u, total_t):>{col_w}}"
    print(row1)

    row2 = f"{'Reflect Success':<28}"
    for proj_name, (t, u, s, _) in stats.items():
        row2 += f"{fmt_frac(s, u):>{col_w}}"
    row2 += f"{fmt_frac(total_s, total_u):>{col_w}}"
    print(row2)

    print("─" * len(header))

    print("\n  Failed Reflection Methods:")
    for proj_name, (t, u, s, failed) in stats.items():
        print(f"\n  [{proj_name}]  ({len(failed)} failed)")
        for name in sorted(failed):
            print(f"    - {name}")
        if not failed:
            print("    (none)")

    return stats


# ─────────────────────────────────────────────────────────────────────────────
# CSV exports
# ─────────────────────────────────────────────────────────────────────────────

def export_success_rate_csv(output_file: str, stats: dict):
    import csv

    total_t = sum(v[0] for v in stats.values())
    total_u = sum(v[1] for v in stats.values())
    total_s = sum(v[2] for v in stats.values())

    col_names = list(PROJECTS.keys()) + ["Overall"]

    with open(output_file, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Metric"] + col_names)

        cells = ["Used Reflection"]
        for proj_name, (t, u, s, _) in stats.items():
            cells.append(fmt_frac(u, t))
        cells.append(fmt_frac(total_u, total_t))
        writer.writerow(cells)

        cells = ["Reflect Success"]
        for proj_name, (t, u, s, _) in stats.items():
            cells.append(fmt_frac(s, u))
        cells.append(fmt_frac(total_s, total_u))
        writer.writerow(cells)

    print(f"Success rate table saved to: {output_file}")


def export_failed_methods_csv(output_file: str, stats: dict):
    import csv

    with open(output_file, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Method", "Project"])
        for proj_name, (t, u, s, failed) in stats.items():
            for name in sorted(failed):
                writer.writerow([name, proj_name])

    print(f"Failed methods saved to: {output_file}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Scanning: {BASE_DIR}\n")
    stats = build_table()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    export_success_rate_csv(os.path.join(output_dir, "reflection_success_rate.csv"), stats)
    export_failed_methods_csv(os.path.join(output_dir, "reflection_failed_methods.csv"), stats)
