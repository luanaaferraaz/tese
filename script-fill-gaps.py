"""
script-fill-gaps.py — Run only the missing tests to reach 5 valid per (model, algo, prompt).

Excludes iaedu models (handled separately).
Only runs combinations that have fewer than 5 valid results across all existing results folders.
"""

from pathlib import Path
import re
import requests
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent
RESULTS_ROOT = BASE_DIR / "results_data"
RESULTS_ROOT.mkdir(exist_ok=True)

ALGORITHMS_DIR = BASE_DIR / "algorithms"
PROPERTIES_DIR = BASE_DIR / "properties"
PROMPTS_DIR = BASE_DIR / "prompts"

TARGET_MIN = 5  # minimum valid tests per (model, algo, prompt)

# Models to fill gaps for (no iaedu)
OLLAMA_MODELS = {
    "qwen2.5-coder-7b": "qwen2.5-coder:7b",
    # "deepseek-coder-6.7b": "deepseek-coder:6.7b",  # eliminated
    # "yi-coder-9b-chat": "yi-coder:9b-chat",  # eliminated
}

CODER_STYLE_MODELS = {
    "qwen2.5-coder-7b",
    "deepseek-coder-6.7b",
    "yi-coder-9b-chat",
}

# Algorithms to check (broken + metadata variants; correct algos already have enough)
ALGORITHMS_TO_CHECK = [
    "new-byzantine-rb-v",
    "new-byzantine-rb-i",
    "new-byzantine-rb-a",
    # Add more here if needed:
    # "new-byzantine-rb-n",
    # "new-byzantine-rb-o",
    # "new-byzantine-rb-p",
]

PROMPTS_TO_CHECK = ["chain_of_thought", "role_based", "strict_format", "zero_shot"]


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


def count_existing_valid(model_slug: str, algo_slug: str, prompt_slug: str) -> int:
    """Count how many valid results already exist for this combination across all results folders."""
    count = 0

    # Check all results_* folders
    for p in sorted(RESULTS_ROOT.iterdir()):
        if not p.is_dir():
            continue
        if not re.match(r"results(_\d+)?$", p.name):
            continue
        # Also check nested (results_72/results_72)
        nested = p / p.name
        check_paths = [p, nested] if nested.exists() else [p]

        for base in check_paths:
            result_file = base / algo_slug / prompt_slug / f"{model_slug}.txt"
            if result_file.exists():
                text = result_file.read_text(encoding="utf-8", errors="replace").strip()
                if text and not text.lower().startswith("error"):
                    count += 1

    # Check tese(1) 2
    tese1 = BASE_DIR / "tese(1) 2"
    if tese1.exists():
        for p in sorted(tese1.iterdir()):
            if not p.is_dir():
                continue
            result_file = p / algo_slug / prompt_slug / f"{model_slug}.txt"
            if result_file.exists():
                text = result_file.read_text(encoding="utf-8", errors="replace").strip()
                if text and not text.lower().startswith("error"):
                    count += 1

    return count


def get_next_results_dir() -> Path:
    i = 0
    while True:
        dir_name = "results" if i == 0 else f"results_{i}"
        path = RESULTS_ROOT / dir_name
        if not path.exists():
            path.mkdir()
            return path
        i += 1


def main():
    # Determine what needs to be run
    gaps = []  # list of (model_label, model_id, algo_name, prompt_name, needed)

    for algo_name in ALGORITHMS_TO_CHECK:
        algo_slug = slugify(algo_name)
        for prompt_name in PROMPTS_TO_CHECK:
            prompt_slug = slugify(prompt_name)
            for model_label in OLLAMA_MODELS:
                model_slug = slugify(model_label)
                existing = count_existing_valid(model_slug, algo_slug, prompt_slug)
                needed = TARGET_MIN - existing
                if needed > 0:
                    gaps.append((model_label, OLLAMA_MODELS[model_label], algo_name, prompt_name, needed))

    if not gaps:
        print("All combinations already have >= 5 valid tests. Nothing to do.")
        return

    # Summary
    total_runs = sum(n for _, _, _, _, n in gaps)
    print(f"Found {len(gaps)} gaps, need {total_runs} total runs:")
    for model_label, _, algo, prompt, needed in gaps:
        print(f"  {model_label} x {algo} x {prompt}: needs {needed} more")
    print()

    # Create results dir
    results_dir = get_next_results_dir()
    print(f"Saving to: {results_dir}")
    print()

    # Run
    for model_label, model_id, algo_name, prompt_name, needed in gaps:
        algo_file = ALGORITHMS_DIR / f"{algo_name}.txt"
        properties_file = PROPERTIES_DIR / f"{algo_name}.txt"
        prompt_file = PROMPTS_DIR / f"{prompt_name}.txt"

        algorithm_text = read_file(algo_file)
        properties_text = read_file(properties_file)
        prompt_template = read_file(prompt_file)

        task_prompt = build_task_prompt(prompt_template, algorithm_text, properties_text)
        final_prompt = wrap_prompt(model_label, task_prompt)

        result_subdir = results_dir / slugify(algo_name) / slugify(prompt_name)
        result_subdir.mkdir(parents=True, exist_ok=True)

        for run in range(needed):
            print(f"[{model_label}] {algo_name} / {prompt_name} (run {run+1}/{needed})...", end=" ")

            try:
                output = query_ollama(model_id, final_prompt)
            except Exception as e:
                output = f"ERROR:\n{e}"

            # Save with unique name to avoid overwriting
            if needed == 1:
                output_path = result_subdir / f"{slugify(model_label)}.txt"
            else:
                output_path = result_subdir / f"{slugify(model_label)}_run{run+1}.txt"

            output_path.write_text(output, encoding="utf-8")
            print("done")

    print(f"\nCompleted. Results in {results_dir}")


if __name__ == "__main__":
    main()
