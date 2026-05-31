import os
import json
import csv
import math

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CITYWALK_DIR = os.path.join(SCRIPT_DIR, "citywalk")

TOOL_DIRS = {
    "conreflect": os.path.join(SCRIPT_DIR, "conreflect"),
    "gpt4_1nano": os.path.join(SCRIPT_DIR, "gpt4_1nano"),
    "deepseek_v3_2": os.path.join(SCRIPT_DIR, "deepseek_v3_2"),
    "haiku4_5": os.path.join(SCRIPT_DIR, "haiku4_5"),
    "coverup": os.path.join(SCRIPT_DIR, "coverup"),
    "llm4cpp": os.path.join(SCRIPT_DIR, "llm4cpp"),
}

PROJECTS = [
    "hjson-cpp", "json.cpp", "jvar",
    "tinyxml2", "jsonxx", "RSJp-cpp",
    "Jzon", "TinyEXIF", "bitmap",
    "indicators", "polypartition"
]
PROJECT_PATHS = {
    "hjson-cpp": os.path.join("hjson-cpp"),
    "json.cpp": os.path.join("json.cpp"),
    "jvar": os.path.join("jvar"),
    "tinyxml2": os.path.join("tinyxml2"),
    "jsonxx": os.path.join("jsonxx"),
    "RSJp-cpp": os.path.join("RSJp-cpp"),
    "Jzon": os.path.join("Jzon"),
    "TinyEXIF": os.path.join("TinyEXIF"),
    "bitmap": os.path.join("bitmap"),
    "indicators": os.path.join("indicators"),
    "polypartition": os.path.join("polypartition")
}

TOOLS: list[tuple[str, str]] = [
    ("citywalk", "Citywalk"),
    ("gpt4_1nano", "GPT-4.1-nano"),
    ("deepseek_v3_2", "Deepseek-V3.2"),
    ("haiku4_5", "Haiku-4.5"),
    ("coverup", "CoverUp"),
    ("llm4cpp", "LLM4CPP"),
    ("conreflect", "TraceIT"),
]

ground_truth_methods = {proj: {} for proj in PROJECTS}
ground_truth_files = {proj: {} for proj in PROJECTS}

def load_json(path: str):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return json.load(fh)

def safe_float(val) -> float | None:
    if val is None: return None
    try:
        f = float(val)
        return 0.0 if math.isnan(f) else f
    except (TypeError, ValueError):
        return None

def parse_pct_str(s) -> float | None:
    if not isinstance(s, str): return None
    s = s.strip()
    if s in ("N/A", ""): return 0.0
    try:
        return float(s.rstrip("%"))
    except ValueError:
        return None

def iter_method_dirs(project_path: str):
    if not os.path.isdir(project_path): return
    for root, dirs, files in os.walk(project_path):
        if any(f.startswith("coverage_") and f.endswith(".json") and "non_reflect" not in f for f in files):
            yield root

def _resolve_coverage_path(method_dir: str, func_name: str) -> str | None:
    cov_path = os.path.join(method_dir, f"coverage_{func_name}.json")
    if os.path.isfile(cov_path): return cov_path
    candidates = [f for f in os.listdir(method_dir) if
                  f.startswith("coverage_") and f.endswith(".json") and "non_reflect" not in f]
    return os.path.join(method_dir, candidates[0]) if candidates else None

def _append_coverage_raw(file_data: dict, filename: str, s_cov: int, s_tot: int, b_cov: int, b_tot: int):
    if filename not in file_data:
        file_data[filename] = {"s_cov": 0, "s_tot": 0, "b_cov": 0, "b_tot": 0}
    file_data[filename]["s_cov"] += s_cov
    file_data[filename]["s_tot"] += s_tot
    file_data[filename]["b_cov"] += b_cov
    file_data[filename]["b_tot"] += b_tot

def calc_pct(cov: int, tot: int, s_tot: int = 0) -> float:
    if tot > 0:
        return (cov / tot) * 100.0
    if s_tot > 0:
        return 100.0
    return 0.0

