import re
import sys
import threading
import time
from collections import deque

import pygame

from core.llm import ask_llm
from core.logger import JsonlLogger
from core.viewer import open_window, pause, draw_grid_lines, draw_panel
from envs.arena import ArenaEnv, DIRS

NUM_GAMES = 5
MAX_STEPS = 1500        
FPS = 10                
LLM_EVERY = 1          
USE_LLM = True          
NUM_FOOD = 40           
END_PAUSE = 4
NAMES = ["Red", "Blue", "Green", "Yellow"]
START_MODES = ["FOOD", "HUNT", "SAFE", "FOOD"]   
MODES = ["FOOD", "HUNT", "SAFE"]

BACKGROUND = (40, 44, 52)
GRID_LINE = (50, 55, 66)
EMPTY = (28, 31, 38)
FOOD = (240, 200, 60)
SNAKE_BODY = [(200, 70, 70), (70, 120, 220), (70, 180, 90), (210, 180, 50)]
SNAKE_HEAD = [(150, 40, 40), (40, 80, 170), (40, 130, 60), (160, 130, 20)]
EYE = (255, 255, 255)
PUPIL = (0, 0, 0)
TITLE_TEXT = (255, 210, 80)
INFO_TEXT = (230, 230, 230)
REPLY_TEXT = (150, 220, 150)

CELL = 20
MARGIN = 10
PANEL_W = 400
BOARD_PX = 32 * CELL
PANEL_X = BOARD_PX + 2 * MARGIN
WINDOW_W = PANEL_X + PANEL_W
WINDOW_H = BOARD_PX + 2 * MARGIN

RULES = f"""You control one snake in a {32}x{32} arena with 3 other snakes. Everyone moves at the same time.
You die if you hit a wall or any snake body (yours too). Eating food makes you longer.
If two heads meet, the longer snake survives. A dead snake turns into food.
A fast autopilot does the steering and avoids walls and bodies. YOU choose the strategy:
  FOOD -> go for the nearest food (grow fast)
  HUNT -> chase and cut off the nearest smaller snake (only works if you are longer than it)
  SAFE -> stay in open space and avoid trouble (good when crowded or small)
Goal: be the longest snake, or the last one alive."""

brain = {"modes": list(START_MODES), "busy": False, "latency": 0.0, "who": 0,
         "reply": "No LLM answer yet.", "last_len": [3, 3, 3, 3]}


def first_step(env, start, goals, blocked):
    """Breadth-first search: the first move on the shortest path to any goal."""
    queue, seen = deque([(start, None)]), {start}
    while queue:
        cell, first = queue.popleft()
        if first and cell in goals:
            return first
        for name, (dr, dc) in DIRS.items():
            nxt = (cell[0] + dr, cell[1] + dc)
            if nxt not in seen and env.inside(nxt) and nxt not in blocked:
                seen.add(nxt)
                queue.append((nxt, first or name))
    return None


def open_space(env, start, blocked, limit=300):
    """How many free cells can we reach from here? Small = a dead end."""
    seen, stack = {start}, [start]
    while stack and len(seen) < limit:
        r, c = stack.pop()
        for dr, dc in DIRS.values():
            nxt = (r + dr, c + dc)
            if nxt not in seen and env.inside(nxt) and nxt not in blocked:
                seen.add(nxt)
                stack.append(nxt)
    return len(seen)


