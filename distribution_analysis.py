import os
import json
import math
import statistics
from typing import Optional

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from scipy import stats
import argparse

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CITYWALK_DIR = os.path.join(SCRIPT_DIR, "citywalk")

TOOL_DIRS = {
    "conreflect": os.path.join(SCRIPT_DIR, "conreflect"),
    "coverup":    os.path.join(SCRIPT_DIR, "coverup"),
    "gpt4_1nano": os.path.join(SCRIPT_DIR, "gpt4_1nano"),
    "deepseek_v3_2": os.path.join(SCRIPT_DIR, "deepseek_v3_2"),
    "haiku4_5": os.path.join(SCRIPT_DIR, "haiku4_5"),
}

PROJECTS = [
    "hjson-cpp", "json.cpp", "jvar", 
    "tinyxml2", "jsonxx", "RSJp-cpp", 
    "Jzon", "TinyEXIF", "bitmap", 
    "indicators", "polypartition"
]
PROJECT_PATHS = {
    "hjson-cpp": os.path.join("hjson-cpp"),
    "json.cpp":  os.path.join("json.cpp"),
    "jvar":      os.path.join("jvar"),
    "tinyxml2":  os.path.join("tinyxml2"),
    "jsonxx":    os.path.join("jsonxx"),
    "RSJp-cpp": os.path.join("RSJp-cpp"),
    "Jzon": os.path.join("Jzon", "Jzon.cpp"),
    "TinyEXIF": os.path.join("TinyEXIF"),
    "bitmap": os.path.join("bitmap"),
    "indicators": os.path.join("indicators"),
    "polypartition": os.path.join("polypartition"),
}

TOOLS: list[tuple[str, str]] = [
    ("citywalk",   "CITYWALK"),
    ("gpt4_1nano", "GPT-4.1-Nano"),
    ("deepseek_v3_2", "DeepSeek-V3.2"),
    ("haiku4_5", "Haiku-4.5"),
    ("coverup",    "CoverUp"),
    ("conreflect", "TRACIT"),
]

# Màu cho từng tool (thứ tự giống TOOLS)
TOOL_COLORS = {
    "citywalk":   "#D85A30",   # coral
    "gpt4_1nano": "#1E90FF",   # dodger blue
    "deepseek_v3_2": "#8A2BE2", # blueviolet
    "haiku4_5": "#228B22",   # forest green
    "coverup":    "#185FA5",   # blue
    "conreflect": "#0F6E56",   # teal/green
}

OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers  (giữ nguyên từ file gốc)
# ─────────────────────────────────────────────────────────────────────────────

def load_json(path: str):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return json.load(fh)


def safe_float(val) -> Optional[float]:
    if val is None: return None
    try:
        f = float(val)
        return 0.0 if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def parse_pct_str(s) -> Optional[float]:
    if not isinstance(s, str): return None
    s = s.strip()
    if s in ("N/A", ""): return 0.0
    try:
        return float(s.rstrip("%"))
    except ValueError:
        return None


def avg(values: list) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def iter_method_dirs(project_path: str):
    if not os.path.isdir(project_path): return
    for root, dirs, files in os.walk(project_path):
        if any(
            f.startswith("coverage_") and f.endswith(".json") and "non_reflect" not in f
            for f in files
        ):
            yield root


def _resolve_coverage_path(method_dir: str, func_name: str) -> Optional[str]:
    cov_path = os.path.join(method_dir, f"coverage_{func_name}.json")
    if os.path.isfile(cov_path): return cov_path
    candidates = [
        f for f in os.listdir(method_dir)
        if f.startswith("coverage_") and f.endswith(".json") and "non_reflect" not in f
    ]
    return os.path.join(method_dir, candidates[0]) if candidates else None


def _check_compile_error(log_path: str) -> bool:
    if not os.path.isfile(log_path): return False
    try:
        data = load_json(log_path)
        if isinstance(data, dict): return data.get("compile_error", False)
        if isinstance(data, list):
            return any(e.get("compile_error", False) for e in data if isinstance(e, dict))
    except Exception:
        pass
    return False


def _load_conreflect_totals(project: str) -> dict:
    con_path = os.path.join(TOOL_DIRS["conreflect"], PROJECT_PATHS.get(project, ""))
    br_totals = {}
    if not os.path.isdir(con_path): return br_totals
    for method_dir in iter_method_dirs(con_path):
        func_name = os.path.basename(method_dir)
        cov_path = _resolve_coverage_path(method_dir, func_name)
        if cov_path:
            try:
                br_totals[func_name] = load_json(cov_path).get("totalBranches")
            except Exception:
                pass
    return br_totals