def get_total_stmts_branches():
    for proj in PROJECTS:
        rel_path = PROJECT_PATHS.get(proj)
        if not rel_path: continue

        full_path = os.path.join(TOOL_DIRS.get("conreflect", ""), rel_path)
        if not os.path.isdir(full_path):
            continue

        for method_dir in iter_method_dirs(full_path):
            func_name = os.path.basename(method_dir)
            filename = os.path.basename(os.path.dirname(method_dir))
            cov_path = _resolve_coverage_path(method_dir, func_name)
            if not cov_path:
                continue
            try:
                data = load_json(cov_path)
                s_tot = data.get("totalStatements", 0) or 0
                b_tot = data.get("totalBranches", 0) or 0
                if func_name not in ground_truth_methods[proj]:
                    ground_truth_methods[proj][func_name] = {"s_tot": 0, "b_tot": 0, "filename": filename}
                ground_truth_methods[proj][func_name]["s_tot"] = s_tot
                ground_truth_methods[proj][func_name]["b_tot"] = b_tot
            except Exception:
                pass

        for func_name, totals in ground_truth_methods[proj].items():
            fname = totals["filename"]
            if fname not in ground_truth_files[proj]:
                ground_truth_files[proj][fname] = {"s_tot": 0, "b_tot": 0}
            ground_truth_files[proj][fname]["s_tot"] += totals["s_tot"]
            ground_truth_files[proj][fname]["b_tot"] += totals["b_tot"]

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
    temp_file_map = {}
    for entry in entries:
        fname = os.path.basename(entry.get("filename", ""))
        if not fname: continue
        if entry.get("compile_error"):
            continue
        l_total_entry = entry.get("lines_total", 0) or 0
        b_total_entry = entry.get("branches_total", 0) or 0
        s_cov_entry = entry.get("lines_hit")
        if s_cov_entry is None:
            pct = parse_pct_str(entry.get("lines_coverage")) or 0.0
            s_cov_entry = round((pct / 100.0) * l_total_entry)
        b_cov_entry = entry.get("branches_hit")
        if b_cov_entry is None:
            pct = parse_pct_str(entry.get("branches_coverage")) or 0.0
            b_cov_entry = round((pct / 100.0) * b_total_entry)
        if fname not in temp_file_map:
            temp_file_map[fname] = {"s_cov": 0, "s_tot": 0, "b_cov": 0, "b_tot": 0}
        temp_file_map[fname]["s_cov"] += s_cov_entry
        temp_file_map[fname]["s_tot"] += l_total_entry
        temp_file_map[fname]["b_cov"] += b_cov_entry
        temp_file_map[fname]["b_tot"] += b_total_entry
    for fname, data in temp_file_map.items():
        _append_coverage_raw(file_data, fname, data["s_cov"], data["s_tot"], data["b_cov"], data["b_tot"])
    return file_data

def load_directory_based_coverage(project: str, tool: str) -> dict:
    file_data = {}
    rel_path = PROJECT_PATHS.get(project)
    if not rel_path: return file_data
    full_path = os.path.join(TOOL_DIRS.get(tool, ""), rel_path)

    if not os.path.isdir(full_path):
        return file_data

    for method_dir in iter_method_dirs(full_path):
        func_name = os.path.basename(method_dir)
        filename = os.path.basename(os.path.dirname(method_dir))
        cov_path = _resolve_coverage_path(method_dir, func_name)
        if not cov_path:
            continue

        try:
            data = load_json(cov_path)
            s_tot = int(data.get("totalStatements", 0) or 0)
            b_tot = int(data.get("totalBranches", 0) or 0)
            stmt_pct = safe_float(data.get("stmtCov")) or 0.0
            branch_pct = safe_float(data.get("branchCov")) or 0.0
            s_cov = round((stmt_pct / 100.0) * s_tot)
            b_cov = round((branch_pct / 100.0) * b_tot)
            _append_coverage_raw(file_data, filename, s_cov, s_tot, b_cov, b_tot)
        except Exception:
            _append_coverage_raw(file_data, filename, 0, 0, 0, 0)

    return file_data