def choose_move(env, i, mode):
    snake = env.snakes[i]
    head, length = snake[0], len(snake)
    blocked = env.occupied() - {snake[-1]}           
    enemies = [j for j in range(env.n) if j != i and env.alive[j]]

    danger = set()
    for j in enemies:
        if len(env.snakes[j]) >= length:
            hr, hc = env.snakes[j][0]
            danger.update((hr + dr, hc + dc) for dr, dc in DIRS.values())

    legal = {m: (head[0] + dr, head[1] + dc) for m, (dr, dc) in DIRS.items()
             if env.inside((head[0] + dr, head[1] + dc)) and (head[0] + dr, head[1] + dc) not in blocked}
    if not legal:
        return env.facing[i]
    safe = {m: c for m, c in legal.items() if c not in danger} or legal
    room = {m: open_space(env, c, blocked) for m, c in safe.items()}
    roomiest = max(room, key=room.get)

    goals = set(env.food)
    if mode == "HUNT":
        prey = [j for j in enemies if len(env.snakes[j]) < length]
        if prey:
            j = min(prey, key=lambda j: abs(env.snakes[j][0][0] - head[0]) + abs(env.snakes[j][0][1] - head[1]))
            dr, dc = DIRS[env.facing[j]]
            ahead = (env.snakes[j][0][0] + dr, env.snakes[j][0][1] + dc)   # cut it off
            if env.inside(ahead) and ahead not in blocked:
                goals = {ahead}
    if mode == "SAFE":
        goals = set()                                
        for m, c in safe.items():
            if c in env.food and room[m] >= length:
                return m

    move = first_step(env, head, goals, blocked | (danger - goals)) if goals else None
    if move in safe and room[move] >= length:        
        return move
    return roomiest


def build_prompt(env, i):
    me, head = env.snakes[i], env.snakes[i][0]
    dist = lambda cell: abs(cell[0] - head[0]) + abs(cell[1] - head[1])
    food = min(map(dist, env.food)) if env.food else "none"
    board = "\n".join(f"  {NAMES[j]}: length {len(env.snakes[j])}" + ("" if env.alive[j] else " (dead)")
                      for j in range(env.n))
    rivals = [j for j in range(env.n) if j != i and env.alive[j]]
    near = "none"
    if rivals:
        j = min(rivals, key=lambda j: dist(env.snakes[j][0]))
        near = f"{NAMES[j]}, length {len(env.snakes[j])}, {dist(env.snakes[j][0])} cells away"
    return f"""{RULES}

        You are the {NAMES[i]} snake. Your strategy now: {brain['modes'][i]}.
        Your length: {len(me)} (it was {brain['last_len'][i]} at your last decision).
        Nearest food: {food} cells away. Nearest rival: {near}.

        Scoreboard:
        {board}

        Your surroundings (11x11 window, H = your head, o = your body, X = rival head, x = rival body, F = food, # = wall):
        {env.view(i)}

        Think briefly, then finish with exactly one line in this format:
        MODE: FOOD   (or HUNT, SAFE)"""


def parse_mode(text):
    matches = re.findall(r"MODE:\s*(FOOD|HUNT|SAFE)", text, re.IGNORECASE)
    return matches[-1].upper() if matches else None


def ask_in_background(i, prompt, length, logger, game, step):
    """Runs in its own thread, so the game keeps moving while we wait."""
    start = time.time()
    reply = ask_llm(prompt)
    mode = parse_mode(reply)
    if mode:
        brain["modes"][i] = mode
    brain["reply"] = f"[{NAMES[i]}] {reply or '(empty reply)'}"
    brain["latency"] = time.time() - start
    brain["last_len"][i] = length
    logger.log(game=game, step=step, snake=NAMES[i], prompt=prompt, reply=reply, mode=mode,
               valid=mode is not None, latency=brain["latency"])
    print(f"  LLM answered for {NAMES[i]} in {brain['latency']:.1f}s -> {mode}")
    brain["busy"] = False