def _append_coverage(file_data: dict, filename: str, s: float, b: float):
    if filename not in file_data:
        file_data[filename] = {"stmt": [], "branch": []}
    file_data[filename]["stmt"].append(s)
    file_data[filename]["branch"].append(b)


# ─────────────────────────────────────────────────────────────────────────────
# Loaders  (giữ nguyên từ file gốc)
# ─────────────────────────────────────────────────────────────────────────────

def load_citywalk_coverage(project: str) -> dict:
    file_data = {}
    if not os.path.isdir(CITYWALK_DIR): return file_data

    norm_project = project.replace("_", "").replace("-", "").lower()
    project_dirs = []
    for entry in os.listdir(CITYWALK_DIR):
        remainder = "_".join(entry.split("_")[2:]).replace("_", "").replace("-", "").lower()
        if remainder.startswith(norm_project) or remainder == norm_project:
            project_dirs.append(os.path.join(CITYWALK_DIR, entry))
    if not project_dirs: return file_data

    report_path = os.path.join(sorted(project_dirs)[-1], "post", "coverage_report.json")
    if not os.path.isfile(report_path): return file_data

    try:
        entries = load_json(report_path)
    except Exception:
        return file_data

    for entry in entries:
        fname = entry.get("filename")
        if not fname: continue
        fname = os.path.basename(fname)
        if entry.get("compile_error"):
            continue
        else:
            s = parse_pct_str(entry.get("lines_coverage"))
            b_total = entry.get("branches_total", 0) or 0
            l_total = entry.get("lines_total", 0) or 0
            b = (100.0 if (b_total == 0 and l_total > 0)
                 else parse_pct_str(entry.get("branches_coverage")))
            s, b = s or 0.0, b or 0.0
        _append_coverage(file_data, fname, s, b)
    return file_data


def load_directory_based_coverage(project: str, tool: str) -> dict:
    file_data = {}
    rel_path = PROJECT_PATHS.get(project)
    if not rel_path: return file_data

    full_path = os.path.join(TOOL_DIRS.get(tool, ""), rel_path)
    if not os.path.isdir(full_path): return file_data

    is_ref = (tool == "conreflect")
    conreflect_branches = {} if is_ref else _load_conreflect_totals(project)

    for method_dir in iter_method_dirs(full_path):
        func_name = os.path.basename(method_dir)
        filename = os.path.basename(os.path.dirname(method_dir))
        cov_path = _resolve_coverage_path(method_dir, func_name)
        if not cov_path: continue

        if not is_ref:
            log_path = os.path.join(method_dir, f"{func_name}_ai_0_logs.json")
            if _check_compile_error(log_path):
                _append_coverage(file_data, filename, 0.0, 0.0)
                continue

        try:
            data = load_json(cov_path)
        except Exception:
            continue

        s = safe_float(data.get("stmtCov"))
        total_stmt = data.get("totalStatements")
        total_br = (data.get("totalBranches") if is_ref
                    else conreflect_branches.get(func_name, data.get("totalBranches")))
        raw_b = safe_float(data.get("branchCov"))

        if not is_ref and s is not None and s == 0.0:
            b = 0.0
        elif total_stmt is not None and total_br == 0 and total_stmt > 0:
            b = 100.0
        else:
            b = raw_b

        _append_coverage(
            file_data, filename,
            s if s is not None else 0.0,
            b if b is not None else 0.0
        )
    return file_data


# ─────────────────────────────────────────────────────────────────────────────
# Thu thập raw method-level values
# ─────────────────────────────────────────────────────────────────────────────

def collect_raw_values() -> dict[str, dict[str, list[float]]]:
    """
    Trả về:
        raw[tool_key][project] = [coverage_value_per_method, ...]
    Mỗi method → 1 giá trị (avg nếu có nhiều lần chạy).
    """
    raw: dict[str, dict[str, list[float]]] = {
        tool: {proj: [] for proj in PROJECTS + ["Overall"]}
        for tool, _ in TOOLS
    }

    for proj in PROJECTS:
        tool_file_data = {}
        for tool, _ in TOOLS:
            if tool == "citywalk":
                tool_file_data[tool] = load_citywalk_coverage(proj)
            else:
                tool_file_data[tool] = load_directory_based_coverage(proj, tool)

        for tool, _ in TOOLS:
            for fname, metrics in tool_file_data[tool].items():
                for s in metrics["stmt"]:
                    if s is not None:
                        raw[tool][proj].append(s)
                        raw[tool]["Overall"].append(s)

    return raw


# ─────────────────────────────────────────────────────────────────────────────
# Kiểm định thống kê
# ─────────────────────────────────────────────────────────────────────────────

