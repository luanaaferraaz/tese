import os
from openai import OpenAI
import aisuite as ai

# =========================
# CONFIG
# =========================

API_BASE_URL = "https://api.iaedu.pt/agent-chat//api/v1/agent/cmamvd3n4000"  # <-- MUDA SÓ ISTO

# opcional (se não precisares, apaga esta linha)
CHANNEL_ID = os.environ.get("OPENAI_CHANNEL_ID")

# =========================
# CLIENTES
# =========================

# cliente para endpoint custom
OPENAI_CLIENT = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=API_BASE_URL,
    default_headers={
        **({"X-Channel-Id": CHANNEL_ID} if CHANNEL_ID else {})
    }
)

# cliente normal (aisuite)
AISUITE_CLIENT = ai.Client()

# =========================
# MODELOS
# =========================

MODELS = [
    "custom_openai:gpt-4o",

    "ollama:llama3.3",
    "ollama:yi-coder:9b-chat",
    "ollama:deepseek-coder:6.7b",
    "ollama:qwen2.5-coder:7b",
    "ollama:phi:2.7b",
    "ollama:opencode-6.7b",
]

# =========================
# QUERY
# =========================
def query_custom_agent(messages):
    prompt = messages[-1]["content"]

    response = requests.post(
        API_URL,
        json={"message": prompt},
        headers={
            "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
            "Content-Type": "application/json",
        },
    )

    try:
        return response.json()
    except:
        return response.text

def query_model(model_name: str, messages: list[dict]) -> str:
    try:
        # --- endpoint custom OpenAI ---
        if model_name.startswith("custom_openai:"):
            real_model = model_name.split(":", 1)[1]

            response = OPENAI_CLIENT.chat.completions.create(
                model=real_model,
                messages=messages,
                temperature=0.0,
                max_tokens=1200,
            )
            return response.choices[0].message.content

        # --- outros modelos (aisuite) ---
        response = AISUITE_CLIENT.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.0,
            max_tokens=1200,
        )
        return response.choices[0].message.content

    except Exception as e:
        return f"ERROR: {e}"
    

messages = [{"role": "user", "content": "Say hello"}]

print(query_custom_agent("custom_openai:gpt-4o"))