import random
import re

import pygame

from core.llm import ask_llm
from core.logger import JsonlLogger
from core.viewer import open_window, pause, draw_grid_lines, draw_panel
from envs.snake import SnakeEnv

NUM_EPISODES = 2
MAX_STEPS = 40
PAUSE_SECONDS = 4      
END_PAUSE = 3          
USE_HINTS = True       
MOVES = ["UP", "DOWN", "LEFT", "RIGHT"]

BACKGROUND = (40, 44, 52)
GRID_LINE = (60, 66, 78)
EMPTY = (30, 34, 42)
FOOD = (230, 70, 70)
BODY = (80, 180, 100)
HEAD = (50, 140, 70)
EYE = (255, 255, 255)
PUPIL = (0, 0, 0)
TITLE_TEXT = (255, 210, 80)
INFO_TEXT = (230, 230, 230)
REPLY_TEXT = (150, 220, 150)

BOARD_PX = 480
MARGIN = 10
PANEL_W = 400
PANEL_X = BOARD_PX + 2 * MARGIN
WINDOW_W = PANEL_X + PANEL_W
WINDOW_H = BOARD_PX + 2 * MARGIN

EYES = {
    "UP": [(0.3, 0.3), (0.7, 0.3)],
    "DOWN": [(0.3, 0.7), (0.7, 0.7)],
    "LEFT": [(0.3, 0.3), (0.3, 0.7)],
    "RIGHT": [(0.7, 0.3), (0.7, 0.7)],
}

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


def draw(screen, env, info, reply, facing):
    screen.fill(BACKGROUND)
    cell = BOARD_PX // env.size

    def square(pos):
        return pygame.Rect(MARGIN + pos[1] * cell, MARGIN + pos[0] * cell, cell, cell)

    pygame.draw.rect(screen, EMPTY, (MARGIN, MARGIN, BOARD_PX, BOARD_PX))
    if env.food:
        pygame.draw.rect(screen, FOOD, square(env.food))
    for part in env.snake[1:]:
        pygame.draw.rect(screen, BODY, square(part))
    pygame.draw.rect(screen, HEAD, square(env.head))

    draw_grid_lines(screen, env.size, cell, MARGIN, MARGIN, GRID_LINE)

    head_square = square(env.head)
    for fx, fy in EYES[facing]:
        center = (head_square.x + int(fx * cell), head_square.y + int(fy * cell))
        pygame.draw.circle(screen, EYE, center, cell // 7)
        pygame.draw.circle(screen, PUPIL, center, cell // 14)

    draw_panel(screen, PANEL_X, PANEL_W - MARGIN, "Snake", info, reply,
               TITLE_TEXT, INFO_TEXT, REPLY_TEXT)
    pygame.display.flip()


def play_episode(screen, env, logger, episode):
    env.reset()
    history = []
    invalid_count = 0
    facing = "RIGHT"  

    for step in range(1, MAX_STEPS + 1):
        info = [f"Episode: {episode}/{NUM_EPISODES}",
                f"Step: {step}/{MAX_STEPS}",
                f"Score: {env.score}"]

        draw(screen, env, info + ["Status: asking the LLM..."], "Thinking...", facing)

        prompt = build_prompt(env, history)
        reply = ask_llm(prompt)
        action = parse_action(reply)

        valid = action is not None
        if not valid:
            invalid_count += 1
            action = random.choice(MOVES)  

        before = env.head
        outcome = env.look(action)         
        reward, done = env.step(action)
        facing = action

        history.append(f"{before} -> {action} ({outcome})")
        logger.log(episode=episode, step=step, prompt=prompt, reply=reply,
                   action=action, valid=valid, outcome=outcome,
                   reward=reward, score=env.score, done=done)
        print(f"Episode {episode} | step {step} | {action} | {outcome} | score {env.score}")

        info = [f"Episode: {episode}/{NUM_EPISODES}",
                f"Step: {step}/{MAX_STEPS}",
                f"Score: {env.score}",
                f"Action: {action} ({outcome})",
                f"Valid reply: {valid}"]
        if done:
            info.append("Result: GAME OVER")
        draw(screen, env, info, reply, facing)

        if done:
            pause(END_PAUSE)
            break
        pause(PAUSE_SECONDS)

    return env.score, invalid_count


if __name__ == "__main__":
    screen = open_window("Tier 1 - Snake", WINDOW_W, WINDOW_H)
    env = SnakeEnv(size=8, seed=42)  
    logger = JsonlLogger("tier1_snake")

    scores = []
    total_invalid = 0
    for ep in range(1, NUM_EPISODES + 1):
        score, invalid = play_episode(screen, env, logger, ep)
        scores.append(score)
        total_invalid += invalid
        print(f"Episode {ep} finished. Score: {score}\n")

    print(f"Scores: {scores}")
    print(f"Average score: {sum(scores) / len(scores):.1f}")
    print(f"Invalid replies: {total_invalid}")
    print(f"Log saved to: {logger.path}")
    pygame.quit()
