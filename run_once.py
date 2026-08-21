#!/usr/bin/env python3
"""
run_once.py — Single one-shot run of GPT-5.5, LLaMA-70B and Qwen-7B.

Runs every (algorithm x model) combination EXACTLY ONCE, using the same single
combined prompt for all three models. No retries, no gap-filling loop, no
minimum-target counting. When it finishes, it is done.

Results are written to results_data/results_N/<algorithm>/combined/<model>.txt
so that update_excel.py picks them up like any other run.

Prerequisites on the machine that runs this:
  - GPT-5.5 (iaedu): internet access and a VALID iaedu agent id (see IAEDU below).
  - LLaMA-70B (Groq): environment variable GROQ_API_KEY set, and `aisuite` installed.
  - Qwen-7B (Ollama): a local Ollama server running with the model pulled:
        ollama pull qwen2.5-coder:7b
        ollama serve   (usually already running)

Usage:
    python3 run_once.py
"""

from pathlib import Path
import os
import re
import json
import uuid
import requests

try:
    import aisuite as ai
except Exception:
    ai = None

# ── API KEYS (kept here so everything travels with the project) ─────────────
# Groq key for LLaMA-70B. Paste your key between the quotes (starts with "gsk_").
# It is injected into the environment below so aisuite picks it up automatically.
GROQ_API_KEY = ""   # <-- PASTE YOUR GROQ KEY HERE (e.g. "gsk_...")

if GROQ_API_KEY:
    os.environ["GROQ_API_KEY"] = GROQ_API_KEY

# The iaedu keys for GPT-5.5 are already embedded further below (IAEDU_GPT).

BASE_DIR = Path(__file__).resolve().parent
RESULTS_ROOT = BASE_DIR / "results_data"
RESULTS_ROOT.mkdir(exist_ok=True)

ALGORITHMS_DIR = BASE_DIR / "algorithms_v3"
PROPERTIES_DIR = BASE_DIR / "properties_v3"
PROMPT_FILE = BASE_DIR / "prompts" / "combined.txt"
PROMPT_LABEL = "combined"          # subfolder name used for every result

REQUEST_TIMEOUT = 600

# ── Model configuration ────────────────────────────────────────────────────
# GPT-5.5 via the iaedu platform.
#   IMPORTANT: if the agent id ever returns "Agent not found", replace the id in
#   the endpoint below with the current one from the iaedu dashboard.
IAEDU_GPT = {
    "label": "iaedu-model-1",
    "endpoint": "https://api.iaedu.pt/agent-chat//api/v1/agent/cmor5objoex9gfp01vm7p95jh/stream",
    "api_key": "sk-usr-yugi4mt3t2k73xmukt5d1pd2lcwfuwpnfm",
    "channel_id": "cmqv8knmx5nmcp701nxpwjcpg",
}

GROQ_LLAMA = {
    "label": "llama-3.3-70b-groq",
    "model": "groq:llama-3.3-70b-versatile",
}

OLLAMA_QWEN = {
    "label": "qwen2.5-coder-7b",
    "model": "qwen2.5-coder:7b",
}


# ── Helpers ────────────────────────────────────────────────────────────────
def slugify(text: str) -> str:
    return re.sub(r"[^\w\-\.]+", "_", text.strip().lower())


def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def build_prompt(template: str, algorithm_text: str, properties_text: str) -> str:
    return template.replace("{algorithm}", algorithm_text).replace("{properties}", properties_text)


def get_next_results_dir() -> Path:
    i = 0
    while True:
        name = "results" if i == 0 else f"results_{i}"
        path = RESULTS_ROOT / name
        if not path.exists():
            path.mkdir()
            return path
        i += 1


# ── Model callers (single call, no retry) ──────────────────────────────────
def query_gpt_iaedu(prompt: str) -> str:
    """Return the raw streamed response (start/token/message/done lines)."""
    headers = {"x-api-key": IAEDU_GPT["api_key"]}
    data = {
        "channel_id": IAEDU_GPT["channel_id"],
        "thread_id": str(uuid.uuid4()),   # fresh thread each call, no context carry-over
        "user_info": json.dumps({}),
        "message": prompt,
    }
    r = requests.post(IAEDU_GPT["endpoint"], headers=headers, data=data,
                      stream=True, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    lines = [ln.decode("utf-8") for ln in r.iter_lines() if ln]
    return "\n".join(lines)


def query_llama_groq(client, prompt: str) -> str:
    resp = client.chat.completions.create(
        model=GROQ_LLAMA["model"],
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )
    return resp.choices[0].message.content


def query_qwen_ollama(prompt: str) -> str:
    # coder-style wrapper works best for the coder model
    wrapped = f"### Instruction:\n{prompt}\n\n### Response:"
    r = requests.post(
        "http://localhost:11434/api/chat",
        json={"model": OLLAMA_QWEN["model"],
              "messages": [{"role": "user", "content": wrapped}],
              "stream": False},
        timeout=REQUEST_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["message"]["content"]


# ── Main ────────────────────────────────────────────────────────────────────
def main() -> None:
    template = read_file(PROMPT_FILE)
    results_dir = get_next_results_dir()
    print(f"Saving to: {results_dir}")

    client = ai.Client() if ai is not None else None

    algo_files = sorted(ALGORITHMS_DIR.glob("*.txt"))
    total = len(algo_files) * 3
    done = 0

    for algo_file in algo_files:
        algo_name = algo_file.stem
        prop_file = PROPERTIES_DIR / f"{algo_name}.txt"
        if not prop_file.exists():
            print(f"  ! no properties for {algo_name}, skipping")
            continue
        prompt = build_prompt(template, read_file(algo_file), read_file(prop_file))

        out_base = results_dir / slugify(algo_name) / PROMPT_LABEL
        out_base.mkdir(parents=True, exist_ok=True)

        # one call per model, no retry — failures are saved as ERROR text
        jobs = [
            (IAEDU_GPT["label"],  lambda p=prompt: query_gpt_iaedu(p)),
            (GROQ_LLAMA["label"], lambda p=prompt: query_llama_groq(client, p)),
            (OLLAMA_QWEN["label"], lambda p=prompt: query_qwen_ollama(p)),
        ]
        for label, call in jobs:
            done += 1
            out_path = out_base / f"{label}.txt"
            try:
                output = call()
            except Exception as e:
                output = f"ERROR:\n{type(e).__name__}: {e}"
            out_path.write_text(output, encoding="utf-8")
            status = "ERROR" if output.startswith("ERROR:") else "ok"
            print(f"  [{done}/{total}] {algo_name} / {label}: {status}")

    print(f"\nDone. Results in {results_dir}")
    print("Next: run  python3 update_excel.py  to refresh versionControl.xlsx")


if __name__ == "__main__":
    main()
