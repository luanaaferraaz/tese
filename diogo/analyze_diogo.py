#!/usr/bin/env python3
"""Analyze the new Diogo test dataset (results_26/76/133/200 unzipped).

Reuses the verdict parser from update_excel.py. Aggregates:
  - per-model correct-algorithm accuracy vs broken-detection rate
  - per-algorithm results
  - per-property detection on broken variants
  - error / incorrect_output rates
"""
from __future__ import annotations
import sys
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent            # .../diogo
TESE = BASE.parent                                 # .../tese
sys.path.insert(0, str(TESE))
import update_excel as ue  # noqa: E402

UNZ = BASE / "_unzipped"
# properties bundled with the dataset
PROP_DIR = UNZ / "results_26" / "properties_v3"

def load_props() -> dict[str, list[str]]:
    props = {}
    for f in sorted(PROP_DIR.glob("*.txt")):
        raw = f.read_text(encoding="utf-8").strip()
        names = [n.strip() for n in raw.replace("\n", ",").split(",") if n.strip()]
        props[f.stem.lower()] = names   # lowercase key for case-insensitive match
    return props

PROPS = load_props()

def props_for(algo_dirname: str) -> list[str] | None:
    key = algo_dirname.lower()
    if key in PROPS:
        return PROPS[key]
    return None

def is_broken(algo_dirname: str) -> bool:
    return algo_dirname.lower().endswith("_b")

# discover every leaf run folder: results_N/<algo>/<prompt>/<model>.txt
run_dirs = []
for zipf in ["results_26", "results_76", "results_133", "results_200"]:
    z = UNZ / zipf
    if not z.is_dir():
        continue
    for child in sorted(z.iterdir()):
        # nested run folders named results_<n>
        if child.is_dir() and child.name.startswith("results_") and child.name[8:].isdigit():
            run_dirs.append(child)

print(f"Discovered {len(run_dirs)} run folders")

# aggregate
# per model: correct-algo (accuracy = classified correct), broken (detection = classified wrong)
model_correct = defaultdict(lambda: {"correct":0,"wrong":0,"fmt":0,"err":0,"n":0})
model_broken  = defaultdict(lambda: {"correct":0,"wrong":0,"fmt":0,"err":0,"n":0})
algo_stats    = defaultdict(lambda: defaultdict(lambda: {"correct":0,"wrong":0,"fmt":0,"err":0,"n":0}))
# per-property detection on broken variants: prop -> {model -> {detected, total}}
prop_detect   = defaultdict(lambda: defaultdict(lambda: {"nonsat":0,"total":0}))

def bump(d, cls):
    d["n"] += 1
    if cls == "correct": d["correct"] += 1
    elif cls == "wrong": d["wrong"] += 1
    elif cls == "incorrect_output": d["fmt"] += 1
    elif cls == "error": d["err"] += 1

for run in run_dirs:
    for algo_dir in sorted(run.iterdir()):
        if not algo_dir.is_dir():
            continue
        expected = props_for(algo_dir.name)
        if expected is None:
            continue
        broken = is_broken(algo_dir.name)
        for prompt_dir in sorted(algo_dir.iterdir()):
            if not prompt_dir.is_dir():
                continue
            for rf in sorted(prompt_dir.glob("*.txt")):
                model = rf.stem
                sat, tot, cls = ue.parse_result_file(rf, expected)
                (model_broken if broken else model_correct)[model_key := model]
                bump((model_broken if broken else model_correct)[model], cls)
                bump(algo_stats[algo_dir.name][model], cls)
                # per-property on broken
                if broken and cls in ("correct","wrong"):
                    verdicts = ue.parse_per_property_verdicts(rf, expected)
                    if verdicts:
                        for p in expected:
                            v = verdicts.get(p)
                            if v is not None:
                                prop_detect[p][model]["total"] += 1
                                if v == "non_satisfied":
                                    prop_detect[p][model]["nonsat"] += 1

def pct(a,b): return f"{100*a/b:5.1f}%" if b else "  n/a"

print("\n" + "="*78)
print("PER-MODEL SUMMARY")
print("="*78)
for model in sorted(set(list(model_correct)+list(model_broken))):
    c = model_correct[model]; b = model_broken[model]
    valid_c = c["correct"]+c["wrong"]+c["fmt"]
    valid_b = b["correct"]+b["wrong"]+b["fmt"]
    print(f"\n{model}")
    print(f"  CORRECT algos: n={c['n']:4d}  valid={valid_c:4d}  err={c['err']:3d}")
    print(f"     accuracy(correct-classified) = {pct(c['correct'],valid_c)}  "
          f"[correct={c['correct']} wrong={c['wrong']} fmt={c['fmt']}]")
    print(f"  BROKEN  algos: n={b['n']:4d}  valid={valid_b:4d}  err={b['err']:3d}")
    print(f"     detection(wrong-classified)  = {pct(b['wrong'],valid_b)}  "
          f"[wrong={b['wrong']} correct(missed)={b['correct']} fmt={b['fmt']}]")

print("\n" + "="*78)
print("PER-ALGORITHM (valid tests only; accuracy=correct for good algos, detection=wrong for _b)")
print("="*78)
for algo in sorted(algo_stats):
    broken = is_broken(algo)
    line = f"\n{algo}  ({'BROKEN' if broken else 'correct'})"
    print(line)
    for model in sorted(algo_stats[algo]):
        s = algo_stats[algo][model]
        valid = s["correct"]+s["wrong"]+s["fmt"]
        metric = s["wrong"] if broken else s["correct"]
        label = "detect" if broken else "accur "
        print(f"    {model:16s} n={s['n']:3d} valid={valid:3d} err={s['err']:2d} "
              f"{label}={pct(metric,valid)} "
              f"[c={s['correct']} w={s['wrong']} fmt={s['fmt']}]")

print("\n" + "="*78)
print("PER-PROPERTY DETECTION ON BROKEN VARIANTS (nonsat / total, higher=better)")
print("="*78)
for p in sorted(prop_detect):
    print(f"\n{p}")
    for model in sorted(prop_detect[p]):
        d = prop_detect[p][model]
        print(f"    {model:16s} {d['nonsat']:3d}/{d['total']:3d} = {pct(d['nonsat'],d['total'])}")
