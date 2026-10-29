import json, os, re, time, requests
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv
from game import SnakeGame, DIRECTIONS

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)


@dataclass
class AgentResult:
    direction: Optional[str]
    thought: str
    status: str
    latency_ms: float
    model_name: str
    masked_key: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cumulative_tokens: int = 0


class SnakeLLMAgent:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY", "")
        self.model_name = os.getenv("MODEL_NAME", "nvidia/nemotron-3.5-super-vl:free")
        self.url = "https://openrouter.ai/api/v1/chat/completions"
        self.cumulative_tokens = 0

    def get_masked_key(self):
        return f"{self.api_key[:8]}...{self.api_key[-4:]}" if len(self.api_key) > 12 else "No Key Set"

    def is_using_live_key(self):
        return bool(self.api_key and "your_openrouter_api_key" not in self.api_key)

    def _prompt(self, game: SnakeGame):
        hr, hc = game.snake[0]
        fr, fc = game.food
        return (
            f"Snake {game.size}x{game.size} Board:\n{game.get_board_text()}\n"
            f"H=({hr},{hc}), B={game.snake[1:]}, F=({fr},{fc}). Safe:{game.get_safe_moves()}.\n"
            f"Reply JSON: {{\"thought\": \"<under 10 words>\", \"direction\": \"UP|DOWN|LEFT|RIGHT\"}}"
        )

    def choose_move(self, game: SnakeGame):
        masked, t0 = self.get_masked_key(), time.perf_counter()
        if not self.is_using_live_key():
            return AgentResult(None, "Missing API key in .env", "ERROR", 0, self.model_name, masked, cumulative_tokens=self.cumulative_tokens)

        headers = {"Authorization": f"Bearer {self.api_key.strip()}", "Content-Type": "application/json"}
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": self._prompt(game)}],
            "temperature": 0.1,
            "max_tokens": 80,
            "reasoning": {"enabled": False},
        }
        print(f"[API CALL] Querying OpenRouter ({self.model_name})...", end=" ", flush=True)

        try:
            resp = requests.post(self.url, headers=headers, json=payload, timeout=12)
            ms = (time.perf_counter() - t0) * 1000.0
            if resp.status_code == 200:
                data = resp.json()
                u = data.get("usage", {})
                p_tok, c_tok = u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
                tot = u.get("total_tokens", p_tok + c_tok)
                self.cumulative_tokens += tot

                msg = data["choices"][0]["message"]
                txt = (msg.get("content") or "") + " " + (msg.get("reasoning") or "")
                d, thought = None, ""

                m = re.search(r"\{.*?\}", txt, re.DOTALL)
                if m:
                    try:
                        p = json.loads(m.group(0))
                        d, thought = p.get("direction", "").strip().upper(), p.get("thought", "")
                    except Exception:
                        pass

                if not d or d not in DIRECTIONS:
                    dm = re.search(r"\b(UP|DOWN|LEFT|RIGHT)\b", txt, re.IGNORECASE)
                    d = dm.group(1).upper() if dm else None

                if d in DIRECTIONS:
                    print(f"DONE in {ms:.0f}ms (Tok: {tot}) -> {d}")
                    return AgentResult(d, thought or f"Move {d}", "LIVE_API", ms, self.model_name, masked, p_tok, c_tok, tot, self.cumulative_tokens)

            err = resp.text[:100]
            print(f"FAILED (Status {resp.status_code}: {err})")
            return AgentResult(None, f"API Error ({resp.status_code}): {err}", "ERROR", ms, self.model_name, masked, cumulative_tokens=self.cumulative_tokens)
        except Exception as e:
            ms = (time.perf_counter() - t0) * 1000.0
            print(f"ERROR ({str(e)[:60]})")
            return AgentResult(None, f"Network Error: {str(e)[:60]}", "ERROR", ms, self.model_name, masked, cumulative_tokens=self.cumulative_tokens)
