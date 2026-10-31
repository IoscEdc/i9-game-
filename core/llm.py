import os
import time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL"),
)
MODEL = os.getenv("LLM_MODEL")


def ask_llm(prompt):
    for attempt in range(1, 4):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            print(f"  LLM error (try {attempt}/3): {e}")
            time.sleep(10 * attempt)  # wait longer each time
    return ""

