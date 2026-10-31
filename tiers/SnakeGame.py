import random
import re
import time

from core.llm import ask_llm
from core.logger import JsonlLogger
from envs.snake import SnakeEnv

NUM_EPISODES = 2
MAX_STEPS = 40         
PAUSE_SECONDS = 4      
USE_HINTS = True      
MOVES = ["UP", "DOWN", "LEFT", "RIGHT"]

RULES = """You are playing Snake on an 8x8 grid.
Legend: H = your head, o = your body, F = food, . = empty cell.
Row 0 is the top, column 0 is the left.
Moves: UP (row-1), DOWN (row+1), LEFT (col-1), RIGHT (col+1).
Eating food scores a point and makes the snake longer.
You die if you hit a wall or your own body.
Goal: eat as much food as possible without dying."""


def build_prompt(env, history):
    head_r, head_c = env.head
    food_r, food_c = env.food
    recent = "\n".join(history[-5:]) if history else "None yet"

    hints = ""
    if USE_HINTS:
        lines = [f"  {m}: {env.look(m)}" for m in MOVES]
        hints = "\nWhat is next to your head:\n" + "\n".join(lines) + "\n"

    return f"""{RULES}

        Current grid:
        {env.state_to_text()}

        Your head is at row {head_r}, column {head_c}.
        The food is at row {food_r}, column {food_c}.
        Score: {env.score}
        {hints}
        Your recent moves:
        {recent}

        Think briefly, then finish with exactly one line in this format:
        ACTION: UP   (or DOWN, LEFT, RIGHT)"""


def parse_action(text):
    matches = re.findall(r"ACTION:\s*(UP|DOWN|LEFT|RIGHT)", text, re.IGNORECASE)
    return matches[-1].upper() if matches else None


def play_episode(env, logger, episode):
    env.reset()
    history = []
    invalid_count = 0

    for step in range(1, MAX_STEPS + 1):
        prompt = build_prompt(env, history)
        reply = ask_llm(prompt)
        action = parse_action(reply)

        valid = action is not None
        if not valid:
            invalid_count += 1
            action = random.choice(MOVES)  # fallback

        before = env.head
        outcome = env.look(action)         # what we are about to run into
        reward, done = env.step(action)

        history.append(f"{before} -> {action} ({outcome})")
        logger.log(episode=episode, step=step, prompt=prompt, reply=reply,
                   action=action, valid=valid, outcome=outcome,
                   reward=reward, score=env.score, done=done)
        print(f"Episode {episode} | step {step} | {action} | {outcome} | score {env.score}")

        if done:
            break
        time.sleep(PAUSE_SECONDS)

    return env.score, invalid_count


if __name__ == "__main__":
    env = SnakeEnv(size=8, seed=42)  # fixed seed = same food positions each run
    logger = JsonlLogger("tier1_snake")

    scores = []
    total_invalid = 0
    for ep in range(1, NUM_EPISODES + 1):
        score, invalid = play_episode(env, logger, ep)
        scores.append(score)
        total_invalid += invalid
        print(f"Episode {ep} finished. Score: {score}\n")

    print(f"Scores: {scores}")
    print(f"Average score: {sum(scores) / len(scores):.1f}")
    print(f"Invalid replies: {total_invalid}")
    print(f"Log saved to: {logger.path}")
