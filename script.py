from pathlib import Path
import aisuite as ai
import requests
import re

BASE_DIR = Path(__file__).resolve().parent
RESULTS_ROOT = BASE_DIR / "results_data"
RESULTS_ROOT.mkdir(exist_ok=True)
ALGORITHMS_DIR = BASE_DIR / "algorithms"
RESULTS_DIR = RESULTS_ROOT / "results"
PROMPT_FILE = BASE_DIR / "prompt.txt"

# =========================
# MODELS
# =========================

AISUITE_MODELS = {
    # "gpt-4.1": "openai:gpt-4.1",
    # "claude-3.5-sonnet": "anthropic:claude-3-5-sonnet-latest",
    # "gemini-1.5-pro": "google:gemini-1.5-pro",
    # "deepseek-r1": "deepseek:deepseek-reasoner"
}

OLLAMA_MODELS = {
    "phi": "phi:2.7b",
    "qwen2.5-coder-7b": "qwen2.5-coder:7b",
    "deepseek-coder-6.7b": "deepseek-coder:6.7b",
    "yi-coder-9b-chat": "yi-coder:9b-chat",
}

# =========================
# HELPERS
# =========================

def slugify(text: str) -> str:
    return re.sub(r"[^\w\-\.]+", "_", text.strip().lower())

def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()

def build_prompt(template: str, algorithm: str) -> str:
    return template.replace("{algorithm}", algorithm)

# =========================
# QUERY FUNCTIONS
# =========================

def query_ollama(model: str, prompt: str) -> str:
    url = "http://localhost:11434/api/chat"

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    }

    r = requests.post(url, json=payload, timeout=600)
    r.raise_for_status()

    return r.json()["message"]["content"]

def query_aisuite(client, model: str, prompt: str) -> str:
    res = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return res.choices[0].message.content

# =========================
# MAIN
# =========================

def main():
    template = read_file(PROMPT_FILE)
    RESULTS_DIR.mkdir(exist_ok=True)

    client = ai.Client()
    client.configure({
        "ollama": {"timeout": 600},
        "openai": {"timeout": 600},
        "anthropic": {"timeout": 600},
        "google": {"timeout": 600},
    })

    for algo_file in ALGORITHMS_DIR.glob("*.txt"):
        algo_name = algo_file.stem
        algo_text = read_file(algo_file)

        final_prompt = build_prompt(template, algo_text)

        algo_dir = RESULTS_DIR / slugify(algo_name)
        algo_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n=== {algo_name} ===")

        # 🔹 Ollama
        for label, model in OLLAMA_MODELS.items():
            print(f"[OLLAMA] {label}")

            try:
                output = query_ollama(model, final_prompt)
            except Exception as e:
                output = f"ERROR:\n{e}"

            (algo_dir / f"{slugify(label)}.txt").write_text(output, encoding="utf-8")

        # 🔹 AISUITE
        for label, model in AISUITE_MODELS.items():
            print(f"[AISUITE] {label}")

            try:
                output = query_aisuite(client, model, final_prompt)
            except Exception as e:
                output = f"ERROR:\n{e}"

            (algo_dir / f"{slugify(label)}.txt").write_text(output, encoding="utf-8")

if __name__ == "__main__":
    main()