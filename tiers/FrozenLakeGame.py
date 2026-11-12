import random
import re

import pygame

from core.llm import ask_llm
from core.logger import JsonlLogger
from core.viewer import open_window, pause, draw_grid_lines, draw_panel
from envs.frozenlake import FrozenLakeEnv


NUM_EPISODES = 3
MAX_STEPS = 20
PAUSE_SECONDS = 4     
END_PAUSE = 3          

BACKGROUND = (0, 0, 0)
GRID_LINE = (255, 255, 255)
ICE = (173, 216, 230)
START = (120, 200, 120)
HOLE = (40, 40, 40)
GOAL = (240, 200, 50)
PLAYER = (220, 60, 60)
TITLE_TEXT = (255, 210, 80)
INFO_TEXT = (230, 230, 230)
REPLY_TEXT = (150, 220, 150)
TILE_COLORS = {"S": START, "F": ICE, "H": HOLE, "G": GOAL}


BOARD_PX = 480
MARGIN = 10
PANEL_W = 400
PANEL_X = BOARD_PX + 2 * MARGIN
WINDOW_W = PANEL_X + PANEL_W
WINDOW_H = BOARD_PX + 2 * MARGIN

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


def draw(screen, env, info, reply):
    screen.fill(BACKGROUND)
    cell = BOARD_PX // env.size
    grid = env.env.unwrapped.desc

    for r in range(env.size):
        for c in range(env.size):
            tile = grid[r][c].decode()
            square = pygame.Rect(MARGIN + c * cell, MARGIN + r * cell, cell, cell)
            pygame.draw.rect(screen, TILE_COLORS[tile], square)

    row, col = env.position()
    player = pygame.Rect(MARGIN + col * cell + cell // 4, MARGIN + row * cell + cell // 4,
                         cell // 2, cell // 2)
    pygame.draw.rect(screen, PLAYER, player)

    draw_grid_lines(screen, env.size, cell, MARGIN, MARGIN, GRID_LINE)
    draw_panel(screen, PANEL_X, PANEL_W - MARGIN, "FrozenLake", info, reply,
               TITLE_TEXT, INFO_TEXT, REPLY_TEXT)
    pygame.display.flip()


def play_episode(screen, env, logger, episode, wins):
    env.reset()
    history = []
    for step in range(1, MAX_STEPS + 1):
        info = [f"Episode: {episode}/{NUM_EPISODES}",
                f"Step: {step}/{MAX_STEPS}",
                f"Wins so far: {wins}"]

        draw(screen, env, info + ["Status: asking the LLM..."], "Thinking...")

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

        info += [f"Action: {action}", f"Valid reply: {valid}"]
        if done:
            info.append("Result: WIN" if reward == 1 else "Result: LOSS (hole)")
        draw(screen, env, info, reply)

        if done:
            pause(END_PAUSE)
            return reward
        pause(PAUSE_SECONDS)
    return 0.0  


if __name__ == "__main__":
    screen = open_window("Tier 0 - FrozenLake", WINDOW_W, WINDOW_H)
    env = FrozenLakeEnv(slippery=False)
    logger = JsonlLogger("tier0")

    wins = 0
    for ep in range(1, NUM_EPISODES + 1):
        wins += play_episode(screen, env, logger, ep, int(wins))

    print(f"Wins: {int(wins)} / {NUM_EPISODES}")
    print(f"Log saved to: {logger.path}")
    pygame.quit()