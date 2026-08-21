#!/usr/bin/env python3
"""Extract GPT-5.5 (iaedu-model-1) justifications on CORRECT algorithms
where it marked properties as non-satisfied (the source of the 0% rows)."""
import sys, re
from pathlib import Path
from collections import defaultdict
sys.path.insert(0, str(Path.cwd()))
import update_excel as ue

UNZ = Path("diogo/_unzipped")
PROP_DIR = UNZ/"results_26"/"properties_v3"
PROPS = {}
for f in sorted(PROP_DIR.glob("*.txt")):
    raw = f.read_text().strip()
    PROPS[f.stem.lower()] = [n.strip() for n in raw.replace("\n", ",").split(",") if n.strip()]

run_dirs = []
for z in ["results_26","results_76","results_133","results_200"]:
    zp = UNZ/z
    if zp.is_dir():
        for c in sorted(zp.iterdir()):
            if c.is_dir() and c.name.startswith("results_") and c.name[8:].isdigit():
                run_dirs.append(c)

TARGET = ["best-effort-broadcast","echo-broadcast","bracha-byzantine-rb",
          "imbs-byzantine-rb","rb-crash-failure"]
MODEL = "iaedu-model-1"

# collect the raw "non satisfied" reason lines per (algo, property)
reasons = defaultdict(lambda: defaultdict(list))

def get_message(rf):
    raw = rf.read_text(encoding="utf-8", errors="replace")
    if ue._is_json_stream(raw):
        return ue._extract_gpt_message(raw)
    return raw

for run in run_dirs:
    for algo_dir in sorted(run.iterdir()):
        if not algo_dir.is_dir(): continue
        key = algo_dir.name.lower()
        if key not in TARGET: continue
        for prompt_dir in algo_dir.iterdir():
            if not prompt_dir.is_dir(): continue
            rf = prompt_dir/f"{MODEL}.txt"
            if not rf.exists(): continue
            msg = get_message(rf)
            if not msg: continue
            # capture lines like "Validity - [non satisfied]: reason"
            for line in msg.splitlines():
                m = re.search(r"([A-Za-z][\w \-]+?)\s*[-–:]\s*\[?\s*non[\s_]*satisfied\s*\]?\s*:?\s*(.*)",
                              line, re.IGNORECASE)
                if m:
                    prop = m.group(1).strip()
                    reason = m.group(2).strip()
                    if reason:
                        reasons[key][prop].append(reason)

for algo in TARGET:
    print("="*80)
    print(algo)
    print("="*80)
    for prop in sorted(reasons[algo]):
        rs = reasons[algo][prop]
        print(f"\n  [{prop}]  ({len(rs)} justificações)")
        # show a few distinct examples
        seen = []
        for r in rs:
            short = r[:160]
            if short not in seen:
                seen.append(short)
            if len(seen) >= 4:
                break
        for s in seen:
            print(f"     - {s}")