def build_metrics():
    file_comparison = {}
    for proj in PROJECTS:
        file_comparison[proj] = {}
        tool_file_data = {}
        for tool, _ in TOOLS:
            if tool == "citywalk":
                f_data = load_citywalk_coverage(proj)
            else:
                f_data = load_directory_based_coverage(proj, tool)
            tool_file_data[tool] = f_data
        all_files = set(fname for t_data in tool_file_data.values() for fname in t_data.keys())
        for fname in sorted(all_files):
            file_comparison[proj][fname] = {}
            for tool, _ in TOOLS:
                metrics = tool_file_data[tool].get(fname, {
                    "s_cov": 0, "s_tot": 0, "b_cov": 0, "b_tot": 0
                })
                file_comparison[proj][fname][tool] = metrics
    return file_comparison

def export_file_csv(output_file: str, file_comparison: dict, metric: str):
    with open(output_file, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Project", "File"] + [label for _, label in TOOLS])
        total_cov = {key: 0 for key, _ in TOOLS}
        total_tot = {key: 0 for key, _ in TOOLS}
        total_stmt_tot = {key: 0 for key, _ in TOOLS}
        for proj in PROJECTS:
            for fname in sorted(file_comparison[proj].keys()):
                row = [proj, fname]
                for tool, _ in TOOLS:
                    data = file_comparison[proj][fname][tool]
                    if metric == "stmt":
                        cov, tot = data["s_cov"], data["s_tot"]
                    else:
                        cov, tot = data["b_cov"], data["b_tot"]
                    total_cov[tool] += cov
                    total_tot[tool] += tot
                    total_stmt_tot[tool] += data["s_tot"]
                    pct = calc_pct(cov, tot, data["s_tot"])
                    row.append(f"{pct:.2f}")
                writer.writerow(row)
        overall_row = ["Overall", ""]
        for tool, _ in TOOLS:
            pct = calc_pct(total_cov[tool], total_tot[tool], total_stmt_tot[tool])
            overall_row.append(f"{pct:.2f}")
        writer.writerow(overall_row)
    print(f"  Saved File-level ({metric.upper()}) : {output_file}")

def export_project_csv(output_file: str, file_comparison: dict, metric: str):
    with open(output_file, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Project"] + [label for _, label in TOOLS])
        overall_cov = {key: 0 for key, _ in TOOLS}
        overall_tot = {key: 0 for key, _ in TOOLS}
        overall_stmt_tot = {key: 0 for key, _ in TOOLS}
        for proj in PROJECTS:
            row = [proj]
            proj_cov = {key: 0 for key, _ in TOOLS}
            proj_tot = {key: 0 for key, _ in TOOLS}
            proj_stmt_tot = {key: 0 for key, _ in TOOLS}
            for fname in file_comparison[proj].keys():
                for tool, _ in TOOLS:
                    data = file_comparison[proj][fname][tool]
                    if metric == "stmt":
                        cov, tot = data["s_cov"], data["s_tot"]
                    else:
                        cov, tot = data["b_cov"], data["b_tot"]
                    proj_cov[tool] += cov
                    proj_tot[tool] += tot
                    proj_stmt_tot[tool] += data["s_tot"]
                    overall_cov[tool] += cov
                    overall_tot[tool] += tot
                    overall_stmt_tot[tool] += data["s_tot"]
            for tool, _ in TOOLS:
                pct = calc_pct(proj_cov[tool], proj_tot[tool], proj_stmt_tot[tool])
                row.append(f"{pct:.2f}")
            writer.writerow(row)
        overall_row = ["Overall"]
        for tool, _ in TOOLS:
            pct = calc_pct(overall_cov[tool], overall_tot[tool], overall_stmt_tot[tool])
            overall_row.append(f"{pct:.2f}")
        writer.writerow(overall_row)
    print(f"  Saved Project-level ({metric.upper()}) : {output_file}")

if __name__ == "__main__":
    # get_total_stmts_branches()
    file_comp = build_metrics()
    output_dir = os.path.join(SCRIPT_DIR, "output")
    os.makedirs(output_dir, exist_ok=True)
    export_project_csv(os.path.join(output_dir, "baselines_vs_conreflect_project_level_stmt_coverage.csv"), file_comp, "stmt")
    export_project_csv(os.path.join(output_dir, "baselines_vs_conreflect_project_level_branch_coverage.csv"), file_comp, "branch")
