import argparse
import os
import json
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "conreflect")

PROJECTS = {
    "hjson-cpp": os.path.join("hjson-cpp"),
    "json.cpp":  os.path.join("json.cpp", "json.cpp"),
    "jvar":      os.path.join("jvar"),
    "tinyxml2":  os.path.join("tinyxml2", "tinyxml2.cpp"),
    "jsonxx":    os.path.join("jsonxx"),
    "RSJp-cpp":      os.path.join("RSJp-cpp"),
    "Jzon":      os.path.join("Jzon"),
    "TinyEXIF": os.path.join("TinyEXIF"),
    "bitmap": os.path.join("bitmap"),
    "indicators": os.path.join("indicators"),
    "polypartition": os.path.join("polypartition"),
}

# Larger typography for publication/readability.
ANNOTATION_FONT_SIZE = 20
TICK_FONT_SIZE = 22
AXIS_LABEL_FONT_SIZE = 22

# ─────────────────────────────────────────────────────────────────────────────
# Helpers  (mirrors reflection_success_table.py logic)
# ─────────────────────────────────────────────────────────────────────────────

def load_json(path: str):
    with open(path, encoding="utf-8", errors="replace") as fh:
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
    for root, dirs, files in os.walk(project_path):
        if any(f.startswith("coverage_") and f.endswith(".json") for f in files):
            yield root


def method_used_reflect(func_dir: str) -> bool:
    for fname in os.listdir(func_dir):
        if not fname.endswith("_logs.json"):
            continue
        try:
            data = load_json(os.path.join(func_dir, fname))
            if str(data.get("testCaseStatus", "")).lower() == "failed":
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
    cov_file = os.path.join(func_dir, f"coverage_{func_name}.json")
    non_ref  = os.path.join(func_dir, f"coverage_non_reflect_{func_name}.json")
    if not os.path.isfile(cov_file) or not os.path.isfile(non_ref):
        return False
    try:
        cov    = load_json(cov_file)
        nonref = load_json(non_ref)
        sc = safe_float(cov.get("stmtCov"));   sn = safe_float(nonref.get("stmtCov"))
        total_br    = cov.get("totalBranches")
        nr_total_br = nonref.get("totalBranches")
        raw_bc = safe_float(cov.get("branchCov")); raw_bn = safe_float(nonref.get("branchCov"))
        bc = 100.0 if (total_br == 0) else raw_bc
        bn = 100.0 if (nr_total_br == 0) else raw_bn
        if sc is not None and sn is not None and sc > sn:
            return True
        if bc is not None and bn is not None and bc > bn:
            return True
    except Exception:
        pass
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Collect full coverage rows for table export
# ─────────────────────────────────────────────────────────────────────────────

def collect_coverage_rows(project_path: str, include_all: bool = True) -> list[dict]:
    """
    For each method that used reflection (and, when include_all=False, also
    succeeded), return a dict with:
      func_name, stmt_before, stmt_after, stmt_delta,
      branch_before, branch_after, branch_delta
    """
    rows = []
    for func_dir in iter_function_dirs(project_path):
        func_name = os.path.basename(func_dir)
        if not method_used_reflect(func_dir):
            continue
        if not include_all and not method_reflect_success(func_dir):
            continue
        cov_file = os.path.join(func_dir, f"coverage_{func_name}.json")
        non_ref  = os.path.join(func_dir, f"coverage_non_reflect_{func_name}.json")
        if not os.path.isfile(cov_file) or not os.path.isfile(non_ref):
            continue
        try:
            cov    = load_json(cov_file)
            nonref = load_json(non_ref)
        except Exception:
            continue
        sc = safe_float(cov.get("stmtCov"));    sn = safe_float(nonref.get("stmtCov"))
        total_br    = cov.get("totalBranches")
        nr_total_br = nonref.get("totalBranches")
        raw_bc = safe_float(cov.get("branchCov"));  raw_bn = safe_float(nonref.get("branchCov"))
        bc = 100.0 if (total_br == 0) else raw_bc
        bn = 100.0 if (nr_total_br == 0) else raw_bn
        rows.append({
            "func":          func_name,
            "stmt_before":   sn,
            "stmt_after":    sc,
            "stmt_delta":    (sc - sn) if sc is not None and sn is not None else None,
            "branch_before": bn,
            "branch_after":  bc,
            "branch_delta":  (bc - bn) if bc is not None and bn is not None else None,
        })
    return rows


def _fmt(val, sign=False) -> str:
    if val is None:
        return "N/A"
    prefix = "+" if sign and val > 0 else ""
    return f"{prefix}{val:.2f}%"

# ─────────────────────────────────────────────────────────────────────────────
# Collect deltas
# ─────────────────────────────────────────────────────────────────────────────

def collect_deltas(project_path: str, include_all: bool = True) -> list[float]:
    deltas = []
    for func_dir in iter_function_dirs(project_path):
        func_name = os.path.basename(func_dir)
        if not method_used_reflect(func_dir):
            continue
        if not include_all and not method_reflect_success(func_dir):
            continue
        cov_file = os.path.join(func_dir, f"coverage_{func_name}.json")
        non_ref  = os.path.join(func_dir, f"coverage_non_reflect_{func_name}.json")
        if not os.path.isfile(cov_file) or not os.path.isfile(non_ref):
            continue
        try:
            sc = safe_float(load_json(cov_file).get("stmtCov"))
            sn = safe_float(load_json(non_ref).get("stmtCov"))
        except Exception:
            continue
        if sc is not None and sn is not None:
            deltas.append(sc - sn)
    return deltas


