import random
import re
import time

from core.llm import ask_llm
from core.logger import JsonlLogger
from envs.frozenlake import FrozenLakeEnv

NUM_EPISODES = 3
MAX_STEPS = 20
PAUSE_SECONDS = 4  # keeps us under free-tier rate limits

RULES = """You are playing FrozenLake on a 4x4 grid.
Legend: P = you, S = start, F = frozen (safe), H = hole (you lose), G = goal (you win).
Row 0 is the top, column 0 is the left.
Moves: LEFT (col-1), RIGHT (col+1), UP (row-1), DOWN (row+1).
Moving into a wall leaves you where you are.
Reach G without stepping on H."""


def build_prompt(env, history):
    row, col = env.position()
    recent = "\n".join(history[-5:]) if history else "None yet"
    return f"""{RULES}

Current grid:
{env.state_to_text()}

You are at row {row}, column {col}.
Your recent moves:
{recent}

Think briefly, then finish with exactly one line in this format:
ACTION: LEFT   (or RIGHT, UP, DOWN)"""


def parse_action(text):
    matches = re.findall(r"ACTION:\s*(LEFT|RIGHT|UP|DOWN)", text, re.IGNORECASE)
    return matches[-1].upper() if matches else None


def play_episode(env, logger, episode):
    env.reset()
    history = []
    for step in range(1, MAX_STEPS + 1):
        prompt = build_prompt(env, history)
        reply = ask_llm(prompt)
        action = parse_action(reply)

        valid = action is not None
        if not valid:
            action = random.choice(["LEFT", "RIGHT", "UP", "DOWN"])  # fallback

        before = env.position()
        reward, done = env.step(action)
        after = env.position()

        history.append(f"{before} -> {action} -> {after}")
        logger.log(episode=episode, step=step, prompt=prompt, reply=reply,
                   action=action, valid=valid, reward=reward, done=done)
        print(f"Episode {episode} | step {step} | {action} | {before} -> {after}")

        if done:
            return reward  # 1.0 = reached goal, 0.0 = fell in a hole
        time.sleep(PAUSE_SECONDS)
    return 0.0  # ran out of steps


if __name__ == "__main__":
    env = FrozenLakeEnv(slippery=False)  # start easy: no random slipping
    logger = JsonlLogger("tier0")

    wins = 0
    for ep in range(1, NUM_EPISODES + 1):
        result = play_episode(env, logger, ep)
        wins += result
        print(f"Episode {ep} finished. {'WIN' if result == 1 else 'LOSS'}\n")

    print(f"Wins: {int(wins)} / {NUM_EPISODES}")
    print(f"Log saved to: {logger.path}")