def run_statistical_tests(raw: dict, scope: str = "Overall"):
    """
    Wilcoxon rank-sum test (Mann-Whitney U) của TRACIT vs các baseline.
    Dùng non-parametric vì coverage thường không phân phối chuẩn.
    """
    tracit_vals = raw["conreflect"][scope]

    def fmt_pvalue(p: float) -> str:
        if p is None:
            return "N/A"
        if p == 0.0:
            return "0"
        coeff, exp = f"{p:.2e}".split("e")
        return f"{coeff} * 10^{int(exp)}"

    print(f"\n{'═'*60}")
    print(f"  Statistical Tests — TRACIT vs Baselines [{scope}]")
    print(f"  Test: Mann-Whitney U (two-sided, non-parametric)")
    print(f"{'═'*60}")
    print(f"  {'Baseline':<16} {'VDA':>8} {'p-value':>18} {'Significant':>13}")
    print(f"  {'─'*16} {'─'*8} {'─'*18} {'─'*13}")

    for tool, label in TOOLS:
        if tool == "conreflect":
            continue
        baseline_vals = raw[tool][scope]
        n1, n2 = len(tracit_vals), len(baseline_vals)
        if n2 < 3 or n1 < 3:
            print(f"  {label:<16} {'N/A':>8} {'N/A':>18} {'N/A':>13}")
            continue

        u_stat, p_val = stats.mannwhitneyu(tracit_vals, baseline_vals, alternative="two-sided")
        max_u = n1 * n2
        vda = (u_stat / max_u) if max_u else float("nan")
        p_str = fmt_pvalue(p_val)
        sig = "Yes ***" if p_val < 0.001 else ("Yes **" if p_val < 0.01 else ("Yes *" if p_val < 0.05 else "No"))
        print(f"  {label:<16} {vda:>8.3f} {p_str:>18} {sig:>13}")
    print(f"  (Significance: * p<0.05, ** p<0.01, *** p<0.001)")


# ─────────────────────────────────────────────────────────────────────────────
# Vẽ Box + Strip Plot (Overall)
# ─────────────────────────────────────────────────────────────────────────────

def plot_boxstrip_overall(raw: dict, metric_label: str = "Statement Coverage (%)"):
    # Wider canvas to further reduce x-label overlap with larger fonts.
    fig, ax = plt.subplots(figsize=(17, 5.4))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#F9F9F9")

    tool_keys  = [t for t, _ in TOOLS]
    tool_labels = [label for _, label in TOOLS]
    positions  = list(range(1, len(TOOLS) + 1))

    all_data = [raw[tk]["Overall"] for tk in tool_keys]

    # ── Median lines ─────────────────────────────────────────────────────────
    for pos, tk, data in zip(positions, tool_keys, all_data):
        if data:
            med = statistics.median(data)
            ax.hlines(med, pos - 0.18, pos + 0.18,
                      colors=TOOL_COLORS[tk], linewidths=2.5, zorder=4)

    # ── Strip plot (jittered dots) ────────────────────────────────────────────
    import random
    random.seed(42)
    for pos, tk, data in zip(positions, tool_keys, all_data):
        jitter = [pos + random.uniform(-0.18, 0.18) for _ in data]
        ax.scatter(
            jitter, data,
            color=TOOL_COLORS[tk],
            alpha=0.35,
            s=12,
            zorder=3,
            edgecolors="none",
        )

    # ── Mean markers ──────────────────────────────────────────────────────────
    for pos, data in zip(positions, all_data):
        if data:
            ax.scatter([pos], [statistics.mean(data)],
                       marker="D", s=40, color="white",
                       edgecolors="#555", linewidths=0.8, zorder=5)

    FS = 18

    # ── Annotations: median ───────────────────────────────────────────────
    for pos, tk, data in zip(positions, tool_keys, all_data):
        if not data: continue
        med = statistics.median(data)
        ax.text(pos + 0.27, med, f"{med:.1f}%",
                ha="left", va="center", fontsize=FS + 1,
                color=TOOL_COLORS[tk], fontweight="bold")

    # ── Formatting ────────────────────────────────────────────────────────────
    ax.set_xticks(positions)
    ax.set_xticklabels(tool_labels, fontsize=FS + 1)
    ax.set_ylabel(metric_label, fontsize=FS + 4)
    ax.set_ylim(-8, 108)
    ax.set_xlim(0.3, len(TOOLS) + 0.7)
    ax.tick_params(axis="x", labelsize=FS + 1)
    ax.tick_params(axis="y", labelsize=FS)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5, color="#ccc")
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="x", bottom=False)

    # Intentionally no legend and no title (requested).
    plt.tight_layout()
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Vẽ Box + Strip Plot per Project
# ─────────────────────────────────────────────────────────────────────────────

