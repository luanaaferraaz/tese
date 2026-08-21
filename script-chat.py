from pathlib import Path
import re
import json
import time
import uuid
import requests
from typing import Optional, Dict


BASE_DIR = Path(__file__).resolve().parent
RESULTS_ROOT = BASE_DIR / "results_data"
RESULTS_ROOT.mkdir(exist_ok=True)

ALGORITHMS_DIR = BASE_DIR / "algorithms_v3"
PROPERTIES_DIR = BASE_DIR / "properties_v3"
PROMPTS_DIR = BASE_DIR / "prompts"

REQUEST_TIMEOUT = 600
DELAY_BETWEEN_REQUESTS = 10


def get_next_results_dir(base_name="results") -> Path:
    i = 0
    while True:
        dir_name = base_name if i == 0 else f"{base_name}_{i}"
        path = RESULTS_ROOT / dir_name
        if not path.exists():
            path.mkdir()
            return path
        i += 1


RESULTS_DIR = get_next_results_dir()
print(f"Results directory: {RESULTS_DIR}")


TARGET_MIN = 5  # minimum valid tests per (model, algo, prompt)

# No force-retest or skip needed - fresh start with new algorithm set
FORCE_RETEST_ALGOS = []
SKIP_ALGOS = []


IAEDU_MODELS = {
    "iaedu-model-1": {
        "endpoint": "https://api.iaedu.pt/agent-chat//api/v1/agent/cmor5objoex9gfp01vm7p95jh/stream",
        "api_key": "sk-usr-yugi4mt3t2k73xmukt5d1pd2lcwfuwpnfm",
        "channel_id": "cmqv8knmx5nmcp701nxpwjcpg",
        "thread_id": str(uuid.uuid4()),
    },
    "iaedu-model-2": {
        "endpoint": "https://api.iaedu.pt/agent-chat//api/v1/agent/cmoss7l0f658oko01vk2egfpg/stream",
        "api_key": "sk-usr-lie3qeqhz9ruojqwsajjjjv9kfqql45kln9",
        "channel_id": "cmqv9ynwy5paop7013uxjodsg",
        "thread_id": str(uuid.uuid4()),
    },
}

# "eTK4KwAwrt5AaHh6D_rCD"
# "fWlM50dq2Sg9W5MV3f4JQ"

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


def save_output(result_dir: Path, label: str, output: str) -> None:
    output_path = result_dir / f"{slugify(label)}.txt"
    output_path.write_text(output, encoding="utf-8")


def query_iaedu(
    prompt: str,
    endpoint: str,
    api_key: str,
    channel_id: str,
    thread_id: str,
    user_info: Optional[Dict] = None,
    user_id: Optional[str] = None,
    user_context: Optional[Dict] = None,
    stream: bool = False,
) -> str:
    headers = {
        "x-api-key": api_key,
    }

    data = {
        "channel_id": channel_id,
        "thread_id": thread_id,
        "user_info": json.dumps(user_info or {}),
        "message": prompt,
    }

    if user_id:
        data["user_id"] = user_id

    if user_context:
        data["user_context"] = json.dumps(user_context)

    response = requests.post(
        endpoint,
        headers=headers,
        data=data,
        stream=stream,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    if stream:
        output = []
        for line in response.iter_lines():
            if line:
                output.append(line.decode("utf-8"))
        return "\n".join(output)

    return response.text


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
            result_file = base / algo_slug / prompt_slug / f"{model_slug}.txt"
            if result_file.exists():
                text = result_file.read_text(encoding="utf-8", errors="replace").strip()
                if text and not text.lower().startswith("error"):
                    is_error = False
                    for line in text.splitlines()[:5]:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                            if obj.get("type") in ("context_limit", "error"):
                                is_error = True
                                break
                        except (json.JSONDecodeError, ValueError):
                            break
                    if not is_error:
                        count += 1
    tese1 = BASE_DIR / "tese(1) 2"
    if tese1.exists():
        for p in sorted(tese1.iterdir()):
            if not p.is_dir():
                continue
            result_file = p / algo_slug / prompt_slug / f"{model_slug}.txt"
            if result_file.exists():
                text = result_file.read_text(encoding="utf-8", errors="replace").strip()
                if text and not text.lower().startswith("error"):
                    is_error = False
                    for line in text.splitlines()[:5]:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                            if obj.get("type") in ("context_limit", "error"):
                                is_error = True
                                break
                        except (json.JSONDecodeError, ValueError):
                            break
                    if not is_error:
                        count += 1
    return count


def main():
    algorithm_files = sorted(ALGORITHMS_DIR.glob("*.txt"))
    prompt_files = sorted(PROMPTS_DIR.glob("*.txt"))

    if not algorithm_files:
        raise RuntimeError(f"No algorithm files found in {ALGORITHMS_DIR}")

    if not prompt_files:
        raise RuntimeError(f"No prompt files found in {PROMPTS_DIR}")

    # Determine what needs to be run
    gaps = []
    for algorithm_file in algorithm_files:
        algorithm_name = algorithm_file.stem
        if algorithm_name in SKIP_ALGOS:
            continue
        algo_slug = slugify(algorithm_name)
        for prompt_file in prompt_files:
            prompt_name = prompt_file.stem
            prompt_slug = slugify(prompt_name)
            for label in IAEDU_MODELS:
                model_slug = slugify(label)
                existing = count_existing_valid(model_slug, algo_slug, prompt_slug)
                needed = TARGET_MIN - existing
                if needed > 0:
                    gaps.append((algorithm_file, prompt_file, label, needed, existing))

    if not gaps:
        print("All combinations already have >= 5 valid tests. Nothing to do.")
        return

    total_runs = sum(n for _, _, _, n, _ in gaps)
    print(f"Found {len(gaps)} gaps, need {total_runs} total runs:")
    for algo_f, prompt_f, label, needed, has in gaps:
        print(f"  {label} x {algo_f.stem} x {prompt_f.stem}: needs {needed} (has {has})")
    print()
    print("Starting IAEDU evaluation (gaps only)...")

    for algorithm_file, prompt_file, label, needed, _ in gaps:
        algorithm_name = algorithm_file.stem
        properties_file = PROPERTIES_DIR / f"{algorithm_name}.txt"

        algorithm_text = read_file(algorithm_file)
        properties_text = read_file(properties_file)
        prompt_name = prompt_file.stem
        prompt_template = read_file(prompt_file)

        task_prompt = build_task_prompt(
            prompt_template=prompt_template,
            algorithm_text=algorithm_text,
            properties_text=properties_text,
        )

        result_dir = RESULTS_DIR / slugify(algorithm_name) / slugify(prompt_name)
        result_dir.mkdir(parents=True, exist_ok=True)

        config = IAEDU_MODELS[label]
        print(f"\n[{label}] {algorithm_name} / {prompt_name} ({needed} runs)...")

        try:
            output = query_iaedu(
                prompt=task_prompt,
                endpoint=config["endpoint"],
                api_key=config["api_key"],
                channel_id=config["channel_id"],
                thread_id=str(uuid.uuid4()),
            )
        except Exception as e:
            output = f"ERROR:\n{type(e).__name__}: {e}"

        save_output(result_dir, label, output)
        time.sleep(DELAY_BETWEEN_REQUESTS)


if __name__ == "__main__":
    main()