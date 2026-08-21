"""
script-2.py — Fill gaps for local/API models (Qwen, LLaMA, DeepSeek-Chat).
Runs only the (model, algo, prompt) combinations that have fewer than TARGET valid results.
Loops until all gaps are filled.
"""

from pathlib import Path
import re
import json
import requests
import aisuite as ai
from collections import defaultdict
import time

BASE_DIR = Path(__file__).resolve().parent
RESULTS_ROOT = BASE_DIR / "results_data"
RESULTS_ROOT.mkdir(exist_ok=True)

ALGORITHMS_DIR = BASE_DIR / "algorithms_v3"
PROPERTIES_DIR = BASE_DIR / "properties_v3"
PROMPTS_DIR = BASE_DIR / "prompts"

TARGET = 5  # minimum valid tests per (model, algo, prompt)

# No exclusions needed - algorithms_v3 only contains the algorithms we want to test
EXCLUDE_ALGOS = set()

OLLAMA_MODELS = {
    "qwen2.5-coder-7b": "qwen2.5-coder:7b",
}

GROQ_MODELS = {
    "llama-3.3-70b-groq": "groq:llama-3.3-70b-versatile",
    "deepseek-chat": "deepseek:deepseek-chat",
}

CODER_STYLE_MODELS = {
    "qwen2.5-coder-7b",
}


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
    return response.json()["message"]["content"]


def query_aisuite(client, model: str, prompt: str) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )
    return response.choices[0].message.content


def count_existing_valid(model_slug: str, algo_slug: str, prompt_slug: str) -> int:
    """Count valid results across all existing results folders."""
    count = 0
    for p in sorted(RESULTS_ROOT.iterdir()):
        if not p.is_dir():
            continue
        if not re.match(r"results(_\d+)?(_miguel)?$", p.name):
            continue
        for base in [p, p / p.name]:
            if not base.is_dir():
                continue
            # Check exact name and _runN variants
            for f in base.glob(f"{algo_slug}/{prompt_slug}/{model_slug}*.txt"):
                text = f.read_text(encoding="utf-8", errors="replace").strip()
                if text and not text.lower().startswith("error") and "timed out" not in text.lower()[:100]:
                    count += 1
    # tese(1) 2
    tese1 = BASE_DIR / "tese(1) 2"
    if tese1.exists():
        for p in sorted(tese1.iterdir()):
            if not p.is_dir():
                continue
            for f in p.glob(f"{algo_slug}/{prompt_slug}/{model_slug}*.txt"):
                text = f.read_text(encoding="utf-8", errors="replace").strip()
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


def find_gaps():
    """Find all (model, algo, prompt) combinations below TARGET."""
    gaps = []
    algorithm_files = sorted(ALGORITHMS_DIR.glob("*.txt"))
    prompt_files = sorted(PROMPTS_DIR.glob("*.txt"))

    all_models = {}
    all_models.update(OLLAMA_MODELS)
    all_models.update(GROQ_MODELS)

    for algorithm_file in algorithm_files:
        algo_name = algorithm_file.stem
        if algo_name in EXCLUDE_ALGOS:
            continue
        algo_slug = slugify(algo_name)
        for prompt_file in prompt_files:
            prompt_name = prompt_file.stem
            prompt_slug = slugify(prompt_name)
            for model_label in all_models:
                model_slug = slugify(model_label)
                existing = count_existing_valid(model_slug, algo_slug, prompt_slug)
                needed = TARGET - existing
                if needed > 0:
                    gaps.append((model_label, algorithm_file, prompt_file, needed, existing))
    return gaps


def main():
    client = ai.Client()
    client.configure({
        "groq": {"timeout": 600},
        "deepseek": {"timeout": 600},
    })

    iteration = 0
    while True:
        iteration += 1
        gaps = find_gaps()

        if not gaps:
            print("All combinations have >= 5 valid tests. Done!")
            break

        total_needed = sum(n for _, _, _, n, _ in gaps)
        print(f"\n{'='*60}")
        print(f"Iteration {iteration}: {len(gaps)} gaps, {total_needed} tests needed")
        print(f"{'='*60}")

        # Show summary
        model_summary = defaultdict(int)
        for model, _, _, needed, _ in gaps:
            model_summary[model] += needed
        for model, total in sorted(model_summary.items()):
            print(f"  {model}: {total} tests needed")
        print()

        # Create results dir for this iteration
        results_dir = get_next_results_dir()
        print(f"Saving to: {results_dir}")

        # Run one test per gap
        for model_label, algorithm_file, prompt_file, needed, existing in gaps:
            algo_name = algorithm_file.stem
            prompt_name = prompt_file.stem
            properties_file = PROPERTIES_DIR / f"{algo_name}.txt"

            algorithm_text = read_file(algorithm_file)
            properties_text = read_file(properties_file)
            prompt_template = read_file(prompt_file)

            task_prompt = build_task_prompt(prompt_template, algorithm_text, properties_text)
            final_prompt = wrap_prompt(model_label, task_prompt)

            result_dir = results_dir / slugify(algo_name) / slugify(prompt_name)
            result_dir.mkdir(parents=True, exist_ok=True)

            print(f"  [{model_label}] {algo_name} / {prompt_name} (has {existing}, needs {needed})...", end=" ")

            try:
                if model_label in OLLAMA_MODELS:
                    output = query_ollama(OLLAMA_MODELS[model_label], final_prompt)
                else:
                    output = query_aisuite(client, GROQ_MODELS[model_label], final_prompt)
            except Exception as e:
                output = f"ERROR:\n{e}"

            output_path = result_dir / f"{slugify(model_label)}.txt"
            output_path.write_text(output, encoding="utf-8")
            print("done")

            time.sleep(2)  # small delay between API calls

        print(f"\nIteration {iteration} complete. Rechecking gaps...")


if __name__ == "__main__":
    main()