def draw(screen, env, info):
    screen.fill(BACKGROUND)
    pygame.draw.rect(screen, EMPTY, (MARGIN, MARGIN, BOARD_PX, BOARD_PX))

    def square(cell):
        return pygame.Rect(MARGIN + cell[1] * CELL, MARGIN + cell[0] * CELL, CELL, CELL)

    for cell in env.food:
        pygame.draw.rect(screen, FOOD, square(cell).inflate(-6, -6))
    for i in range(env.n):
        for part in env.snakes[i][1:]:
            pygame.draw.rect(screen, SNAKE_BODY[i], square(part))
        if env.alive[i]:
            pygame.draw.rect(screen, SNAKE_HEAD[i], square(env.snakes[i][0]))

    draw_grid_lines(screen, env.size, CELL, MARGIN, MARGIN, GRID_LINE)

    eyes = {"UP": [(0.3, 0.3), (0.7, 0.3)], "DOWN": [(0.3, 0.7), (0.7, 0.7)],
            "LEFT": [(0.3, 0.3), (0.3, 0.7)], "RIGHT": [(0.7, 0.3), (0.7, 0.7)]}
    for i in range(env.n):
        if env.alive[i]:
            head = square(env.snakes[i][0])
            for fx, fy in eyes[env.facing[i]]:
                center = (head.x + int(fx * CELL), head.y + int(fy * CELL))
                pygame.draw.circle(screen, EYE, center, 3)
                pygame.draw.circle(screen, PUPIL, center, 1)

    draw_panel(screen, PANEL_X, PANEL_W - MARGIN, "Snake Arena", info, brain["reply"],
               TITLE_TEXT, INFO_TEXT, REPLY_TEXT)
    pygame.display.flip()


def play_game(screen, env, logger, game):
    env.reset()
    brain.update(modes=list(START_MODES), busy=False, reply="No LLM answer yet.", last_len=[3] * env.n)
    clock = pygame.time.Clock()
    last_call, step = 0, 0
    info = []

    for step in range(1, MAX_STEPS + 1):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        if USE_LLM and not brain["busy"] and time.time() - last_call > LLM_EVERY:
            living = [j for j in range(env.n) if env.alive[j]]
            brain["who"] = next((j for j in range(brain["who"] + 1, brain["who"] + 1 + env.n)
                                 if env.alive[j % env.n]), living[0]) % env.n
            i = brain["who"]
            brain["busy"], last_call = True, time.time()
            args = (i, build_prompt(env, i), len(env.snakes[i]), logger, game, step)
            threading.Thread(target=ask_in_background, args=args, daemon=True).start()

        env.step({i: choose_move(env, i, brain["modes"][i]) for i in range(env.n) if env.alive[i]})

        info = [f"Game: {game}/{NUM_GAMES}   Step: {step}/{MAX_STEPS}"]
        for i in range(env.n):
            state = f"length {len(env.snakes[i])}  {brain['modes'][i]}" if env.alive[i] else f"DEAD ({env.death[i]})"
            info.append(f"{NAMES[i]}: {state}")
        info.append(f"LLM: {'thinking...' if brain['busy'] else 'idle'}  (last {brain['latency']:.1f}s)")
        draw(screen, env, info)
        clock.tick(FPS)
        if env.done:
            break

    lengths = [len(s) for s in env.snakes]
    living = [i for i in range(env.n) if env.alive[i]]
    winner = living[0] if len(living) == 1 else max(living or range(env.n), key=lambda i: lengths[i])
    draw(screen, env, info + [f"Winner: {NAMES[winner]}"])
    pause(END_PAUSE)
    return winner, lengths


if __name__ == "__main__":
    screen = open_window("Tier 5 - Snake Arena", WINDOW_W, WINDOW_H)
    env = ArenaEnv(size=32, num_food=NUM_FOOD)
    logger = JsonlLogger("tier5_arena")

    wins = [0] * 4
    for g in range(1, NUM_GAMES + 1):
        winner, lengths = play_game(screen, env, logger, g)
        wins[winner] += 1
        print(f"Game {g} finished. Winner: {NAMES[winner]}. Final lengths: {lengths}\n")

    print("Wins: " + ", ".join(f"{NAMES[i]} {wins[i]}" for i in range(4)))
    print(f"Log saved to: {logger.path}")
    pygame.quit()
