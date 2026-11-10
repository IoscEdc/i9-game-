import random
import re
import sys
import threading
import time

import numpy as np
import pygame

from core.llm import ask_llm
from core.logger import JsonlLogger
from core.viewer import open_window, pause, draw_panel
from envs.breakout import BreakoutEnv

NUM_GAMES = 2
MAX_STEPS = 30000       
FPS = 30                
DRAW_EVERY = 1          
LLM_EVERY = 2          
USE_LLM = True          
SHOW = True             
BRAKE = 1.0             
GOAL_SMOOTH = 0.2      
START_ZONE = 5          
STOP_ZONE = 3           
FAR_EXTRA = 8           
AIM_SIDE = {"LEFT": 0.25, "CENTER": 0, "RIGHT": -0.25}   
AIM_HOLD = 400          
STALL_STEPS = 600       
BREAKER_EVERY = 90   
SCREENS = 2   
END_PAUSE = 3

BACKGROUND = (40, 44, 52)
BALL_MARK = (80, 220, 255)
PADDLE_MARK = (255, 255, 255)
TARGET_MARK = (255, 210, 80)
TITLE_TEXT = (255, 210, 80)
INFO_TEXT = (230, 230, 230)
REPLY_TEXT = (150, 220, 150)

SCALE = 3
BOARD_W, BOARD_H = 160 * SCALE, 210 * SCALE
MARGIN = 10
PANEL_W = 400
PANEL_X = BOARD_W + 2 * MARGIN
WINDOW_W = PANEL_X + PANEL_W
WINDOW_H = BOARD_H + 2 * MARGIN

RULES = """You are the strategist for a Breakout bot.
A fast reflex layer already catches the ball. You only choose WHERE on the paddle the ball lands,
which decides the direction it flies after the bounce:
  AIM: LEFT   -> the ball is sent to the left
  AIM: CENTER -> the ball goes mostly straight up (safest)
  AIM: RIGHT  -> the ball is sent to the right
Bricks are at the top. The game ends when all bricks are gone.
Sideways aims are riskier, so use CENTER unless the score has stopped growing or one side clearly has more bricks."""

brain = {"aim": "CENTER", "override": None, "reply": "No LLM answer yet.", "busy": False,
         "latency": 0.0, "notes": [], "stalled": 0, "goal": None, "last": "NOOP"}


def build_prompt(env):
    notes = "\n".join(brain["notes"][-4:]) or "None yet"
    return f"""{RULES}

        Current situation:
        {env.state_to_text()}
        Your current aim: {brain['aim']}
        Steps since the score last changed: {brain['stalled']} (60 steps = 1 second)

        What happened after your earlier choices:
        {notes}

        Think briefly, then finish with exactly one line in this format:
        AIM: LEFT   (or CENTER, RIGHT)"""


def parse_aim(text):
    matches = re.findall(r"AIM:\s*(LEFT|CENTER|RIGHT)", text, re.IGNORECASE)
    return matches[-1].upper() if matches else None


def ask_in_background(prompt, logger, game, step):
    """Runs in its own thread, so the game keeps moving while we wait."""
    start = time.time()
    reply = ask_llm(prompt)
    aim = parse_aim(reply)
    if aim:
        brain["aim"] = aim
    brain["reply"] = reply or "(empty reply)"
    brain["latency"] = time.time() - start
    logger.log(game=game, step=step, prompt=prompt, reply=reply, aim=aim,
               valid=aim is not None, latency=brain["latency"])
    print(f"  LLM answered in {brain['latency']:.1f}s -> aim {aim}")
    brain["busy"] = False


def reflex(env):
    """Fast layer: move the paddle smoothly to where the ball WILL land (shifted by the aim)."""
    if env.target is None or env.paddle_x is None:
        brain["goal"], brain["last"] = None, "NOOP"
        return "NOOP"
    aim = brain["override"] or brain["aim"]          
    raw = env.target + AIM_SIDE[aim] * env.paddle_w

    goal = brain["goal"]
    if goal is None or abs(raw - goal) > 25:         
        goal = raw
    else:
        goal += GOAL_SMOOTH * (raw - goal)
    brain["goal"] = goal

    error = goal - (env.paddle_x + BRAKE * env.paddle_v)   
    far = (env.ball and env.ball[1] < 130) or (env.vel and env.vel[1] < 0)
    limit = STOP_ZONE if brain["last"] != "NOOP" else START_ZONE
    limit += FAR_EXTRA if far else 0

    action = "RIGHT" if error > limit else "LEFT" if error < -limit else "NOOP"
    brain["last"] = action
    return action