# ─────────────────────────────────────────────────────────────────────────────
# Plot
# ─────────────────────────────────────────────────────────────────────────────

def draw_violin(include_all: bool = True, vector_format: str | None = None):
    project_deltas = {}
    for proj_name, rel_path in PROJECTS.items():
        full_path = os.path.join(BASE_DIR, rel_path)
        deltas = collect_deltas(full_path, include_all=include_all) if os.path.isdir(full_path) else []
        project_deltas[proj_name] = deltas
        print(f"  {proj_name}: {len(deltas)} methods, "
              f"mean delta = {np.mean(deltas):.2f}%" if deltas else
              f"  {proj_name}: 0 methods")

    all_deltas = [d for v in project_deltas.values() for d in v]
    labels = list(PROJECTS.keys()) + ["Overall"]
    data   = [project_deltas[p] for p in PROJECTS] + [all_deltas]

    # ── figure ────────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(max(7, 2 * len(labels) + 1), 6))

    VIOLIN_COLOR = "#55A868"  # green
    colors = [VIOLIN_COLOR] * len(data)

    # Split into violin-eligible (≥2 pts) and single-point groups
    violin_positions = [i + 1 for i, d in enumerate(data) if len(d) >= 2]
    violin_data      = [d      for d in data if len(d) >= 2]

    if violin_data:
        parts = ax.violinplot(
            violin_data,
            positions=violin_positions,
            showmedians=True,
            showextrema=True,
        )
        for pc, col in zip(parts["bodies"], [colors[i] for i, d in enumerate(data) if len(d) >= 2]):
            pc.set_facecolor(col)
            pc.set_alpha(0.6)
            pc.set_edgecolor("black")
            pc.set_linewidth(0.8)
        for part_name in ("cmedians", "cmins", "cmaxes", "cbars"):
            if part_name in parts:
                parts[part_name].set_color("black")
                parts[part_name].set_linewidth(1.2)

    # Overlay individual data points (jittered for ≥2, centred for single)
    rng = np.random.default_rng(42)
    for i, (d, col) in enumerate(zip(data, colors)):
        if not d:
            continue
        jitter = rng.uniform(-0.08, 0.08, size=len(d)) if len(d) >= 2 else [0]
        ax.scatter(
            np.full(len(d), i + 1) + jitter, d,
            color=col, edgecolors="black", linewidths=0.5,
            s=60 if len(d) == 1 else 28,
            marker="D" if len(d) == 1 else "o",
            zorder=3, alpha=0.85,
        )

    # Annotate n and mean above each group
    for i, d in enumerate(data):
        if not d:
            continue
        top = max(d)
        label_text = f"n={len(d)}\nμ={np.mean(d):.1f}%" if len(d) >= 2 else f"n=1\n{d[0]:.1f}%"
        ax.text(
            i + 1, top + 1.5,
            label_text,
            ha="center", va="bottom", fontsize=ANNOTATION_FONT_SIZE, color="#333333",
        )

    # Reference line at 0
    ax.axhline(0, color="red", linestyle="--", linewidth=0.9, alpha=0.7, zorder=1)

    # Separate "Overall" violin with a vertical dashed line
    if "Overall" in labels:
        overall_pos = labels.index("Overall") + 1
        ax.axvline(overall_pos - 0.5, color="grey", linestyle=":", linewidth=1.0)

    ax.set_xticks(range(1, len(labels) + 1))
    ax.set_xticklabels(labels, fontsize=TICK_FONT_SIZE)
    ax.tick_params(axis="y", labelsize=TICK_FONT_SIZE)
    ax.set_ylabel("Statement Coverage Increase (%)", fontsize=AXIS_LABEL_FONT_SIZE)
    if include_all:
        title = "Statement coverage increase for methods\nthat used Reflection"
        out_name = "violin_stmt_coverage_increase_all.png"
    else:
        title = "Statement coverage increase for methods\nwith successful reflection"
        out_name = "violin_stmt_coverage_increase.png"
    # ax.set_title(
    #     title,
    #     fontsize=20, fontweight="bold",
    #     pad=30,  # push title up to avoid overlap with annotations
    # )
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)

    # Add extra headroom so annotations don't collide with the title
    current_top = ax.get_ylim()[1]
    ax.set_ylim(top=current_top + 12)

    plt.tight_layout()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, out_name)
    plt.savefig(out_path, dpi=900, bbox_inches="tight")
    print(f"\nPlot saved to: {out_path}")

    if vector_format:
        vec_name = os.path.splitext(out_name)[0] + f".{vector_format}"
        vec_path = os.path.join(output_dir, vec_name)
        plt.savefig(vec_path, format=vector_format, bbox_inches="tight")
        print(f"Vector plot saved to: {vec_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Violin plot of statement coverage increase for methods that used reflection."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--all",
        dest="include_all",
        action="store_true",
        default=True,
        help="Include ALL methods that used reflection (succeeded + failed). [DEFAULT]",
    )
    mode.add_argument(
        "--success-only",
        dest="include_all",
        action="store_false",
        help="Include only methods where reflection succeeded.",
    )
    parser.add_argument(
        "--vector",
        choices=["pdf", "svg"],
        help="Also export a lossless vector copy (pdf or svg).",
    )
    args = parser.parse_args()
    include_all = args.include_all

    mode_label = "all (success + failed)" if include_all else "success only"
    print(f"Scanning: {BASE_DIR}  [mode: {mode_label}]\n")

    draw_violin(include_all=include_all, vector_format=args.vector)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    suffix = "_all" if include_all else ""

