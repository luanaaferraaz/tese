#!/usr/bin/env python3
"""
run_and_update.py — Run experiments, detect failures, retry, and update Excel.

Combines script-2.py (testing) and update_excel.py (analysis) into a single
pipeline that automatically retries failed tests.

Usage:
    python3 run_and_update.py                  # Full run: new results dir + retries + Excel
    python3 run_and_update.py --retry-only     # Only retry failures in existing results + Excel
    python3 run_and_update.py --excel-only     # Only rebuild Excel from existing results
    python3 run_and_update.py --max-retries 3  # Set max retry attempts (default: 2)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional, Dict

import requests
import aisuite as ai
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

BASE_DIR = Path(__file__).resolve().parent
RESULTS_ROOT = BASE_DIR / "results_data"
RESULTS_ROOT.mkdir(exist_ok=True)
ALGORITHMS_DIR = BASE_DIR / "algorithms"
PROPERTIES_DIR = BASE_DIR / "properties"
PROMPTS_DIR = BASE_DIR / "prompts"
XLSX_PATH = BASE_DIR / "versionControl.xlsx"

OLLAMA_MODELS = {
    "qwen2.5-coder-7b": "qwen2.5-coder:7b",
    "deepseek-coder-6.7b": "deepseek-coder:6.7b",
    "yi-coder-9b-chat": "yi-coder:9b-chat",
}

CODER_STYLE_MODELS = {"qwen2.5-coder-7b", "deepseek-coder-6.7b", "yi-coder-9b-chat"}

AISUITE_MODELS: dict[str, str] = {
    # "gpt-4.1": "openai:gpt-4.1",
}

IAEDU_MODELS = {
    "gpt-4o": "iaedu"
}

IAEDU_API_KEY = "sk-usr-93l8c9ximwa4y1c5wkc6hb6um7ef5f1oz3"
IAEDU_CHANNEL_ID = "cmo8gs64f23qtks0143jepxjc"
IAEDU_THREAD_ID = "AwlH9rxPMHbvYIGFAGJgJ"


# ═══════════════════════════════════════════════════════════════════════════════
# PART 1: TESTING (from script-2.py)
# ═══════════════════════════════════════════════════════════════════════════════

def get_next_results_dir(base_name="results") -> Path:
    i = 0
    while True:
        dir_name = base_name if i == 0 else f"{base_name}_{i}"
        path = RESULTS_ROOT / dir_name
        if not path.exists():
            path.mkdir()
            return path
        i += 1


def get_latest_results_dir() -> Path | None:
    """Find the most recent results_* directory."""
    dirs = []
    for p in sorted(RESULTS_ROOT.iterdir()):
        if not p.is_dir():
            continue
        m = re.fullmatch(r"results(?:_(\d+))?", p.name)
        if m:
            version = int(m.group(1)) if m.group(1) else 0
            dirs.append((version, p))
    if not dirs:
        return None
    dirs.sort(key=lambda x: x[0])
    return dirs[-1][1]


def slugify(text: str) -> str:
    return re.sub(r"[^\w\-\.]+", "_", text.strip().lower())


def read_file(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return path.read_text(encoding="utf-8").strip()


def build_task_prompt(prompt_template: str, algorithm_text: str, properties_text: str) -> str:
    return (
        prompt_template
        .replace("{algorithm}", algorithm_text)
        .replace("{properties}", properties_text)
    )


def wrap_prompt(model_label: str, task_prompt: str) -> str:
    if model_label in CODER_STYLE_MODELS:
        return f"### Instruction:\n{task_prompt}\n\n### Response:"
    return task_prompt


def query_ollama(model: str, prompt: str) -> str:
    response = requests.post(
        "http://localhost:11434/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        },
        timeout=600,
    )
    response.raise_for_status()
    data = response.json()
    return data["message"]["content"]


def query_aisuite(client: ai.Client, model: str, prompt: str) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )
    return response.choices[0].message.content


def query_iaedu(prompt: str) -> str:
    url = "https://api.iaedu.pt/agent-chat//api/v1/agent/cmamvd3n40000c801qeacoad2/stream"
    headers = {"x-api-key": IAEDU_API_KEY}
    data = {
        "channel_id": IAEDU_CHANNEL_ID,
        "thread_id": IAEDU_THREAD_ID,
        "user_info": str({}),
        "message": prompt,
    }
    response = requests.post(url, headers=headers, data=data, stream=False, timeout=600)
    response.raise_for_status()
    return response.text


def query_model(label: str, prompt: str, client: ai.Client | None = None) -> str:
    """Query a model by label. Returns the output text or an ERROR string."""
    final_prompt = wrap_prompt(label, prompt)

    if label in OLLAMA_MODELS:
        return query_ollama(OLLAMA_MODELS[label], final_prompt)
    elif label in AISUITE_MODELS:
        if client is None:
            raise ValueError("aisuite client required")
        return query_aisuite(client, AISUITE_MODELS[label], final_prompt)
    elif label in IAEDU_MODELS:
        result = query_iaedu(final_prompt)
        time.sleep(3)  # rate-limit courtesy
        return result
    else:
        return f"ERROR:\nUnknown model label: {label}"


def get_all_model_labels() -> list[str]:
    """Return all configured model labels."""
    return list(OLLAMA_MODELS.keys()) + list(AISUITE_MODELS.keys()) + list(IAEDU_MODELS.keys())


def run_single_test(
    results_dir: Path,
    algorithm_name: str,
    prompt_name: str,
    model_label: str,
    task_prompt: str,
    client: ai.Client | None = None,
) -> bool:
    """Run a single test and write the result. Returns True if no error."""
    result_dir = results_dir / slugify(algorithm_name) / slugify(prompt_name)
    result_dir.mkdir(parents=True, exist_ok=True)
    output_path = result_dir / f"{slugify(model_label)}.txt"

    try:
        output = query_model(model_label, task_prompt, client)
    except Exception as e:
        output = f"ERROR:\n{e}"

    output_path.write_text(output, encoding="utf-8")
    return not output.startswith("ERROR:")


def run_full_tests(results_dir: Path) -> None:
    """Run all algorithm × prompt × model combinations."""
    client = ai.Client()
    algorithm_files = sorted(ALGORITHMS_DIR.glob("*.txt"))
    prompt_files = sorted(PROMPTS_DIR.glob("*.txt"))

    if not algorithm_files:
        raise RuntimeError(f"No algorithm files found in {ALGORITHMS_DIR}")
    if not prompt_files:
        raise RuntimeError(f"No prompt files found in {PROMPTS_DIR}")

    all_models = get_all_model_labels()
    total = len(algorithm_files) * len(prompt_files) * len(all_models)
    done = 0

    for algorithm_file in algorithm_files:
        algorithm_name = algorithm_file.stem
        properties_file = PROPERTIES_DIR / f"{algorithm_name}.txt"
        if not properties_file.exists():
            print(f"  ⚠ Skipping {algorithm_name} (no properties file)")
            continue

        algorithm_text = read_file(algorithm_file)
        properties_text = read_file(properties_file)

        for prompt_file in prompt_files:
            prompt_name = prompt_file.stem
            prompt_template = read_file(prompt_file)
            task_prompt = build_task_prompt(prompt_template, algorithm_text, properties_text)

            for model_label in all_models:
                done += 1
                print(f"  [{done}/{total}] {algorithm_name} / {prompt_name} / {model_label} … ", end="", flush=True)
                ok = run_single_test(results_dir, algorithm_name, prompt_name, model_label, task_prompt, client)
                print("✓" if ok else "✗ ERROR")


# ═══════════════════════════════════════════════════════════════════════════════
# PART 2: FAILURE DETECTION & RETRY
# ═══════════════════════════════════════════════════════════════════════════════

def is_result_failed(file_path: Path) -> bool:
    """Check if a result file represents a failure (error, rate-limit, timeout)."""
    if not file_path.exists():
        return True

    raw = file_path.read_text(encoding="utf-8", errors="replace").strip()

    if not raw:
        return True

    # Plain text errors
    if raw.startswith("ERROR:") or raw.startswith("ERROR\n"):
        return True

    # Check for common error patterns
    lower = raw.lower()
    if "read timed out" in lower:
        return True
    if "rate limit reached" in lower and "429" in lower:
        return True
    if "connection refused" in lower:
        return True
    if "httpconnectionpool" in lower and "timed out" in lower:
        return True

    # GPT JSON-stream: check for error type without message type
    if _is_json_stream_check(raw):
        has_message = False
        has_error = False
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if obj.get("type") == "message":
                    has_message = True
                if obj.get("type") == "error":
                    has_error = True
            except json.JSONDecodeError:
                continue
        if has_error and not has_message:
            return True

    return False


def _is_json_stream_check(text: str) -> bool:
    """Quick check if file is GPT JSON-stream format."""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            return "run_id" in obj
        except json.JSONDecodeError:
            return False
    return False


def find_failures(results_dir: Path) -> list[tuple[str, str, str]]:
    """
    Scan a results directory and return list of (algorithm, prompt, model)
    tuples that have failed results.
    """
    failures = []
    if not results_dir.is_dir():
        return failures

    for algo_dir in sorted(results_dir.iterdir()):
        if not algo_dir.is_dir():
            continue
        algo_name = algo_dir.name

        for prompt_dir in sorted(algo_dir.iterdir()):
            if not prompt_dir.is_dir():
                continue
            prompt_name = prompt_dir.name

            for result_file in sorted(prompt_dir.glob("*.txt")):
                model_name = result_file.stem
                if is_result_failed(result_file):
                    failures.append((algo_name, prompt_name, model_name))

    return failures


def retry_failures(results_dir: Path, max_retries: int = 2) -> int:
    """
    Find failed results and retry them. Returns the number of tests
    that remain failed after all retries.
    """
    client = ai.Client()

    for attempt in range(1, max_retries + 1):
        failures = find_failures(results_dir)
        if not failures:
            print(f"\n  ✅ No failures found — all tests passed!")
            return 0

        print(f"\n  Retry attempt {attempt}/{max_retries}: {len(failures)} failed test(s) to retry")

        still_failed = 0
        for i, (algo_slug, prompt_slug, model_slug) in enumerate(failures, 1):
            # Resolve the original algorithm/prompt/model names
            # The slugified names in the results dir should match the slugified file stems
            algo_file = _find_matching_file(ALGORITHMS_DIR, algo_slug)
            prompt_file = _find_matching_file(PROMPTS_DIR, prompt_slug)
            model_label = _find_matching_model(model_slug)

            if not algo_file or not prompt_file or not model_label:
                print(f"    [{i}/{len(failures)}] ⚠ Cannot resolve: {algo_slug}/{prompt_slug}/{model_slug}")
                still_failed += 1
                continue

            algorithm_name = algo_file.stem
            properties_file = PROPERTIES_DIR / f"{algorithm_name}.txt"
            if not properties_file.exists():
                print(f"    [{i}/{len(failures)}] ⚠ No properties for: {algorithm_name}")
                still_failed += 1
                continue

            algorithm_text = read_file(algo_file)
            properties_text = read_file(properties_file)
            prompt_template = read_file(prompt_file)
            task_prompt = build_task_prompt(prompt_template, algorithm_text, properties_text)

            print(f"    [{i}/{len(failures)}] {algorithm_name}/{prompt_file.stem}/{model_label} … ", end="", flush=True)
            ok = run_single_test(results_dir, algorithm_name, prompt_file.stem, model_label, task_prompt, client)
            if ok:
                print("✓ fixed")
            else:
                print("✗ still failing")
                still_failed += 1

        if still_failed == 0:
            print(f"\n  ✅ All failures resolved after {attempt} attempt(s)!")
            return 0

    # Final count after all retries
    final_failures = find_failures(results_dir)
    return len(final_failures)


def _find_matching_file(directory: Path, slug: str) -> Path | None:
    """Find a .txt file in directory whose stem slugifies to the given slug."""
    for f in directory.glob("*.txt"):
        if slugify(f.stem) == slug:
            return f
    return None


def _find_matching_model(slug: str) -> str | None:
    """Find a model label that slugifies to the given slug."""
    for label in get_all_model_labels():
        if slugify(label) == slug:
            return label
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# PART 3: EXCEL UPDATE (from update_excel.py)
# ═══════════════════════════════════════════════════════════════════════════════

# --- Style constants ---
GREEN_FILL   = PatternFill(start_color="92D050",  end_color="92D050",  fill_type="solid")
RED_FILL     = PatternFill(start_color="FF0000",  end_color="FF0000",  fill_type="solid")
LIGHT_GREEN  = PatternFill(start_color="E2EFDA",  end_color="E2EFDA",  fill_type="solid")
LIGHT_RED    = PatternFill(start_color="FCE4EC",  end_color="FCE4EC",  fill_type="solid")
LIGHT_YELLOW = PatternFill(start_color="FFF9C4",  end_color="FFF9C4",  fill_type="solid")
LIGHT_BLUE   = PatternFill(start_color="D6E4F0",  end_color="D6E4F0",  fill_type="solid")
HEADER_FILL  = PatternFill(start_color="4472C4",  end_color="4472C4",  fill_type="solid")
SECTION_FILL = PatternFill(start_color="2F5496",  end_color="2F5496",  fill_type="solid")
ALGO_FILL    = PatternFill(start_color="D9E2F3",  end_color="D9E2F3",  fill_type="solid")
HEADER_FONT  = Font(bold=True, color="FFFFFF", size=11)
SECTION_FONT = Font(bold=True, color="FFFFFF", size=12)
BOLD         = Font(bold=True, size=11)
NORMAL       = Font(size=11)
SMALL_ITALIC = Font(italic=True, size=10, color="666666")
CENTER       = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT_AL      = Alignment(horizontal="left",   vertical="center", wrap_text=True)
THIN = Border(
    left=Side(style="thin"), right=Side(style="thin"),
    top=Side(style="thin"),  bottom=Side(style="thin"),
)


def discover_results_dirs() -> list[tuple[str, Path]]:
    dirs: list[tuple[str, Path]] = []
    for p in sorted(RESULTS_ROOT.iterdir()):
        if not p.is_dir():
            continue
        m = re.fullmatch(r"results(?:_(\d+))?", p.name)
        if m:
            version = m.group(1) if m.group(1) else "0"
            dirs.append((version, p))
    dirs.sort(key=lambda x: int(x[0]))
    return dirs


def load_properties() -> dict[str, list[str]]:
    props: dict[str, list[str]] = {}
    for f in sorted(PROPERTIES_DIR.glob("*.txt")):
        raw = f.read_text(encoding="utf-8").strip()
        names = [n.strip() for n in raw.replace("\n", ",").split(",") if n.strip()]
        props[f.stem] = names
    return props


# --- Result parsing (same as update_excel.py) ---

def _extract_gpt_message(text: str) -> str | None:
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") == "message":
            content = obj.get("content", {})
            if isinstance(content, dict):
                return content.get("content", "")
            return str(content)
        if obj.get("type") == "error":
            return None
    return None


def _is_json_stream(text: str) -> bool:
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            return "run_id" in obj
        except json.JSONDecodeError:
            return False
    return False


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def count_satisfied(text: str, expected_props: list[str]) -> tuple[int, int]:
    total = len(expected_props)
    if not text or not text.strip():
        return 0, total

    norm = _normalize(text)
    if norm.startswith("error"):
        return 0, total

    bulk_re = re.compile(
        r"(?:" + r",?\s*".join(re.escape(p.lower()) for p in expected_props) + r")"
        + r"\s*[-–:.]?\s*satisfied",
    )
    if bulk_re.search(norm):
        return total, total

    prop_positions: list[tuple[int, str]] = []
    for prop in expected_props:
        pattern = re.compile(re.escape(prop.lower()))
        for m in pattern.finditer(norm):
            prop_positions.append((m.start(), prop))
            break

    prop_positions.sort(key=lambda x: x[0])
    segments: dict[str, str] = {}
    for i, (pos, prop) in enumerate(prop_positions):
        end = prop_positions[i + 1][0] if i + 1 < len(prop_positions) else len(norm)
        segment_end = min(pos + 150, end)
        segments[prop] = norm[pos:segment_end]

    neg_patterns = [
        r"\[\s*non\s*satisfied", r"\[\s*not\s*satisfied",
        r"[-–:]\s*non\s*satisfied", r"[-–:]\s*not\s*satisfied",
        r"not\s+satisfied", r"non\s+satisfied",
        r":\s*no\b", r":\s*false\b", r"result:\s*false",
        r"[-–]\s*false\b", r"violated", r"not\s+met",
        r"[-–]\s*not\s", r"[-–]\s*non\s",
    ]
    pos_patterns = [
        r"\[\s*satisfied\s*\]", r"[-–]\s*satisfied",
        r":\s*satisfied", r"=\s*satisfied", r"is\s+satisfied",
        r":\s*yes\b", r":\s*true\b", r"result:\s*true", r"[-–]\s*true\b",
    ]

    satisfied = 0
    for prop in expected_props:
        segment = segments.get(prop)
        if segment is None:
            continue
        found_negative = any(re.search(p, segment) for p in neg_patterns)
        found_positive = any(re.search(p, segment) for p in pos_patterns)
        if found_negative:
            continue
        if found_positive:
            satisfied += 1

    return satisfied, total


def parse_result_file(file_path: Path, expected_props: list[str]) -> tuple[int, int, bool]:
    raw = file_path.read_text(encoding="utf-8", errors="replace")
    total = len(expected_props)
    if _is_json_stream(raw):
        message_text = _extract_gpt_message(raw)
        if message_text is None:
            return 0, total, False
        sat, tot = count_satisfied(message_text, expected_props)
        return sat, tot, sat == tot
    sat, tot = count_satisfied(raw, expected_props)
    return sat, tot, sat == tot


def scan_results_dir(results_path: Path, all_properties: dict[str, list[str]]):
    results: dict = {}
    if not results_path.is_dir():
        return results
    for algo_dir in sorted(results_path.iterdir()):
        if not algo_dir.is_dir():
            continue
        algo_name = algo_dir.name
        if algo_name not in all_properties:
            continue
        expected = all_properties[algo_name]
        results[algo_name] = {}
        for prompt_dir in sorted(algo_dir.iterdir()):
            if not prompt_dir.is_dir():
                continue
            prompt_name = prompt_dir.name
            results[algo_name][prompt_name] = {}
            for result_file in sorted(prompt_dir.glob("*.txt")):
                model_name = result_file.stem
                sat, tot, ok = parse_result_file(result_file, expected)
                results[algo_name][prompt_name][model_name] = (sat, tot, ok)
    return results


# --- Excel writing (compact version of update_excel.py sections 5-6) ---

def write_version_sheet(wb, version, version_data, all_properties):
    title = f"Version {version}"
    if title in wb.sheetnames:
        del wb[title]
    ws = wb.create_sheet(title)
    row = 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=15)
    ws.cell(row=row, column=1, value=f"Results {version}").font = Font(bold=True, size=14)
    ws.cell(row=row, column=1).alignment = CENTER
    row += 2

    for algo in sorted(version_data):
        algo_data = version_data[algo]
        props = all_properties.get(algo, [])
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=15)
        ws.cell(row=row, column=1, value=algo).font = Font(bold=True, size=12)
        ws.cell(row=row, column=1).fill = ALGO_FILL
        row += 1
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=15)
        ws.cell(row=row, column=1, value=f"Properties ({len(props)}): {', '.join(props)}").font = Font(italic=True, size=10)
        row += 1

        models_in_algo = sorted(set(m for p in algo_data for m in algo_data[p]))
        # Header
        for ci, val in enumerate(["Version", "Prompt"]):
            c = ws.cell(row=row, column=1+ci, value=val)
            c.font = HEADER_FONT; c.fill = HEADER_FILL; c.alignment = CENTER; c.border = THIN
        col = 3
        for model in models_in_algo:
            ws.merge_cells(start_row=row, start_column=col, end_row=row, end_column=col+1)
            c = ws.cell(row=row, column=col, value=model)
            c.font = HEADER_FONT; c.fill = HEADER_FILL; c.alignment = CENTER; c.border = THIN
            col += 2
        row += 1
        # Sub-header
        ws.cell(row=row, column=1).border = THIN
        ws.cell(row=row, column=2).border = THIN
        col = 3
        for _ in models_in_algo:
            ws.cell(row=row, column=col, value="✓").fill = GREEN_FILL
            ws.cell(row=row, column=col).alignment = CENTER; ws.cell(row=row, column=col).border = THIN
            ws.cell(row=row, column=col+1, value="✗").fill = RED_FILL
            ws.cell(row=row, column=col+1).alignment = CENTER; ws.cell(row=row, column=col+1).border = THIN
            ws.cell(row=row, column=col+1).font = Font(bold=True, color="FFFFFF")
            col += 2
        row += 1
        # Data
        for prompt in sorted(algo_data):
            ws.cell(row=row, column=1, value=int(version)).alignment = CENTER
            ws.cell(row=row, column=1).border = THIN
            ws.cell(row=row, column=2, value=prompt.replace("_"," ").title()).border = THIN
            col = 3
            for model in models_in_algo:
                g = ws.cell(row=row, column=col); r = ws.cell(row=row, column=col+1)
                g.fill = GREEN_FILL; g.alignment = CENTER; g.border = THIN
                r.fill = RED_FILL; r.alignment = CENTER; r.border = THIN
                if model in algo_data[prompt]:
                    sat, tot, ok = algo_data[prompt][model]
                    if ok:
                        g.value = sat; g.font = BOLD; r.value = ""
                    else:
                        g.value = ""; r.value = sat; r.font = Font(bold=True, color="FFFFFF")
                else:
                    g.value = ""; r.value = "N/A"
                col += 2
            row += 1
        row += 2

    ws.column_dimensions["A"].width = 10; ws.column_dimensions["B"].width = 20
    for i in range(3, 25):
        ws.column_dimensions[get_column_letter(i)].width = 12


def write_comparison_sheet(wb, all_data, all_properties):
    """Write the comparison/analysis sheet (simplified version)."""
    if "Results Comparison" in wb.sheetnames:
        del wb["Results Comparison"]
    ws = wb.create_sheet("Results Comparison", 0)

    # Aggregate
    model_s = defaultdict(lambda: {"s":0,"t":0})
    prompt_s = defaultdict(lambda: {"s":0,"t":0})
    algo_s = defaultdict(lambda: {"s":0,"t":0})
    ver_s = defaultdict(lambda: {"s":0,"t":0})

    for ver, algos in all_data.items():
        for algo, prompts in algos.items():
            for prompt, models in prompts.items():
                for model, (sat, tot, ok) in models.items():
                    v = 1 if ok else 0
                    model_s[model]["s"] += v; model_s[model]["t"] += 1
                    prompt_s[prompt]["s"] += v; prompt_s[prompt]["t"] += 1
                    algo_s[algo]["s"] += v; algo_s[algo]["t"] += 1
                    ver_s[ver]["s"] += v; ver_s[ver]["t"] += 1

    def pct(s, t): return round(100*s/t, 1) if t else 0

    NCOLS = 8
    row = 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
    ws.cell(row=row, column=1, value="Results Comparison & Analysis").font = Font(bold=True, size=16)
    row += 2

    # Model ranking
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
    ws.cell(row=row, column=1, value="Model Ranking").font = SECTION_FONT
    ws.cell(row=row, column=1).fill = SECTION_FILL
    row += 1
    for rank, (m, s) in enumerate(sorted(model_s.items(), key=lambda x: pct(x[1]["s"],x[1]["t"]), reverse=True), 1):
        ws.cell(row=row, column=1, value=rank).border = THIN
        ws.cell(row=row, column=2, value=m).border = THIN
        ws.cell(row=row, column=3, value=s["s"]).border = THIN
        ws.cell(row=row, column=4, value=s["t"]).border = THIN
        ws.cell(row=row, column=5, value=pct(s["s"],s["t"])).border = THIN
        row += 1
    row += 1

    # Prompt ranking
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
    ws.cell(row=row, column=1, value="Prompt Ranking").font = SECTION_FONT
    ws.cell(row=row, column=1).fill = SECTION_FILL
    row += 1
    for rank, (p, s) in enumerate(sorted(prompt_s.items(), key=lambda x: pct(x[1]["s"],x[1]["t"]), reverse=True), 1):
        ws.cell(row=row, column=1, value=rank).border = THIN
        ws.cell(row=row, column=2, value=p.replace("_"," ").title()).border = THIN
        ws.cell(row=row, column=3, value=s["s"]).border = THIN
        ws.cell(row=row, column=4, value=s["t"]).border = THIN
        ws.cell(row=row, column=5, value=pct(s["s"],s["t"])).border = THIN
        row += 1
    row += 1

    # Algorithm ranking
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
    ws.cell(row=row, column=1, value="Algorithm Ranking (Verification Difficulty)").font = SECTION_FONT
    ws.cell(row=row, column=1).fill = SECTION_FILL
    row += 1
    for rank, (a, s) in enumerate(sorted(algo_s.items(), key=lambda x: pct(x[1]["s"],x[1]["t"]), reverse=True), 1):
        ws.cell(row=row, column=1, value=rank).border = THIN
        ws.cell(row=row, column=2, value=a).border = THIN
        ws.cell(row=row, column=3, value=s["s"]).border = THIN
        ws.cell(row=row, column=4, value=s["t"]).border = THIN
        ws.cell(row=row, column=5, value=pct(s["s"],s["t"])).border = THIN
        row += 1

    ws.column_dimensions["A"].width = 8; ws.column_dimensions["B"].width = 40
    for i in range(3, NCOLS+1):
        ws.column_dimensions[get_column_letter(i)].width = 14


def rebuild_excel(all_properties: dict[str, list[str]]) -> None:
    """Scan all results dirs and rebuild versionControl.xlsx."""
    results_dirs = discover_results_dirs()
    if not results_dirs:
        print("\n  ⚠ No results directories found. Skipping Excel update.")
        return

    all_data: dict[str, dict] = {}
    for ver, path in results_dirs:
        version_data = scan_results_dir(path, all_properties)
        if version_data:
            all_data[ver] = version_data

    if not all_data:
        print("\n  ⚠ No parseable results. Skipping Excel update.")
        return

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    for ver in sorted(all_data, key=lambda x: int(x)):
        write_version_sheet(wb, ver, all_data[ver], all_properties)

    write_comparison_sheet(wb, all_data, all_properties)
    wb.save(str(XLSX_PATH))
    print(f"\n  ✅ Excel saved: {XLSX_PATH}")
    print(f"     Sheets: {wb.sheetnames}")


# ═══════════════════════════════════════════════════════════════════════════════
# PART 4: MAIN — ORCHESTRATION
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Run LLM verification experiments, retry failures, update Excel."
    )
    parser.add_argument("--retry-only", action="store_true",
                        help="Only retry failures in the latest results dir (no new run)")
    parser.add_argument("--excel-only", action="store_true",
                        help="Only rebuild Excel from existing results (no testing)")
    parser.add_argument("--max-retries", type=int, default=2,
                        help="Maximum retry attempts for failed tests (default: 2)")
    args = parser.parse_args()

    print("╔═══════════════════════════════════════════════════════════╗")
    print("║   run_and_update.py — Test, Retry, Update                 ║")
    print("╚═══════════════════════════════════════════════════════════╝\n")

    all_properties = load_properties()
    print(f"Loaded properties for {len(all_properties)} algorithms")

    # ── Mode: Excel only ──
    if args.excel_only:
        print("\n📊 Rebuilding Excel from existing results …")
        rebuild_excel(all_properties)
        return

    # ── Mode: Retry only ──
    if args.retry_only:
        results_dir = get_latest_results_dir()
        if not results_dir:
            print("\n⚠ No results directory found. Run without --retry-only first.")
            sys.exit(1)
        print(f"\n🔄 Retrying failures in: {results_dir.name}")
        remaining = retry_failures(results_dir, max_retries=args.max_retries)
        if remaining:
            print(f"\n  ⚠ {remaining} test(s) still failing after {args.max_retries} retries")
        print("\n📊 Updating Excel …")
        rebuild_excel(all_properties)
        return

    # ── Mode: Full run ──
    results_dir = get_next_results_dir()
    print(f"\n🧪 Running full test suite → {results_dir.name}")
    run_full_tests(results_dir)

    # Retry failures
    print(f"\n🔄 Checking for failures and retrying (max {args.max_retries} attempts) …")
    remaining = retry_failures(results_dir, max_retries=args.max_retries)
    if remaining:
        print(f"\n  ⚠ {remaining} test(s) still failing after all retries")

    # Update Excel
    print("\n📊 Updating Excel …")
    rebuild_excel(all_properties)

    print("\n✅ Done!")


if __name__ == "__main__":
    main()
