#!/usr/bin/env python3
"""
update_excel.py — Scan every results_* folder and rebuild versionControl.xlsx.

Run after script-2.py produces a new results_N directory:

    python3 update_excel.py

The script:
  1. Auto-discovers every results_* folder and treats the suffix as the version.
  2. Reads properties/<algorithm>.txt to know what must be satisfied.
  3. Parses each result file (plain text or GPT JSON-stream).
  4. Writes one "Version N" sheet per results folder (green / red layout).
  5. Writes a "Results Comparison" sheet as the first tab with rankings,
     heatmaps, trends and recommendations.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# ═══════════════════════════════════════════════════════════════════════════════
# Paths
# ═══════════════════════════════════════════════════════════════════════════════
BASE_DIR = Path(__file__).resolve().parent
RESULTS_ROOT = BASE_DIR / "results_data"
PROPERTIES_DIR = BASE_DIR / "properties_v3"
XLSX_PATH = BASE_DIR / "versionControl.xlsx"

# ═══════════════════════════════════════════════════════════════════════════════
# Style constants
# ═══════════════════════════════════════════════════════════════════════════════
GREEN_FILL   = PatternFill(start_color="92D050",  end_color="92D050",  fill_type="solid")
RED_FILL     = PatternFill(start_color="FF0000",  end_color="FF0000",  fill_type="solid")
LIGHT_GREEN  = PatternFill(start_color="E2EFDA",  end_color="E2EFDA",  fill_type="solid")
LIGHT_RED    = PatternFill(start_color="FCE4EC",  end_color="FCE4EC",  fill_type="solid")
LIGHT_YELLOW = PatternFill(start_color="FFF9C4",  end_color="FFF9C4",  fill_type="solid")
LIGHT_BLUE   = PatternFill(start_color="D6E4F0",  end_color="D6E4F0",  fill_type="solid")
HEADER_FILL  = PatternFill(start_color="4472C4",  end_color="4472C4",  fill_type="solid")
SECTION_FILL = PatternFill(start_color="2F5496",  end_color="2F5496",  fill_type="solid")
ALGO_FILL    = PatternFill(start_color="D9E2F3",  end_color="D9E2F3",  fill_type="solid")
ORANGE_FILL  = PatternFill(start_color="FFC000",  end_color="FFC000",  fill_type="solid")
GRAY_FILL    = PatternFill(start_color="A6A6A6",  end_color="A6A6A6",  fill_type="solid")
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


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Discover results folders
# ═══════════════════════════════════════════════════════════════════════════════

def discover_results_dirs() -> list[tuple[str, Path]]:
    """Return sorted list of (version_label, path) for every results* dir."""
    dirs: list[tuple[str, Path]] = []
    root = RESULTS_ROOT if RESULTS_ROOT.is_dir() else BASE_DIR
    for p in sorted(root.iterdir()):
        if not p.is_dir():
            continue
        name = p.name
        # Match "results", "results_1", "results_2", …
        m = re.fullmatch(r"results(?:_(\d+))?", name)
        if m:
            version = m.group(1) if m.group(1) else "0"
            dirs.append((version, p))
    dirs.sort(key=lambda x: int(x[0]))
    return dirs


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Load expected properties per algorithm
# ═══════════════════════════════════════════════════════════════════════════════

def load_properties() -> dict[str, list[str]]:
    """Read properties/<algo>.txt → list of property names."""
    props: dict[str, list[str]] = {}
    for f in sorted(PROPERTIES_DIR.glob("*.txt")):
        raw = f.read_text(encoding="utf-8").strip()
        # Properties are comma-separated on one or more lines
        names = [n.strip() for n in raw.replace("\n", ",").split(",") if n.strip()]
        props[f.stem] = names
    return props


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Parse a single result file
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_gpt_message(text: str) -> str | None:
    """If the file is GPT JSON-stream, pull the 'message' content field."""
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
            return None  # rate-limit or server error → no usable response
    return None


def _is_json_stream(text: str) -> bool:
    """Heuristic: file starts with a JSON object containing 'run_id'."""
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
    """Lowercase, collapse whitespace."""
    return re.sub(r"\s+", " ", text.lower().strip())


def count_satisfied(text: str, expected_props: list[str]) -> tuple[int, int, str]:
    """
    Return (satisfied_count, total_properties, classification).

    Classification is one of:
      - "error"            : file contains a timeout, rate-limit, connection error, etc.
      - "correct"          : all properties satisfied in a recognized format
      - "wrong"            : structured output but some properties marked non-satisfied
      - "incorrect_output" : response doesn't follow expected format (prose, off-topic,
                             wrong properties, etc.)

    Recognized correct formats for a property verdict:
      - Property - [satisfied]
      - Property - satisfied
      - Property [satisfied]
      - Property: satisfied
      - Property = satisfied
      - Property - true / Property: true / Property: yes
      - Bulk: "Prop1, Prop2, Prop3 - Satisfied" (all on one line)
    """
    total = len(expected_props)
    if not text or not text.strip():
        return 0, total, "error"

    norm = _normalize(text)

    # ── Detect errors (no response received) ──
    error_indicators = [
        "error:", "error\n",
        "rate limit reached", "429",
        "read timed out", "timed out",
        "connection refused", "connectionpool",
        "httpconnectionpool",
    ]
    if any(norm.startswith(e) or e in norm[:100] for e in error_indicators[:3]):
        if norm.startswith("error") or ("rate limit" in norm and "429" in norm):
            return 0, total, "error"
    if "timed out" in norm and len(norm) < 200:
        return 0, total, "error"
    if "connection refused" in norm:
        return 0, total, "error"

    # ── Check for bulk verdict: all props listed then one "satisfied" ──
    bulk_re = re.compile(
        r"(?:" + r",?\s*".join(re.escape(p.lower()) for p in expected_props) + r")"
        + r"\s*[-–:.]?\s*satisfied",
    )
    if bulk_re.search(norm):
        return total, total, "correct"

    # ── Split text into per-property segments ──
    prop_positions: list[tuple[int, str]] = []
    for prop in expected_props:
        pattern = re.compile(re.escape(prop.lower()))
        last_match = None
        for m in pattern.finditer(norm):
            last_match = m
        if last_match:
            prop_positions.append((last_match.start(), prop))

    # If fewer than half the expected properties are even mentioned,
    # the output is likely off-topic or uses wrong property names
    if len(prop_positions) < len(expected_props) / 2:
        return 0, total, "incorrect_output"

    prop_positions.sort(key=lambda x: x[0])

    segments: dict[str, str] = {}
    for i, (pos, prop) in enumerate(prop_positions):
        end = prop_positions[i + 1][0] if i + 1 < len(prop_positions) else len(norm)
        segment_end = min(pos + 150, end)
        segments[prop] = norm[pos:segment_end]

    # ── Patterns for structured verdicts ──
    # Positive: property is satisfied
    pos_patterns = [
        r"\[\s*satisfied\s*\]",       # [satisfied]
        r"[-–]\s*\[?\s*satisfied",    # - satisfied / - [satisfied]
        r":\s*\[?\s*satisfied",       # : satisfied / : [satisfied]
        r"=\s*satisfied",             # = satisfied
        r"is\s+satisfied",            # is satisfied
        r":\s*yes\b",                 # : yes
        r":\s*true\b",               # : true
        r"result:\s*true",            # result: true
        r"[-–]\s*true\b",            # - true
    ]
    # Negative: property is explicitly not satisfied
    neg_patterns = [
        r"\[\s*non\s*satisfied",      # [non satisfied]
        r"\[\s*not\s*satisfied",      # [not satisfied]
        r"[-–:]\s*\[?\s*non\s*satisfied",
        r"[-–:]\s*\[?\s*not\s*satisfied",
        r"not\s+satisfied",
        r"non\s+satisfied",
        r":\s*no\b",
        r":\s*false\b",
        r"result:\s*false",
        r"[-–]\s*false\b",
        r"violated",
        r"not\s+met",
        r"[-–]\s*not\s",
        r"[-–]\s*non\s",
    ]

    satisfied = 0
    structured_count = 0  # how many properties had a recognizable verdict format

    for prop in expected_props:
        segment = segments.get(prop)
        if segment is None:
            continue  # property not mentioned

        found_negative = any(re.search(p, segment) for p in neg_patterns)
        found_positive = any(re.search(p, segment) for p in pos_patterns)

        if found_negative:
            structured_count += 1
            continue  # explicitly non-satisfied
        if found_positive:
            structured_count += 1
            satisfied += 1

    # ── Classify the result ──
    if structured_count == 0:
        # No property had a recognizable verdict → incorrect output format
        return 0, total, "incorrect_output"

    if structured_count < len(expected_props) / 2:
        # Too few structured verdicts → mostly unstructured prose
        return satisfied, total, "incorrect_output"

    if satisfied == total:
        return satisfied, total, "correct"
    else:
        return satisfied, total, "wrong"


def parse_result_file(file_path: Path, expected_props: list[str]) -> tuple[int, int, str]:
    """
    Parse one result file.
    Returns (satisfied_count, total_properties, classification).

    Classification: "error" | "correct" | "wrong" | "incorrect_output"
    """
    raw = file_path.read_text(encoding="utf-8", errors="replace")
    total = len(expected_props)

    # Empty file
    if not raw.strip():
        return 0, total, "error"

    # Handle GPT JSON-stream files
    if _is_json_stream(raw):
        message_text = _extract_gpt_message(raw)
        if message_text is None:
            # Error / rate-limit → no response
            return 0, total, "error"
        return count_satisfied(message_text, expected_props)

    # Plain text — check for error patterns first
    norm_start = raw.strip().lower()[:200]
    if norm_start.startswith("error:") or norm_start.startswith("error\n"):
        return 0, total, "error"
    if "read timed out" in norm_start:
        return 0, total, "error"
    if "rate limit reached" in norm_start and "429" in norm_start:
        return 0, total, "error"
    if "connection refused" in norm_start:
        return 0, total, "error"

    # Parse the content
    return count_satisfied(raw, expected_props)


# ═══════════════════════════════════════════════════════════════════════════════
# 3b. Parse per-property verdicts from a single result file
# ═══════════════════════════════════════════════════════════════════════════════

def parse_per_property_verdicts(file_path: Path, expected_props: list[str]) -> dict[str, str] | None:
    """
    Parse one result file and return per-property verdicts.

    Returns:
      dict mapping property name → "satisfied" | "non_satisfied"
      or None if the file is an error/unparseable.

    Only returns results when at least half of the expected properties
    have a recognizable verdict.
    """
    raw = file_path.read_text(encoding="utf-8", errors="replace")

    if not raw.strip():
        return None

    # Handle GPT JSON-stream files
    if _is_json_stream(raw):
        text = _extract_gpt_message(raw)
        if text is None:
            return None
    else:
        text = raw

    # Check for error patterns
    norm_start = text.strip().lower()[:200]
    if norm_start.startswith("error:") or norm_start.startswith("error\n"):
        return None
    if "read timed out" in norm_start:
        return None
    if "rate limit reached" in norm_start and "429" in norm_start:
        return None
    if "connection refused" in norm_start:
        return None
    if "gemini failed" in norm_start:
        return None

    norm = _normalize(text)

    # Reuse the same parsing logic from count_satisfied
    pos_patterns = [
        r"\[\s*satisfied\s*\]",
        r"[-–]\s*\[?\s*satisfied",
        r":\s*\[?\s*satisfied",
        r"=\s*satisfied",
        r"is\s+satisfied",
        r":\s*yes\b",
        r":\s*true\b",
        r"result:\s*true",
        r"[-–]\s*true\b",
    ]
    neg_patterns = [
        r"\[\s*non\s*satisfied",
        r"\[\s*not\s*satisfied",
        r"[-–:]\s*\[?\s*non\s*satisfied",
        r"[-–:]\s*\[?\s*not\s*satisfied",
        r"not\s+satisfied",
        r"non\s+satisfied",
        r":\s*no\b",
        r":\s*false\b",
        r"result:\s*false",
        r"[-–]\s*false\b",
        r"violated",
        r"not\s+met",
        r"[-–]\s*not\s",
        r"[-–]\s*non\s",
    ]

    # Find property positions
    prop_positions: list[tuple[int, str]] = []
    for prop in expected_props:
        pattern = re.compile(re.escape(prop.lower()))
        last_match = None
        for m in pattern.finditer(norm):
            last_match = m
        if last_match:
            prop_positions.append((last_match.start(), prop))

    if len(prop_positions) < len(expected_props) / 2:
        return None

    prop_positions.sort(key=lambda x: x[0])

    segments: dict[str, str] = {}
    for i, (pos, prop) in enumerate(prop_positions):
        end = prop_positions[i + 1][0] if i + 1 < len(prop_positions) else len(norm)
        segment_end = min(pos + 150, end)
        segments[prop] = norm[pos:segment_end]

    verdicts: dict[str, str] = {}
    structured_count = 0

    for prop in expected_props:
        segment = segments.get(prop)
        if segment is None:
            continue

        found_negative = any(re.search(p, segment) for p in neg_patterns)
        found_positive = any(re.search(p, segment) for p in pos_patterns)

        if found_negative:
            verdicts[prop] = "non_satisfied"
            structured_count += 1
        elif found_positive:
            verdicts[prop] = "satisfied"
            structured_count += 1

    if structured_count < len(expected_props) / 2:
        return None

    return verdicts


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Scan a results directory → structured data
# ═══════════════════════════════════════════════════════════════════════════════

def scan_results_dir(
    results_path: Path,
    all_properties: dict[str, list[str]],
) -> dict[str, dict[str, dict[str, tuple[int, int, str]]]]:
    """
    Returns:
      { algorithm: { prompt: { model: (sat, total, classification) } } }

    classification is one of: "error", "correct", "wrong", "incorrect_output"
    """
    results: dict = {}
    if not results_path.is_dir():
        return results

    for algo_dir in sorted(results_path.iterdir()):
        if not algo_dir.is_dir():
            continue
        algo_name = algo_dir.name
        if algo_name not in all_properties:
            print(f"  ⚠ Skipping unknown algorithm '{algo_name}' (no properties file)")
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
                sat, tot, classification = parse_result_file(result_file, expected)
                results[algo_name][prompt_name][model_name] = (sat, tot, classification)

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Write a "Version N" sheet
# ═══════════════════════════════════════════════════════════════════════════════

def write_version_sheet(
    wb: openpyxl.Workbook,
    version: str,
    version_data: dict,
    all_properties: dict[str, list[str]],
):
    title = f"Version {version}"
    if title in wb.sheetnames:
        del wb[title]
    ws = wb.create_sheet(title)

    row = 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=15)
    c = ws.cell(row=row, column=1, value=f"Results {version}")
    c.font = Font(bold=True, size=14); c.alignment = CENTER
    row += 2

    for algo in sorted(version_data):
        algo_data = version_data[algo]
        props = all_properties[algo]
        total_props = len(props)

        # Algorithm header
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=15)
        ac = ws.cell(row=row, column=1, value=algo)
        ac.font = Font(bold=True, size=12); ac.alignment = LEFT_AL; ac.fill = ALGO_FILL
        row += 1

        props_str = ", ".join(props)
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=15)
        ws.cell(row=row, column=1,
                value=f"Properties ({total_props}): {props_str}").font = Font(italic=True, size=10)
        row += 1

        # Collect all models across prompts for this algorithm
        models_in_algo: list[str] = []
        for prompt in sorted(algo_data):
            for model in algo_data[prompt]:
                if model not in models_in_algo:
                    models_in_algo.append(model)
        models_in_algo.sort()

        # Header row: Version | Prompt | model1 (merged 2 cols) | model2 …
        hdr = row
        for ci, val in enumerate(["Version", "Prompt"]):
            c = ws.cell(row=hdr, column=1 + ci, value=val)
            c.font = HEADER_FONT; c.fill = HEADER_FILL; c.alignment = CENTER; c.border = THIN

        col = 3
        for model in models_in_algo:
            ws.merge_cells(start_row=hdr, start_column=col, end_row=hdr, end_column=col + 1)
            mc = ws.cell(row=hdr, column=col, value=model)
            mc.font = HEADER_FONT; mc.fill = HEADER_FILL; mc.alignment = CENTER; mc.border = THIN
            ws.cell(row=hdr, column=col + 1).border = THIN
            col += 2
        row += 1

        # Sub-header: ✓ / ✗ / ⚠ / ✕
        ws.cell(row=row, column=1).border = THIN
        ws.cell(row=row, column=2).border = THIN
        col = 3
        for _ in models_in_algo:
            gc = ws.cell(row=row, column=col, value="✓")
            gc.fill = GREEN_FILL; gc.alignment = CENTER; gc.border = THIN; gc.font = BOLD
            rc = ws.cell(row=row, column=col + 1, value="✗")
            rc.fill = RED_FILL; rc.alignment = CENTER; rc.border = THIN
            rc.font = Font(bold=True, color="FFFFFF")
            col += 2
        row += 1

        # Data rows
        for prompt in sorted(algo_data):
            ws.cell(row=row, column=1, value=int(version)).alignment = CENTER
            ws.cell(row=row, column=1).border = THIN; ws.cell(row=row, column=1).font = NORMAL
            ws.cell(row=row, column=2,
                    value=prompt.replace("_", " ").title()).alignment = LEFT_AL
            ws.cell(row=row, column=2).border = THIN; ws.cell(row=row, column=2).font = NORMAL

            col = 3
            for model in models_in_algo:
                g_cell = ws.cell(row=row, column=col)
                r_cell = ws.cell(row=row, column=col + 1)
                g_cell.alignment = CENTER; g_cell.border = THIN
                r_cell.alignment = CENTER; r_cell.border = THIN

                if model in algo_data[prompt]:
                    sat, tot, classification = algo_data[prompt][model]

                    if classification == "correct":
                        # Green: all properties satisfied
                        g_cell.fill = GREEN_FILL
                        g_cell.value = sat; g_cell.font = BOLD
                        r_cell.fill = GREEN_FILL
                        r_cell.value = ""
                    elif classification == "wrong":
                        # Red: structured answer but some properties non-satisfied
                        g_cell.fill = RED_FILL
                        g_cell.value = ""
                        r_cell.fill = RED_FILL
                        r_cell.value = sat
                        r_cell.font = Font(bold=True, color="FFFFFF")
                    elif classification == "incorrect_output":
                        # Orange: response doesn't follow expected format
                        g_cell.fill = ORANGE_FILL
                        g_cell.value = ""
                        r_cell.fill = ORANGE_FILL
                        r_cell.value = "FMT"
                        r_cell.font = Font(bold=True)
                    elif classification == "error":
                        # Gray: no response (timeout, rate-limit, etc.)
                        g_cell.fill = GRAY_FILL
                        g_cell.value = ""
                        r_cell.fill = GRAY_FILL
                        r_cell.value = "ERR"
                        r_cell.font = Font(bold=True, color="FFFFFF")
                    else:
                        g_cell.fill = GREEN_FILL; g_cell.value = ""
                        r_cell.fill = RED_FILL; r_cell.value = sat
                else:
                    g_cell.value = ""; g_cell.fill = GRAY_FILL
                    r_cell.value = "N/A"; r_cell.fill = GRAY_FILL
                    r_cell.font = Font(italic=True, color="FFFFFF")
                col += 2
            row += 1
        row += 2

    # Legend
    legend_items = [
        (GREEN_FILL, "Green = Correct (all properties satisfied)"),
        (RED_FILL, "Red = Wrong answer (structured but some properties non-satisfied)"),
        (ORANGE_FILL, "Orange/FMT = Incorrect output format (prose, off-topic, wrong properties)"),
        (GRAY_FILL, "Gray/ERR = Error (timeout, rate-limit, no response)"),
    ]
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=15)
    ws.cell(row=row, column=1, value="Legend:").font = Font(bold=True, size=10)
    row += 1
    for fill, desc in legend_items:
        ws.cell(row=row, column=1).fill = fill
        ws.cell(row=row, column=1).border = THIN
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=10)
        ws.cell(row=row, column=2, value=desc).font = Font(size=10)
        row += 1

    ws.column_dimensions["A"].width = 10
    ws.column_dimensions["B"].width = 20
    for i in range(3, 3 + 10 * 2):
        ws.column_dimensions[get_column_letter(i)].width = 12


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Write the "Results Comparison" sheet
# ═══════════════════════════════════════════════════════════════════════════════

def _pct(s: int, t: int) -> float:
    return round(100 * s / t, 1) if t else 0


def _write_header(ws, row, headers, col_start=1):
    for i, h in enumerate(headers):
        c = ws.cell(row=row, column=col_start + i, value=h)
        c.font = HEADER_FONT; c.fill = HEADER_FILL; c.alignment = CENTER; c.border = THIN
    return row + 1


def _write_row(ws, row, values, highlight_col=None, best=None, worst=None):
    for i, v in enumerate(values):
        c = ws.cell(row=row, column=1 + i, value=v)
        c.alignment = CENTER; c.border = THIN; c.font = NORMAL
        if i == 0:
            c.alignment = LEFT_AL
        if highlight_col is not None and i == highlight_col:
            if v == best:
                c.fill = LIGHT_GREEN; c.font = BOLD
            elif v == worst:
                c.fill = LIGHT_RED; c.font = BOLD
    return row + 1


def _section(ws, row, title, ncols):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncols)
    c = ws.cell(row=row, column=1, value=title)
    c.font = SECTION_FONT; c.fill = SECTION_FILL; c.alignment = LEFT_AL; c.border = THIN
    return row + 1


def _insight(ws, row, text, ncols):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncols)
    c = ws.cell(row=row, column=1, value=text)
    c.font = SMALL_ITALIC; c.alignment = LEFT_AL
    return row + 1


def _heatmap_color(cell, value):
    if not isinstance(value, (int, float)):
        return
    if value >= 60:
        cell.fill = LIGHT_GREEN
    elif value <= 20:
        cell.fill = LIGHT_RED
    else:
        cell.fill = LIGHT_YELLOW


def write_comparison_sheet(
    wb: openpyxl.Workbook,
    all_data: dict[str, dict],
    all_properties: dict[str, list[str]],
):
    if "Results Comparison" in wb.sheetnames:
        del wb["Results Comparison"]
    ws = wb.create_sheet("Results Comparison", 0)

    # ── Aggregate stats ──
    model_s   = defaultdict(lambda: {"s": 0, "t": 0})
    prompt_s  = defaultdict(lambda: {"s": 0, "t": 0})
    algo_s    = defaultdict(lambda: {"s": 0, "t": 0})
    ver_s     = defaultdict(lambda: {"s": 0, "t": 0})
    mp_s      = defaultdict(lambda: {"s": 0, "t": 0})
    ma_s      = defaultdict(lambda: {"s": 0, "t": 0})
    pa_s      = defaultdict(lambda: {"s": 0, "t": 0})
    vm_s      = defaultdict(lambda: {"s": 0, "t": 0})
    vp_s      = defaultdict(lambda: {"s": 0, "t": 0})
    va_s      = defaultdict(lambda: {"s": 0, "t": 0})

    all_models  = set()
    all_prompts = set()
    all_algos   = set()

    for ver, algos in all_data.items():
        for algo, prompts in algos.items():
            all_algos.add(algo)
            for prompt, models in prompts.items():
                all_prompts.add(prompt)
                for model, (sat, tot, classification) in models.items():
                    all_models.add(model)
                    if classification == "error":
                        continue
                    v = 1 if classification == "correct" else 0
                    for d, k in [
                        (model_s, model), (prompt_s, prompt), (algo_s, algo), (ver_s, ver),
                        (mp_s, (model, prompt)), (ma_s, (model, algo)), (pa_s, (prompt, algo)),
                        (vm_s, (ver, model)), (vp_s, (ver, prompt)), (va_s, (ver, algo)),
                    ]:
                        d[k]["s"] += v; d[k]["t"] += 1

    all_models_sorted  = sorted(all_models)
    all_prompts_sorted = sorted(all_prompts)
    all_algos_sorted   = sorted(all_algos)
    versions_sorted    = sorted(all_data.keys(), key=lambda x: int(x))

    NCOLS = max(8, 2 + len(all_algos_sorted), 2 + len(all_prompts_sorted))
    row = 1

    # Title
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
    ws.cell(row=row, column=1, value="Results Comparison & Analysis").font = Font(bold=True, size=16)
    ws.cell(row=row, column=1).alignment = CENTER
    row += 2

    # ── 1. Overall by version ──
    row = _section(ws, row, "1. Overall Success Rate by Version", NCOLS)
    row = _write_header(ws, row, ["Version", "Successes", "Total Tests", "Success Rate (%)"])
    vp_map = {v: _pct(ver_s[v]["s"], ver_s[v]["t"]) for v in versions_sorted}
    bv, wv = max(vp_map.values()), min(vp_map.values())
    for v in versions_sorted:
        row = _write_row(ws, row, [f"Version {v}", ver_s[v]["s"], ver_s[v]["t"], vp_map[v]],
                         highlight_col=3, best=bv, worst=wv)
    row += 1

    # ── 2. Model ranking ──
    row = _section(ws, row, "2. Model Ranking (All Versions Combined)", NCOLS)
    row = _write_header(ws, row, ["Rank", "Model", "Successes", "Total Tests", "Success Rate (%)"])
    ranked_m = sorted(model_s.items(), key=lambda x: _pct(x[1]["s"], x[1]["t"]), reverse=True)
    pcts = [_pct(v["s"], v["t"]) for _, v in ranked_m]
    bm, wm = max(pcts), min(pcts)
    for rank, (m, s) in enumerate(ranked_m, 1):
        row = _write_row(ws, row, [rank, m, s["s"], s["t"], _pct(s["s"], s["t"])],
                         highlight_col=4, best=bm, worst=wm)
    best_model, worst_model = ranked_m[0][0], ranked_m[-1][0]
    row = _insight(ws, row,
        f"Best model: {best_model} | Worst model: {worst_model} — "
        f"consider improving prompts for {worst_model} or replacing it.", NCOLS)
    row += 1

    # ── 3. Prompt ranking ──
    row = _section(ws, row, "3. Prompt Template Ranking (All Versions Combined)", NCOLS)
    row = _write_header(ws, row, ["Rank", "Prompt", "Successes", "Total Tests", "Success Rate (%)"])
    ranked_p = sorted(prompt_s.items(), key=lambda x: _pct(x[1]["s"], x[1]["t"]), reverse=True)
    pcts = [_pct(v["s"], v["t"]) for _, v in ranked_p]
    bp, wp = max(pcts), min(pcts)
    for rank, (p, s) in enumerate(ranked_p, 1):
        row = _write_row(ws, row, [rank, p.replace("_", " ").title(), s["s"], s["t"],
                                   _pct(s["s"], s["t"])],
                         highlight_col=4, best=bp, worst=wp)
    best_prompt = ranked_p[0][0].replace("_", " ").title()
    worst_prompt = ranked_p[-1][0].replace("_", " ").title()
    row = _insight(ws, row,
        f"Best prompt: {best_prompt} | Worst prompt: {worst_prompt} — "
        f"the {worst_prompt} template needs redesign.", NCOLS)
    row += 1

    # ── 4. Algorithm ranking ──
    row = _section(ws, row, "4. Algorithm Ranking — Verification Difficulty (All Versions Combined)", NCOLS)
    row = _write_header(ws, row, ["Rank", "Algorithm", "Properties", "Successes",
                                   "Total Tests", "Success Rate (%)"])
    ranked_a = sorted(algo_s.items(), key=lambda x: _pct(x[1]["s"], x[1]["t"]), reverse=True)
    pcts = [_pct(v["s"], v["t"]) for _, v in ranked_a]
    ba, wa = max(pcts), min(pcts)
    for rank, (a, s) in enumerate(ranked_a, 1):
        row = _write_row(ws, row, [rank, a, len(all_properties.get(a, [])),
                                   s["s"], s["t"], _pct(s["s"], s["t"])],
                         highlight_col=5, best=ba, worst=wa)
    easiest = ranked_a[0][0]; hardest = ranked_a[-1][0]
    row = _insight(ws, row,
        f"Easiest to verify: {easiest} | Hardest to verify: {hardest} — "
        f"focus prompt improvements on {hardest}.", NCOLS)
    row += 1

    # ── 5. Model × Prompt heatmap ──
    row = _section(ws, row, "5. Model × Prompt Success Rate (%)", NCOLS)
    row = _write_header(ws, row, ["Model"] + [p.replace("_", " ").title() for p in all_prompts_sorted])
    for m in all_models_sorted:
        vals = [m]
        for p in all_prompts_sorted:
            k = (m, p)
            vals.append(_pct(mp_s[k]["s"], mp_s[k]["t"]) if mp_s[k]["t"] else "N/A")
        row = _write_row(ws, row, vals)
        for ci, p in enumerate(all_prompts_sorted):
            _heatmap_color(ws.cell(row=row - 1, column=2 + ci), ws.cell(row=row - 1, column=2 + ci).value)
    row = _insight(ws, row,
        "Green ≥60% | Yellow 21-59% | Red ≤20%. "
        "Cells show % of tests where ALL properties were satisfied.", NCOLS)
    row += 1

    # ── 6. Model × Algorithm heatmap ──
    row = _section(ws, row, "6. Model × Algorithm Success Rate (%)", NCOLS)
    row = _write_header(ws, row, ["Model"] + list(all_algos_sorted))
    for m in all_models_sorted:
        vals = [m]
        for a in all_algos_sorted:
            k = (m, a)
            vals.append(_pct(ma_s[k]["s"], ma_s[k]["t"]) if ma_s[k]["t"] else "N/A")
        row = _write_row(ws, row, vals)
        for ci in range(len(all_algos_sorted)):
            _heatmap_color(ws.cell(row=row - 1, column=2 + ci), ws.cell(row=row - 1, column=2 + ci).value)
    row = _insight(ws, row,
        "Green ≥60% | Yellow 21-59% | Red ≤20%. "
        "Identifies which model struggles with which algorithm.", NCOLS)
    row += 1

    # ── 7. Prompt × Algorithm heatmap ──
    row = _section(ws, row, "7. Prompt × Algorithm Success Rate (%)", NCOLS)
    row = _write_header(ws, row, ["Prompt"] + list(all_algos_sorted))
    for p in all_prompts_sorted:
        vals = [p.replace("_", " ").title()]
        for a in all_algos_sorted:
            k = (p, a)
            vals.append(_pct(pa_s[k]["s"], pa_s[k]["t"]) if pa_s[k]["t"] else "N/A")
        row = _write_row(ws, row, vals)
        for ci in range(len(all_algos_sorted)):
            _heatmap_color(ws.cell(row=row - 1, column=2 + ci), ws.cell(row=row - 1, column=2 + ci).value)
    row = _insight(ws, row,
        "Green ≥60% | Yellow 21-59% | Red ≤20%. "
        "Shows which prompt works best for each algorithm.", NCOLS)
    row += 1

    # ── 8. Model trends across versions ──
    row = _section(ws, row, "8. Model Performance by Version (Success Rate %)", NCOLS)
    row = _write_header(ws, row, ["Model"] + [f"V{v}" for v in versions_sorted] + ["Trend"])
    for m in all_models_sorted:
        vals = [m]
        plist = []
        for v in versions_sorted:
            k = (v, m)
            if vm_s[k]["t"]:
                p = _pct(vm_s[k]["s"], vm_s[k]["t"])
                vals.append(p); plist.append(p)
            else:
                vals.append("N/A"); plist.append(None)
        valid = [x for x in plist if x is not None]
        if len(valid) >= 2:
            diff = valid[-1] - valid[0]
            trend = "↑ Improving" if diff > 5 else ("↓ Declining" if diff < -5 else "→ Stable")
        else:
            trend = "—"
        vals.append(trend)
        row = _write_row(ws, row, vals)
        tc = ws.cell(row=row - 1, column=2 + len(versions_sorted))
        if "Improving" in trend:   tc.fill = LIGHT_GREEN; tc.font = BOLD
        elif "Declining" in trend: tc.fill = LIGHT_RED;   tc.font = BOLD
        else:                      tc.fill = LIGHT_YELLOW
    row = _insight(ws, row,
        "Compares each model's success rate between versions. "
        "Trend shows if the model is getting better or worse results.", NCOLS)
    row += 1

    # ── 9. Algorithm trends across versions ──
    row = _section(ws, row, "9. Algorithm Verification Success by Version (Success Rate %)", NCOLS)
    row = _write_header(ws, row, ["Algorithm"] + [f"V{v}" for v in versions_sorted] + ["Trend"])
    for a in all_algos_sorted:
        vals = [a]
        plist = []
        for v in versions_sorted:
            k = (v, a)
            if va_s[k]["t"]:
                p = _pct(va_s[k]["s"], va_s[k]["t"])
                vals.append(p); plist.append(p)
            else:
                vals.append("N/A"); plist.append(None)
        valid = [x for x in plist if x is not None]
        if len(valid) >= 2:
            diff = valid[-1] - valid[0]
            trend = "↑ Improving" if diff > 5 else ("↓ Declining" if diff < -5 else "→ Stable")
        elif len(valid) == 1:
            idx = next(i for i, x in enumerate(plist) if x is not None)
            trend = f"— (new in V{versions_sorted[idx]})"
        else:
            trend = "—"
        vals.append(trend)
        row = _write_row(ws, row, vals)
        tc = ws.cell(row=row - 1, column=2 + len(versions_sorted))
        if "Improving" in trend:   tc.fill = LIGHT_GREEN; tc.font = BOLD
        elif "Declining" in trend: tc.fill = LIGHT_RED;   tc.font = BOLD
        else:                      tc.fill = LIGHT_YELLOW
    row = _insight(ws, row,
        "Shows whether verification success improved or declined between versions "
        "for each algorithm.", NCOLS)
    row += 1

    # ── 10. Key findings ──
    row = _section(ws, row, "10. Key Findings & Recommendations", NCOLS)

    worst_mp = sorted(mp_s.items(), key=lambda x: _pct(x[1]["s"], x[1]["t"]))
    worst_pa = sorted(pa_s.items(), key=lambda x: _pct(x[1]["s"], x[1]["t"]))

    findings = [
        ("BEST",   f"BEST MODEL: {best_model} — highest overall success rate."),
        ("WORST",  f"WORST MODEL: {worst_model} — consistently fails to produce structured output."),
        ("BEST",   f"BEST PROMPT: {best_prompt} — most reliable at eliciting correct verification."),
        ("WORST",  f"WORST PROMPT: {worst_prompt} — needs significant redesign."),
        ("BEST",   f"EASIEST ALGORITHM: {easiest} — models verify this most successfully."),
        ("WORST",  f"HARDEST ALGORITHM: {hardest} — lowest verification success; needs prompt improvements."),
    ]
    for (m, p), s in worst_mp[:3]:
        r = _pct(s["s"], s["t"])
        findings.append(("CRITICAL", f"CRITICAL: {m} + {p.replace('_',' ').title()} = {r}% success."))
    for (p, a), s in worst_pa[:3]:
        r = _pct(s["s"], s["t"])
        findings.append(("WEAK", f"WEAK SPOT: {p.replace('_',' ').title()} on {a} = {r}%."))

    # GPT rate-limit note
    gpt_total = model_s.get("gpt-4o", {"t": 0})["t"]
    if gpt_total:
        gpt_errors = sum(
            1 for v in all_data for a in all_data[v] for p in all_data[v][a]
            if "gpt-4o" in all_data[v][a][p]
            and all_data[v][a][p]["gpt-4o"][2] == "error"
        )
        findings.append(("NOTE",
            f"NOTE: gpt-4o had {gpt_errors} error responses out of "
            f"{gpt_total} tests. Its true capability is likely higher."))

    style_map = {
        "BEST":     (Font(size=11, color="006100"), LIGHT_GREEN),
        "WORST":    (Font(size=11, color="9C0006"), LIGHT_RED),
        "CRITICAL": (Font(size=11, color="9C0006"), LIGHT_RED),
        "WEAK":     (Font(size=11, color="9C6500"), LIGHT_YELLOW),
        "NOTE":     (Font(size=11, color="003399"), LIGHT_BLUE),
        "REC":      (BOLD, None),
    }
    for tag, text in findings:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
        c = ws.cell(row=row, column=1, value=f"• {text}")
        c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        c.border = THIN
        font, fill = style_map.get(tag, (NORMAL, None))
        c.font = font
        if fill:
            c.fill = fill
        ws.row_dimensions[row].height = 30
        row += 1

    # Column widths
    ws.column_dimensions["A"].width = 35
    ws.column_dimensions["B"].width = 30
    for i in range(3, NCOLS + 1):
        ws.column_dimensions[get_column_letter(i)].width = 18


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Write the "Cumulative Success Rate" sheet
# ═══════════════════════════════════════════════════════════════════════════════

def write_cumulative_sheet(
    wb: openpyxl.Workbook,
    all_data: dict[str, dict],
    all_properties: dict[str, list[str]],
):
    """
    Writes a visually polished sheet showing cumulative success rate per model
    across versions, with color gradients, banded rows, and clear tables.
    """
    if "Cumulative Success" in wb.sheetnames:
        del wb["Cumulative Success"]
    ws = wb.create_sheet("Cumulative Success")

    versions_sorted = sorted(all_data.keys(), key=lambda x: int(x))

    # ── Collect per-model, per-version stats ──
    model_version_stats: dict[str, dict[str, dict]] = defaultdict(
        lambda: defaultdict(lambda: {"correct": 0, "total": 0})
    )
    for ver in versions_sorted:
        for algo in all_data[ver]:
            for prompt in all_data[ver][algo]:
                for model, (sat, tot, classification) in all_data[ver][algo][prompt].items():
                    if classification == "error":
                        continue
                    model_version_stats[model][ver]["total"] += 1
                    if classification == "correct":
                        model_version_stats[model][ver]["correct"] += 1

    all_models_sorted = sorted(model_version_stats.keys())

    # ── Build cumulative data ──
    cumulative: dict[str, dict[str, dict]] = {}
    for model in all_models_sorted:
        cumulative[model] = {}
        cum_correct = 0
        cum_total = 0
        for ver in versions_sorted:
            stats = model_version_stats[model].get(ver, {"correct": 0, "total": 0})
            ver_correct = stats["correct"]
            ver_total = stats["total"]
            cum_correct += ver_correct
            cum_total += ver_total
            cum_pct = round(100 * cum_correct / cum_total, 1) if cum_total > 0 else None
            ver_pct = round(100 * ver_correct / ver_total, 1) if ver_total > 0 else None
            cumulative[model][ver] = {
                "cum_correct": cum_correct,
                "cum_total": cum_total,
                "cum_pct": cum_pct,
                "ver_correct": ver_correct,
                "ver_total": ver_total,
                "ver_pct": ver_pct,
            }

    # ── Color helpers ──
    DARK_GREEN_FILL  = PatternFill(start_color="27AE60", end_color="27AE60", fill_type="solid")
    MED_GREEN_FILL   = PatternFill(start_color="82E0AA", end_color="82E0AA", fill_type="solid")
    YELLOW_FILL_CUM  = PatternFill(start_color="F9E79F", end_color="F9E79F", fill_type="solid")
    ORANGE_FILL_CUM  = PatternFill(start_color="F5B041", end_color="F5B041", fill_type="solid")
    RED_FILL_CUM     = PatternFill(start_color="E74C3C", end_color="E74C3C", fill_type="solid")
    NO_DATA_FILL     = PatternFill(start_color="D5D8DC", end_color="D5D8DC", fill_type="solid")
    BAND_FILL        = PatternFill(start_color="EBF5FB", end_color="EBF5FB", fill_type="solid")
    TITLE_FILL       = PatternFill(start_color="1B4F72", end_color="1B4F72", fill_type="solid")
    SUBTITLE_FILL    = PatternFill(start_color="2E86C1", end_color="2E86C1", fill_type="solid")
    MODEL_HEADER_FILL = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
    ELIM_RED_FILL    = PatternFill(start_color="FADBD8", end_color="FADBD8", fill_type="solid")
    ELIM_ORANGE_FILL = PatternFill(start_color="FDEBD0", end_color="FDEBD0", fill_type="solid")
    ACTIVE_GREEN_FILL = PatternFill(start_color="D5F5E3", end_color="D5F5E3", fill_type="solid")

    THICK_BORDER = Border(
        left=Side(style="medium"), right=Side(style="medium"),
        top=Side(style="medium"), bottom=Side(style="medium"),
    )

    def _gradient_fill(pct):
        """Return fill based on percentage with 5-level gradient."""
        if pct >= 80:
            return DARK_GREEN_FILL
        elif pct >= 60:
            return MED_GREEN_FILL
        elif pct >= 40:
            return YELLOW_FILL_CUM
        elif pct >= 20:
            return ORANGE_FILL_CUM
        else:
            return RED_FILL_CUM

    def _pct_font(pct):
        """White text for dark backgrounds, black for light."""
        if pct >= 80 or pct < 20:
            return Font(bold=True, size=10, color="FFFFFF")
        return Font(bold=True, size=10, color="000000")

    NCOLS = max(2 + len(versions_sorted), 7)
    row = 1

    # ═══ Title ═══
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
    c = ws.cell(row=row, column=1, value="📊 Cumulative Model Success Rate")
    c.font = Font(bold=True, size=18, color="FFFFFF")
    c.fill = TITLE_FILL
    c.alignment = CENTER
    ws.row_dimensions[row].height = 30
    row += 1

    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
    c = ws.cell(row=row, column=1,
                value="Success % up to each version — errors/timeouts excluded from calculation")
    c.font = Font(italic=True, size=11, color="FFFFFF")
    c.fill = SUBTITLE_FILL
    c.alignment = CENTER
    ws.row_dimensions[row].height = 22
    row += 2

    # ═══ LEGEND ═══
    ws.cell(row=row, column=1, value="Legend:").font = Font(bold=True, size=11)
    row += 1
    legend_items = [
        (DARK_GREEN_FILL, "≥ 80%", Font(bold=True, size=10, color="FFFFFF")),
        (MED_GREEN_FILL, "60–79%", Font(bold=True, size=10)),
        (YELLOW_FILL_CUM, "40–59%", Font(bold=True, size=10)),
        (ORANGE_FILL_CUM, "20–39%", Font(bold=True, size=10)),
        (RED_FILL_CUM, "< 20%", Font(bold=True, size=10, color="FFFFFF")),
        (NO_DATA_FILL, "No data (model not tested)", Font(italic=True, size=10)),
    ]
    for i, (fill, label, font) in enumerate(legend_items):
        col = 1 + (i * 2)
        c = ws.cell(row=row, column=col, value="  ")
        c.fill = fill
        c.border = THIN
        c = ws.cell(row=row, column=col + 1, value=label)
        c.font = font
    row += 2

    # ═══ SECTION 1: Cumulative Success Rate Table ═══
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
    c = ws.cell(row=row, column=1, value="CUMULATIVE SUCCESS RATE (%) — From V0 Up To Each Version")
    c.font = Font(bold=True, size=13, color="FFFFFF")
    c.fill = MODEL_HEADER_FILL
    c.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[row].height = 25
    for ci in range(1, NCOLS + 1):
        ws.cell(row=row, column=ci).fill = MODEL_HEADER_FILL
        ws.cell(row=row, column=ci).border = THICK_BORDER
    row += 1

    # Header row
    headers = ["Model"] + [f"V{v}" for v in versions_sorted]
    for i, h in enumerate(headers):
        c = ws.cell(row=row, column=1 + i, value=h)
        c.font = Font(bold=True, size=10, color="FFFFFF")
        c.fill = HEADER_FILL
        c.alignment = CENTER
        c.border = THICK_BORDER
    row += 1

    # Data rows with banding and gradient fills
    for mi, model in enumerate(all_models_sorted):
        is_band = mi % 2 == 1
        # Model name cell
        mc = ws.cell(row=row, column=1, value=model)
        mc.font = Font(bold=True, size=11)
        mc.alignment = Alignment(horizontal="left", vertical="center")
        mc.border = THICK_BORDER
        if is_band:
            mc.fill = BAND_FILL

        for ci, ver in enumerate(versions_sorted):
            cell = ws.cell(row=row, column=2 + ci)
            cell.alignment = CENTER
            cell.border = THIN
            pct = cumulative[model][ver]["cum_pct"]
            if pct is not None:
                cell.value = pct
                cell.number_format = '0.0"%"'
                cell.fill = _gradient_fill(pct)
                cell.font = _pct_font(pct)
            else:
                cell.value = "—"
                cell.fill = NO_DATA_FILL
                cell.font = Font(italic=True, size=10, color="666666")
        row += 1

    row += 2

    # ═══ SECTION 2: Per-Version Success Rate ═══
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
    c = ws.cell(row=row, column=1, value="PER-VERSION SUCCESS RATE (%) — Individual Version Only")
    c.font = Font(bold=True, size=13, color="FFFFFF")
    c.fill = MODEL_HEADER_FILL
    c.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[row].height = 25
    for ci in range(1, NCOLS + 1):
        ws.cell(row=row, column=ci).fill = MODEL_HEADER_FILL
        ws.cell(row=row, column=ci).border = THICK_BORDER
    row += 1

    # Header row
    for i, h in enumerate(headers):
        c = ws.cell(row=row, column=1 + i, value=h)
        c.font = Font(bold=True, size=10, color="FFFFFF")
        c.fill = HEADER_FILL
        c.alignment = CENTER
        c.border = THICK_BORDER
    row += 1

    # Data rows
    for mi, model in enumerate(all_models_sorted):
        is_band = mi % 2 == 1
        mc = ws.cell(row=row, column=1, value=model)
        mc.font = Font(bold=True, size=11)
        mc.alignment = Alignment(horizontal="left", vertical="center")
        mc.border = THICK_BORDER
        if is_band:
            mc.fill = BAND_FILL

        for ci, ver in enumerate(versions_sorted):
            cell = ws.cell(row=row, column=2 + ci)
            cell.alignment = CENTER
            cell.border = THIN
            pct = cumulative[model][ver]["ver_pct"]
            if pct is not None:
                cell.value = pct
                cell.number_format = '0.0"%"'
                cell.fill = _gradient_fill(pct)
                cell.font = _pct_font(pct)
            else:
                cell.value = "—"
                cell.fill = NO_DATA_FILL
                cell.font = Font(italic=True, size=10, color="666666")
        row += 1

    row += 2

    # ═══ SECTION 3: Model Elimination Justification ═══
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
    c = ws.cell(row=row, column=1, value="MODEL ELIMINATION JUSTIFICATION")
    c.font = Font(bold=True, size=13, color="FFFFFF")
    c.fill = MODEL_HEADER_FILL
    c.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[row].height = 25
    for ci in range(1, NCOLS + 1):
        ws.cell(row=row, column=ci).fill = MODEL_HEADER_FILL
        ws.cell(row=row, column=ci).border = THICK_BORDER
    row += 1

    # Header
    elim_headers = ["Model", "First Seen", "Last Seen", "Final Cumul. %", "Total Tests", "Status", "Recommendation"]
    for i, h in enumerate(elim_headers):
        c = ws.cell(row=row, column=1 + i, value=h)
        c.font = Font(bold=True, size=10, color="FFFFFF")
        c.fill = HEADER_FILL
        c.alignment = CENTER
        c.border = THICK_BORDER
    row += 1

    last_global_ver = versions_sorted[-1]

    for model in all_models_sorted:
        first_ver = None
        last_ver = None
        final_pct = None
        final_total = 0
        for ver in versions_sorted:
            stats = cumulative[model][ver]
            if stats["ver_total"] > 0:
                if first_ver is None:
                    first_ver = ver
                last_ver = ver
                if stats["cum_pct"] is not None:
                    final_pct = stats["cum_pct"]
                    final_total = stats["cum_total"]

        was_eliminated = (last_ver != last_global_ver) if last_ver else False

        if final_pct is not None:
            if was_eliminated:
                if final_pct < 30:
                    status = "❌ Eliminated"
                    rec = f"Very low performance ({final_pct}%) — removed after V{last_ver}"
                    row_fill = ELIM_RED_FILL
                elif final_pct < 60:
                    status = "❌ Eliminated"
                    rec = f"Underperforming ({final_pct}%) — removed after V{last_ver}"
                    row_fill = ELIM_RED_FILL
                else:
                    status = "⚠️ Eliminated"
                    rec = f"Good perf. ({final_pct}%) — removed for other reasons (cost/rate-limits)"
                    row_fill = ELIM_ORANGE_FILL
            elif final_pct < 20:
                status = "⚠️ At risk"
                rec = "Consider eliminating — very low success rate"
                row_fill = ELIM_ORANGE_FILL
            elif final_pct < 40:
                status = "⚠️ Underperf."
                rec = "Monitor closely — below acceptable threshold"
                row_fill = ELIM_ORANGE_FILL
            else:
                status = "✅ Active"
                rec = "Acceptable performance — kept in pipeline"
                row_fill = ACTIVE_GREEN_FILL
        else:
            status = "—"
            rec = "No data available"
            row_fill = NO_DATA_FILL

        values = [
            model,
            f"V{first_ver}" if first_ver else "—",
            f"V{last_ver}" if last_ver else "—",
            f"{final_pct}%" if final_pct is not None else "—",
            final_total,
            status,
            rec,
        ]
        for i, v in enumerate(values):
            c = ws.cell(row=row, column=1 + i, value=v)
            c.alignment = CENTER if i > 0 else LEFT_AL
            c.border = THIN
            c.fill = row_fill
            if i == 0:
                c.font = Font(bold=True, size=11)
            elif i == 5:  # Status column
                c.font = Font(bold=True, size=11)
            elif i == 6:  # Recommendation
                c.font = Font(size=10)
                c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
            else:
                c.font = Font(size=11)
        ws.row_dimensions[row].height = 22
        row += 1

    row += 2

    # ═══ Footer note ═══
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
    c = ws.cell(row=row, column=1,
                value="Note: Errors (timeouts, rate-limits) are excluded from success rate. "
                      "Models absent in a version show '—'. Cumulative % aggregates all tests from V0 to that version.")
    c.font = Font(italic=True, size=10, color="555555")
    c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)

    # ── Column widths ──
    ws.column_dimensions["A"].width = 24
    for i in range(2, 2 + len(versions_sorted)):
        ws.column_dimensions[get_column_letter(i)].width = 9
    # Wider columns for the justification table
    if len(versions_sorted) + 2 < 7:
        for i in range(2, 8):
            ws.column_dimensions[get_column_letter(i)].width = 14
    ws.column_dimensions[get_column_letter(6)].width = 16
    ws.column_dimensions[get_column_letter(7)].width = 55


# ═══════════════════════════════════════════════════════════════════════════════
# 7b. Write the "Property Analysis" sheet
# ═══════════════════════════════════════════════════════════════════════════════

def write_property_analysis_sheet(
    wb: openpyxl.Workbook,
    all_properties: dict[str, list[str]],
):
    """
    Writes a sheet with per-property accuracy analysis:
    - Global property ranking (which properties are easiest/hardest to verify)
    - Per-model property breakdown (best/worst property per model)
    - Per-algorithm property breakdown
    - Broken algorithm detection analysis (for -v, -i, -a variants)
    """
    if "Property Analysis" in wb.sheetnames:
        del wb["Property Analysis"]
    ws = wb.create_sheet("Property Analysis")

    # ── Scan all results directories to get per-property verdicts ──
    broken_algos = {
        "new-byzantine-rb-v", "new-byzantine-rb-i", "new-byzantine-rb-a",
        "new-byzantine-rb-p", "new-byzantine-rb-n", "new-byzantine-rb-o",
    }
    # Expected violations for broken pseudocode algorithms
    expected_violations = {
        "new-byzantine-rb-v": "RB-Validity",
        "new-byzantine-rb-i": "RB-Integrity",
        "new-byzantine-rb-a": "RB-Agreement",
    }

    # Collect per-property stats for correct algorithms
    # prop_model[prop][model] = {satisfied: N, non_satisfied: N}
    prop_model: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"satisfied": 0, "non_satisfied": 0})
    )
    # algo_prop[algo][prop] = {satisfied: N, non_satisfied: N}
    algo_prop: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"satisfied": 0, "non_satisfied": 0})
    )
    # prompt_prop[prompt][prop] = {satisfied: N, non_satisfied: N}
    prompt_prop: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"satisfied": 0, "non_satisfied": 0})
    )
    # prompt_prop_model[prompt][prop][model] = {satisfied: N, non_satisfied: N}
    prompt_prop_model: dict[str, dict[str, dict[str, dict[str, int]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: {"satisfied": 0, "non_satisfied": 0}))
    )
    # For broken algorithms: detection stats
    # broken_stats[model][algo] = {detected_correct_prop: N, detected_wrong_prop: N, missed: N}
    broken_stats: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"detected_correct": 0, "detected_wrong": 0, "missed": 0, "total": 0})
    )

    results_dirs = discover_results_dirs()
    for _, results_path in results_dirs:
        if not results_path.is_dir():
            continue
        for algo_dir in sorted(results_path.iterdir()):
            if not algo_dir.is_dir():
                continue
            algo = algo_dir.name
            if algo not in all_properties:
                continue
            expected = all_properties[algo]

            for prompt_dir in sorted(algo_dir.iterdir()):
                if not prompt_dir.is_dir():
                    continue
                prompt_name = prompt_dir.name
                for result_file in sorted(prompt_dir.glob("*.txt")):
                    model = result_file.stem
                    verdicts = parse_per_property_verdicts(result_file, expected)
                    if verdicts is None:
                        continue

                    if algo not in broken_algos:
                        # Correct algorithm — all should be satisfied
                        for prop, verdict in verdicts.items():
                            prop_model[prop][model][verdict] += 1
                            algo_prop[algo][prop][verdict] += 1
                            prompt_prop[prompt_name][prop][verdict] += 1
                            prompt_prop_model[prompt_name][prop][model][verdict] += 1
                    elif algo in expected_violations:
                        # Broken pseudocode algorithm
                        violated_prop = expected_violations[algo]
                        broken_stats[model][algo]["total"] += 1
                        has_any_non_sat = any(v == "non_satisfied" for v in verdicts.values())
                        if not has_any_non_sat:
                            broken_stats[model][algo]["missed"] += 1
                        else:
                            # Check if the correct property was detected
                            if verdicts.get(violated_prop) == "non_satisfied":
                                broken_stats[model][algo]["detected_correct"] += 1
                            else:
                                broken_stats[model][algo]["detected_wrong"] += 1

    # ── Style helpers ──
    TITLE_FILL = PatternFill(start_color="1B4F72", end_color="1B4F72", fill_type="solid")
    SUBTITLE_FILL = PatternFill(start_color="2E86C1", end_color="2E86C1", fill_type="solid")
    SECTION_HDR = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
    STRONG_GREEN = PatternFill(start_color="27AE60", end_color="27AE60", fill_type="solid")
    STRONG_RED = PatternFill(start_color="E74C3C", end_color="E74C3C", fill_type="solid")
    BAND = PatternFill(start_color="EBF5FB", end_color="EBF5FB", fill_type="solid")

    def gradient_fill(pct):
        if pct >= 95:
            return PatternFill(start_color="27AE60", end_color="27AE60", fill_type="solid")
        elif pct >= 85:
            return PatternFill(start_color="82E0AA", end_color="82E0AA", fill_type="solid")
        elif pct >= 70:
            return PatternFill(start_color="F9E79F", end_color="F9E79F", fill_type="solid")
        elif pct >= 50:
            return PatternFill(start_color="F5B041", end_color="F5B041", fill_type="solid")
        else:
            return PatternFill(start_color="E74C3C", end_color="E74C3C", fill_type="solid")

    def pct_font(pct):
        if pct >= 95 or pct < 50:
            return Font(bold=True, size=10, color="FFFFFF")
        return Font(bold=True, size=10, color="000000")

    NCOLS = 10
    row = 1

    # ═══ Title ═══
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
    c = ws.cell(row=row, column=1, value="📊 Per-Property Verification Analysis")
    c.font = Font(bold=True, size=18, color="FFFFFF")
    c.fill = TITLE_FILL
    c.alignment = CENTER
    ws.row_dimensions[row].height = 30
    row += 1

    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
    c = ws.cell(row=row, column=1,
                value="Accuracy per property on correct algorithms — identifies which properties models verify best/worst")
    c.font = Font(italic=True, size=11, color="FFFFFF")
    c.fill = SUBTITLE_FILL
    c.alignment = CENTER
    row += 2

    # ═══ SECTION 1: Global Property Ranking ═══
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
    c = ws.cell(row=row, column=1, value="1. GLOBAL PROPERTY RANKING (correct algorithms, all models)")
    c.font = Font(bold=True, size=13, color="FFFFFF")
    c.fill = SECTION_HDR
    for ci in range(1, NCOLS + 1):
        ws.cell(row=row, column=ci).fill = SECTION_HDR
    row += 1

    # Header
    headers = ["Rank", "Property", "Satisfied", "Non-Satisfied", "Total", "Accuracy %", "Assessment"]
    for i, h in enumerate(headers):
        c = ws.cell(row=row, column=1 + i, value=h)
        c.font = HEADER_FONT
        c.fill = HEADER_FILL
        c.alignment = CENTER
        c.border = THIN
    row += 1

    # Compute and sort
    prop_ranking = []
    for prop in sorted(prop_model):
        total_sat = sum(prop_model[prop][m]["satisfied"] for m in prop_model[prop])
        total_nonsat = sum(prop_model[prop][m]["non_satisfied"] for m in prop_model[prop])
        total = total_sat + total_nonsat
        if total >= 5:
            pct = round(100 * total_sat / total, 1)
            prop_ranking.append((prop, total_sat, total_nonsat, total, pct))
    prop_ranking.sort(key=lambda x: x[4], reverse=True)

    for rank, (prop, sat, nonsat, total, pct) in enumerate(prop_ranking, 1):
        if pct >= 95:
            assessment = "✅ Excellent"
        elif pct >= 85:
            assessment = "👍 Good"
        elif pct >= 70:
            assessment = "⚠️ Moderate"
        else:
            assessment = "❌ Weak"
        values = [rank, prop, sat, nonsat, total, pct, assessment]
        for i, v in enumerate(values):
            c = ws.cell(row=row, column=1 + i, value=v)
            c.alignment = CENTER if i != 1 and i != 6 else LEFT_AL
            c.border = THIN
            c.font = NORMAL
            if i == 5:
                c.fill = gradient_fill(pct)
                c.font = pct_font(pct)
        row += 1
    row += 2

    # ═══ SECTION 2: Per-Model Property Breakdown ═══
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
    c = ws.cell(row=row, column=1, value="2. PER-MODEL PROPERTY ACCURACY (correct algorithms)")
    c.font = Font(bold=True, size=13, color="FFFFFF")
    c.fill = SECTION_HDR
    for ci in range(1, NCOLS + 1):
        ws.cell(row=row, column=ci).fill = SECTION_HDR
    row += 1

    all_models_sorted = sorted(set(m for p in prop_model for m in prop_model[p]))
    all_props_sorted = sorted(prop_model.keys())

    # Header
    headers2 = ["Model"] + all_props_sorted
    for i, h in enumerate(headers2):
        c = ws.cell(row=row, column=1 + i, value=h)
        c.font = HEADER_FONT
        c.fill = HEADER_FILL
        c.alignment = CENTER
        c.border = THIN
    row += 1

    for mi, model in enumerate(all_models_sorted):
        mc = ws.cell(row=row, column=1, value=model)
        mc.font = Font(bold=True, size=10)
        mc.alignment = LEFT_AL
        mc.border = THIN
        if mi % 2 == 1:
            mc.fill = BAND

        for ci, prop in enumerate(all_props_sorted):
            cell = ws.cell(row=row, column=2 + ci)
            cell.alignment = CENTER
            cell.border = THIN
            s = prop_model[prop].get(model, {"satisfied": 0, "non_satisfied": 0})
            total = s["satisfied"] + s["non_satisfied"]
            if total > 0:
                pct = round(100 * s["satisfied"] / total, 1)
                cell.value = pct
                cell.fill = gradient_fill(pct)
                cell.font = pct_font(pct)
            else:
                cell.value = "—"
                cell.font = Font(italic=True, size=10, color="666666")
            if mi % 2 == 1 and total == 0:
                cell.fill = BAND
        row += 1
    row += 2

    # ═══ SECTION 3: Per-Algorithm Property Breakdown ═══
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
    c = ws.cell(row=row, column=1, value="3. PER-ALGORITHM PROPERTY ACCURACY (all models combined)")
    c.font = Font(bold=True, size=13, color="FFFFFF")
    c.fill = SECTION_HDR
    for ci in range(1, NCOLS + 1):
        ws.cell(row=row, column=ci).fill = SECTION_HDR
    row += 1

    for algo in sorted(algo_prop):
        # Algorithm sub-header
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
        ac = ws.cell(row=row, column=1, value=algo)
        ac.font = Font(bold=True, size=11)
        ac.fill = ALGO_FILL
        ac.alignment = LEFT_AL
        row += 1

        # Header for this algo
        for i, h in enumerate(["Property", "Satisfied", "Non-Satisfied", "Total", "Accuracy %"]):
            c = ws.cell(row=row, column=1 + i, value=h)
            c.font = Font(bold=True, size=10, color="FFFFFF")
            c.fill = HEADER_FILL
            c.alignment = CENTER
            c.border = THIN
        row += 1

        for prop in sorted(algo_prop[algo]):
            s = algo_prop[algo][prop]
            total = s["satisfied"] + s["non_satisfied"]
            if total == 0:
                continue
            pct = round(100 * s["satisfied"] / total, 1)
            values = [prop, s["satisfied"], s["non_satisfied"], total, pct]
            for i, v in enumerate(values):
                c = ws.cell(row=row, column=1 + i, value=v)
                c.alignment = CENTER if i > 0 else LEFT_AL
                c.border = THIN
                c.font = NORMAL
                if i == 4:
                    c.fill = gradient_fill(pct)
                    c.font = pct_font(pct)
            row += 1
        row += 1

    row += 1

    # ═══ SECTION 4: Broken Algorithm Detection ═══
    if any(broken_stats[m][a]["total"] > 0 for m in broken_stats for a in broken_stats[m]):
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
        c = ws.cell(row=row, column=1, value="4. PSEUDOCODE-ERROR DETECTION (broken algorithm variants -v, -i, -a)")
        c.font = Font(bold=True, size=13, color="FFFFFF")
        c.fill = SECTION_HDR
        for ci in range(1, NCOLS + 1):
            ws.cell(row=row, column=ci).fill = SECTION_HDR
        row += 1

        # Explanation
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
        ws.cell(row=row, column=1,
                value="Detected correct = model identified the right violated property | "
                      "Detected wrong = model said non-satisfied but wrong property | "
                      "Missed = model said all satisfied (failed to detect error)").font = Font(italic=True, size=9)
        row += 1

        headers4 = ["Model", "Algorithm", "Total Valid", "Detected (correct prop)", "Detected (wrong prop)", "Missed", "Detection %"]
        for i, h in enumerate(headers4):
            c = ws.cell(row=row, column=1 + i, value=h)
            c.font = HEADER_FONT
            c.fill = HEADER_FILL
            c.alignment = CENTER
            c.border = THIN
        row += 1

        for model in sorted(broken_stats):
            for algo in sorted(broken_stats[model]):
                s = broken_stats[model][algo]
                if s["total"] == 0:
                    continue
                detected_total = s["detected_correct"] + s["detected_wrong"]
                det_pct = round(100 * detected_total / s["total"], 1)
                correct_pct = round(100 * s["detected_correct"] / s["total"], 1) if s["total"] > 0 else 0
                values = [model, algo, s["total"], s["detected_correct"], s["detected_wrong"], s["missed"], det_pct]
                for i, v in enumerate(values):
                    c = ws.cell(row=row, column=1 + i, value=v)
                    c.alignment = CENTER if i > 0 else LEFT_AL
                    c.border = THIN
                    c.font = NORMAL
                    if i == 6:
                        c.fill = gradient_fill(det_pct)
                        c.font = pct_font(det_pct)
                row += 1

        row += 2

        # Summary: overall detection
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
        total_all = sum(broken_stats[m][a]["total"] for m in broken_stats for a in broken_stats[m])
        total_det_correct = sum(broken_stats[m][a]["detected_correct"] for m in broken_stats for a in broken_stats[m])
        total_det_wrong = sum(broken_stats[m][a]["detected_wrong"] for m in broken_stats for a in broken_stats[m])
        total_missed = sum(broken_stats[m][a]["missed"] for m in broken_stats for a in broken_stats[m])
        ws.cell(row=row, column=1,
                value=f"OVERALL: {total_all} tests | "
                      f"{total_det_correct} correctly detected ({round(100*total_det_correct/max(total_all,1),1)}%) | "
                      f"{total_det_wrong} wrong property flagged | "
                      f"{total_missed} completely missed ({round(100*total_missed/max(total_all,1),1)}%)").font = Font(bold=True, size=11)
        row += 1

    # ═══ SECTION 5: Prompt × Property Accuracy ═══
    all_prompts_sorted = sorted(prompt_prop.keys())
    all_props_in_prompts = sorted(set(p for pr in prompt_prop for p in prompt_prop[pr]))

    if all_prompts_sorted and all_props_in_prompts:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
        c = ws.cell(row=row, column=1, value="5. PROMPT × PROPERTY ACCURACY (correct algorithms, all models)")
        c.font = Font(bold=True, size=13, color="FFFFFF")
        c.fill = SECTION_HDR
        for ci in range(1, NCOLS + 1):
            ws.cell(row=row, column=ci).fill = SECTION_HDR
        row += 1

        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
        ws.cell(row=row, column=1,
                value="Shows which prompt template yields the highest accuracy for each property. "
                      "Use this to select the best prompt per verification target.").font = Font(italic=True, size=9)
        row += 1

        # Header
        headers5 = ["Prompt"] + all_props_in_prompts
        for i, h in enumerate(headers5):
            c = ws.cell(row=row, column=1 + i, value=h.replace("_", " ").title() if i == 0 else h)
            c.font = HEADER_FONT
            c.fill = HEADER_FILL
            c.alignment = CENTER
            c.border = THIN
        row += 1

        # Data rows — find best prompt per property for highlighting
        best_per_prop = {}
        for prop in all_props_in_prompts:
            best_pct = -1
            for prompt in all_prompts_sorted:
                s = prompt_prop[prompt][prop]
                total = s["satisfied"] + s["non_satisfied"]
                if total >= 3:
                    pct = 100 * s["satisfied"] / total
                    if pct > best_pct:
                        best_pct = pct
                        best_per_prop[prop] = prompt

        for pi, prompt in enumerate(all_prompts_sorted):
            mc = ws.cell(row=row, column=1, value=prompt.replace("_", " ").title())
            mc.font = Font(bold=True, size=10)
            mc.alignment = LEFT_AL
            mc.border = THIN
            if pi % 2 == 1:
                mc.fill = BAND

            for ci, prop in enumerate(all_props_in_prompts):
                cell = ws.cell(row=row, column=2 + ci)
                cell.alignment = CENTER
                cell.border = THIN
                s = prompt_prop[prompt][prop]
                total = s["satisfied"] + s["non_satisfied"]
                if total > 0:
                    pct = round(100 * s["satisfied"] / total, 1)
                    cell.value = pct
                    cell.fill = gradient_fill(pct)
                    cell.font = pct_font(pct)
                    # Mark best prompt per property with a thick border
                    if best_per_prop.get(prop) == prompt:
                        cell.border = Border(
                            left=Side(style="thick", color="006100"),
                            right=Side(style="thick", color="006100"),
                            top=Side(style="thick", color="006100"),
                            bottom=Side(style="thick", color="006100"),
                        )
                else:
                    cell.value = "—"
                    cell.font = Font(italic=True, size=10, color="666666")
            row += 1

        # Summary row: best prompt per property
        row += 1
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
        recommendations = []
        for prop in all_props_in_prompts:
            if prop in best_per_prop:
                s = prompt_prop[best_per_prop[prop]][prop]
                total = s["satisfied"] + s["non_satisfied"]
                pct = round(100 * s["satisfied"] / total, 1) if total > 0 else 0
                recommendations.append(f"{prop} → {best_per_prop[prop].replace('_', ' ')} ({pct}%)")
        ws.cell(row=row, column=1,
                value="Best prompt per property: " + " | ".join(recommendations)).font = Font(italic=True, size=10)
        row += 2

    # ═══ SECTION 6: Prompt × Property × Model detail ═══
    if all_prompts_sorted and all_props_in_prompts and all_models_sorted:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
        c = ws.cell(row=row, column=1, value="6. PROMPT × PROPERTY BREAKDOWN PER MODEL (correct algorithms)")
        c.font = Font(bold=True, size=13, color="FFFFFF")
        c.fill = SECTION_HDR
        for ci in range(1, NCOLS + 1):
            ws.cell(row=row, column=ci).fill = SECTION_HDR
        row += 1

        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
        ws.cell(row=row, column=1,
                value="For each model, shows accuracy per prompt×property combination. "
                      "Identifies which prompt works best for each model on each property.").font = Font(italic=True, size=9)
        row += 1

        for model in all_models_sorted:
            # Check if this model has enough data
            model_total = sum(
                prompt_prop_model[pr][p][model]["satisfied"] + prompt_prop_model[pr][p][model]["non_satisfied"]
                for pr in all_prompts_sorted for p in all_props_in_prompts
            )
            if model_total < 5:
                continue

            # Model sub-header
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=NCOLS)
            mc = ws.cell(row=row, column=1, value=model)
            mc.font = Font(bold=True, size=11)
            mc.fill = ALGO_FILL
            mc.alignment = LEFT_AL
            row += 1

            # Header for this model
            model_headers = ["Prompt"] + all_props_in_prompts
            for i, h in enumerate(model_headers):
                c = ws.cell(row=row, column=1 + i, value=h)
                c.font = Font(bold=True, size=9, color="FFFFFF")
                c.fill = HEADER_FILL
                c.alignment = CENTER
                c.border = THIN
            row += 1

            for prompt in all_prompts_sorted:
                pc = ws.cell(row=row, column=1, value=prompt.replace("_", " ").title())
                pc.font = Font(size=10)
                pc.alignment = LEFT_AL
                pc.border = THIN

                for ci, prop in enumerate(all_props_in_prompts):
                    cell = ws.cell(row=row, column=2 + ci)
                    cell.alignment = CENTER
                    cell.border = THIN
                    s = prompt_prop_model[prompt][prop][model]
                    total = s["satisfied"] + s["non_satisfied"]
                    if total > 0:
                        pct = round(100 * s["satisfied"] / total, 1)
                        cell.value = pct
                        cell.fill = gradient_fill(pct)
                        cell.font = pct_font(pct)
                    else:
                        cell.value = "—"
                        cell.font = Font(italic=True, size=9, color="666666")
                row += 1
            row += 1

    # ── Column widths ──
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 22
    for i in range(3, NCOLS + 1):
        ws.column_dimensions[get_column_letter(i)].width = 16


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("╔══════════════════════════════════════════════╗")
    print("║   update_excel.py — Rebuild versionControl   ║")
    print("╚══════════════════════════════════════════════╝\n")

    # Load expected properties
    all_properties = load_properties()
    print(f"Loaded properties for {len(all_properties)} algorithms:")
    for algo, props in sorted(all_properties.items()):
        print(f"  • {algo}: {', '.join(props)}")

    # Discover results directories
    results_dirs = discover_results_dirs()
    if not results_dirs:
        print("\n⚠ No results_* directories found. Nothing to do.")
        sys.exit(0)

    print(f"\nFound {len(results_dirs)} results folder(s):")
    for ver, path in results_dirs:
        print(f"  • Version {ver}: {path}")

    # Parse all results
    all_data: dict[str, dict] = {}
    for ver, path in results_dirs:
        print(f"\nScanning {path.name} …")
        version_data = scan_results_dir(path, all_properties)
        if version_data:
            all_data[ver] = version_data
            total_tests = sum(
                1 for a in version_data for p in version_data[a]
                for m in version_data[a][p]
            )
            total_correct = sum(
                1 for a in version_data for p in version_data[a]
                for m in version_data[a][p] if version_data[a][p][m][2] == "correct"
            )
            total_wrong = sum(
                1 for a in version_data for p in version_data[a]
                for m in version_data[a][p] if version_data[a][p][m][2] == "wrong"
            )
            total_fmt = sum(
                1 for a in version_data for p in version_data[a]
                for m in version_data[a][p] if version_data[a][p][m][2] == "incorrect_output"
            )
            total_err = sum(
                1 for a in version_data for p in version_data[a]
                for m in version_data[a][p] if version_data[a][p][m][2] == "error"
            )
            print(f"  → {total_tests} tests: {total_correct} correct, {total_wrong} wrong, "
                  f"{total_fmt} incorrect format, {total_err} errors")
        else:
            print(f"  → No results found")

    if not all_data:
        print("\n⚠ No parseable results. Nothing to write.")
        sys.exit(0)

    # Build workbook
    wb = openpyxl.Workbook()
    # Remove the default empty sheet
    wb.remove(wb.active)

    # Write version sheets
    for ver in sorted(all_data, key=lambda x: int(x)):
        print(f"\nWriting 'Version {ver}' sheet …")
        write_version_sheet(wb, ver, all_data[ver], all_properties)

    # Write comparison sheet (inserted as first)
    print("\nWriting 'Results Comparison' sheet …")
    write_comparison_sheet(wb, all_data, all_properties)

    # Write cumulative success sheet
    print("\nWriting 'Cumulative Success' sheet …")
    write_cumulative_sheet(wb, all_data, all_properties)

    # Write property analysis sheet
    print("\nWriting 'Property Analysis' sheet …")
    write_property_analysis_sheet(wb, all_properties)

    # Save (with fallback if file is locked by another application)
    try:
        wb.save(str(XLSX_PATH))
        print(f"\n✅ Saved {XLSX_PATH}")
    except PermissionError:
        fallback = XLSX_PATH.with_stem(XLSX_PATH.stem + "_new")
        print(f"\n⚠ Permission denied — file is likely open in another application.")
        print(f"  Saving to: {fallback}")
        wb.save(str(fallback))
        print(f"  ✅ Saved {fallback}")
        print(f"  → Close the original file and rename, or run again.")
    print(f"   Sheets: {wb.sheetnames}")


if __name__ == "__main__":
    main()