def draw(screen, env, info):
    screen.fill(BACKGROUND)
    picture = pygame.surfarray.make_surface(np.ascontiguousarray(env.frame.swapaxes(0, 1)))
    screen.blit(pygame.transform.scale(picture, (BOARD_W, BOARD_H)), (MARGIN, MARGIN))

    paddle_y = MARGIN + 191 * SCALE
    if env.ball:   
        center = (MARGIN + int(env.ball[0] * SCALE), MARGIN + int(env.ball[1] * SCALE))
        pygame.draw.circle(screen, BALL_MARK, center, 10, 2)
    if env.target is not None:   
        goal_x = MARGIN + int((brain["goal"] if brain["goal"] is not None else env.target) * SCALE)
        pygame.draw.line(screen, TARGET_MARK, (goal_x, paddle_y - 25), (goal_x, paddle_y + 25), 3)
    if env.paddle_x is not None:   
        box = pygame.Rect(0, 0, env.paddle_w * SCALE, 8 * SCALE)
        box.center = (MARGIN + int(env.paddle_x * SCALE), paddle_y)
        pygame.draw.rect(screen, PADDLE_MARK, box, 2)

    draw_panel(screen, PANEL_X, PANEL_W - MARGIN, "Breakout", info, brain["reply"],
               TITLE_TEXT, INFO_TEXT, REPLY_TEXT)
    pygame.display.flip()


def play_game(screen, env, logger, game):
    env.reset()
    brain.update(aim="CENTER", override=None, reply="No LLM answer yet.", busy=False,
                 notes=[], stalled=0, goal=None, last="NOOP")
    clock = pygame.time.Clock()
    last_call = 0
    need_fire = True       
    lives = env.lives
    missing = 0            
    action = "FIRE"
    info = []
    aim_start = None       
    last_score, last_gain = env.score, 0
    result = "GAME OVER" 

    for step in range(1, MAX_STEPS + 1):
        if SHOW:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

        if env.score != last_score:
            last_score, last_gain = env.score, step
        brain["stalled"] = step - last_gain
        if brain["stalled"] > STALL_STEPS:
            if step % BREAKER_EVERY == 0 or brain["override"] is None:
                brain["override"] = random.choice(["LEFT", "RIGHT"])
        else:
            brain["override"] = None

        if aim_start is None or aim_start[0] != brain["aim"]:
            aim_start = (brain["aim"], env.score, step, env.lives)
        if brain["aim"] != "CENTER" and step - aim_start[2] > AIM_HOLD:
            brain["aim"] = "CENTER"

        if USE_LLM and not brain["busy"] and time.time() - last_call > LLM_EVERY:
            if step > 1:         # tell the LLM how its last choice worked out
                aim, score0, _, lives0 = aim_start
                brain["notes"].append(f"Aim {aim}: score went from {score0} to {env.score}, "
                                      f"lives from {lives0} to {env.lives}.")
            brain["busy"] = True
            last_call = time.time()
            args = (build_prompt(env), logger, game, step)
            threading.Thread(target=ask_in_background, args=args, daemon=True).start()

        if need_fire:
            action, need_fire = "FIRE", False
        else:
            action = reflex(env)
        env.step(action)

        if step == 1:
            print(f"Perception check: paddle_x={env.paddle_x}, walls=({env.left}, {env.right})")
        if env.lives < lives:                 
            lives, need_fire, env.target = env.lives, True, None
        missing = 0 if env.ball and env.unseen == 0 else missing + 1
        if missing > 120:                     
            need_fire, missing = True, 0

        if SHOW and step % DRAW_EVERY == 0:
            info = [f"Game: {game}/{NUM_GAMES}",
                    f"Step: {step}/{MAX_STEPS}",
                    f"Score: {env.score}   Lives: {env.lives}   Screen: {min(env.cleared + 1, SCREENS)}/{SCREENS}",
                    f"Aim: {brain['aim']}" + (f"  (loop breaker: {brain['override']})" if brain["override"] else ""),
                    f"Reflex action: {action}",
                    f"LLM: {'thinking...' if brain['busy'] else 'idle'}",
                    f"Last LLM latency: {brain['latency']:.1f}s"]
            draw(screen, env, info)
            clock.tick(FPS // DRAW_EVERY)     

        if env.cleared >= SCREENS:            
            result = "ALL BRICKS CLEARED"
            break
        if env.done:
            break

    if result == "GAME OVER" and not env.done:
        result = "STEP LIMIT REACHED"
    print(f"Game {game}: {result}")
    if SHOW:
        draw(screen, env, info + [f"Result: {result}"])
        pause(END_PAUSE)
    return env.score


if __name__ == "__main__":
    screen = open_window("Tier 3 - Breakout", WINDOW_W, WINDOW_H) if SHOW else None
    env = BreakoutEnv(frameskip=1)    
    logger = JsonlLogger("tier3_breakout")

    scores = []
    for g in range(1, NUM_GAMES + 1):
        score = play_game(screen, env, logger, g)
        scores.append(score)
        print(f"Game {g} finished. Score: {score}\n")

    print(f"Scores: {scores}")
    print(f"Average score: {sum(scores) / len(scores):.1f}")
    print(f"Log saved to: {logger.path}")
    pygame.quit()