def plot_boxstrip_per_project(raw: dict, metric_label: str = "Statement Coverage (%)"):
    n_proj = len(PROJECTS)
    fig, axes = plt.subplots(1, n_proj, figsize=(3.2 * n_proj, 5), sharey=True)
    fig.patch.set_facecolor("white")

    import random
    random.seed(7)

    tool_keys   = [t for t, _ in TOOLS]
    tool_labels = [label for _, label in TOOLS]
    positions   = list(range(1, len(TOOLS) + 1))

    for ax, proj in zip(axes, PROJECTS):
        ax.set_facecolor("#F9F9F9")
        all_data = [raw[tk][proj] for tk in tool_keys]

        bp = ax.boxplot(
            all_data,
            positions=positions,
            widths=0.5,
            patch_artist=True,
            notch=False,
            showfliers=False,
            medianprops=dict(color="white", linewidth=2),
            whiskerprops=dict(linewidth=1),
            capprops=dict(linewidth=1),
            boxprops=dict(linewidth=0.8),
        )

        for patch, tk in zip(bp["boxes"], tool_keys):
            patch.set_facecolor(TOOL_COLORS[tk])
            patch.set_alpha(0.75)
            patch.set_edgecolor(TOOL_COLORS[tk])

        for element in ["whiskers", "caps"]:
            for line, tk in zip(bp[element], [t for t in tool_keys for _ in range(2)]):
                line.set_color(TOOL_COLORS[tk])
                line.set_alpha(0.7)

        for pos, tk, data in zip(positions, tool_keys, all_data):
            jitter = [pos + random.uniform(-0.2, 0.2) for _ in data]
            ax.scatter(jitter, data, color=TOOL_COLORS[tk],
                       alpha=0.4, s=10, zorder=3, edgecolors="none")

        # Mean diamonds
        for pos, data in zip(positions, all_data):
            if data:
                ax.scatter([pos], [statistics.mean(data)],
                           marker="D", s=30, color="white",
                           edgecolors="#555", linewidths=0.7, zorder=5)

        ax.set_title(proj, fontsize=9, pad=6)
        ax.set_xticks(positions)
        ax.set_xticklabels(
            ["CW", "Nano", "CUp", "TR"],  # abbreviated
            fontsize=7.5
        )
        ax.yaxis.grid(True, linestyle="--", alpha=0.4, color="#ccc")
        ax.set_axisbelow(True)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.tick_params(axis="x", bottom=False)
        ax.set_ylim(-5, 108)

    axes[0].set_ylabel(metric_label, fontsize=9)

    legend_elements = [
        mpatches.Patch(facecolor=TOOL_COLORS[tk], alpha=0.75,
                       label=f"{label} ({abbr})")
        for (tk, label), abbr in zip(TOOLS, ["CW", "Nano", "CUp", "TR"])
    ]
    fig.legend(
        handles=legend_elements,
        loc="lower center",
        ncol=4,
        fontsize=8,
        framealpha=0.9,
        edgecolor="#ddd",
        bbox_to_anchor=(0.5, -0.04),
    )
    fig.suptitle(
        f"Distribution of {metric_label} per project",
        fontsize=11, y=1.02,
    )
    plt.tight_layout()
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Distribution analysis plots with optional lossless vector export."
    )
    parser.add_argument(
        "--vector",
        choices=["pdf", "svg"],
        help="Also export plots as a lossless vector file (pdf or svg).",
    )
    args = parser.parse_args()

    print("Loading coverage data...")
    raw = collect_raw_values()

    # ── Kiểm định thống kê ────────────────────────────────────────────────────
    run_statistical_tests(raw, scope="Overall")

    # ── Vẽ và lưu biểu đồ ────────────────────────────────────────────────────
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("\nGenerating plots...")

    fig_overall = plot_boxstrip_overall(raw, "Statement Coverage (%)")
    out_overall = os.path.join(OUTPUT_DIR, "distribution_overall.png")
    fig_overall.savefig(out_overall, dpi=180, bbox_inches="tight")
    print(f"  Saved: {out_overall}")
    if args.vector:
        out_overall_vec = os.path.join(
            OUTPUT_DIR, f"distribution_overall.{args.vector}"
        )
        fig_overall.savefig(out_overall_vec, bbox_inches="tight")
        print(f"  Saved: {out_overall_vec}")
    plt.close(fig_overall)

    # fig_proj = plot_boxstrip_per_project(raw, "Statement Coverage (%)")
    # out_proj = os.path.join(OUTPUT_DIR, "distribution_per_project.png")
    # fig_proj.savefig(out_proj, dpi=180, bbox_inches="tight")
    # print(f"  Saved: {out_proj}")
    # plt.close(fig_proj)

    print("\nDone.")
