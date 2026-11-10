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

NUM_GAMES = 2
SIZE = 20
NUM_FOOD = 25
MAX_STEPS = 150
LLM_SNAKES = [0, 1]
ALGO_MODES = {2: "FOOD", 3: "HUNT"}
MAX_PLAN_STEPS = 12
MIN_GAP = 4
MOVE_DELAY = 0.15
USE_HINTS = True
STOP_BEFORE_CRASH = True
REPLAN_NEAR = 3
END_PAUSE = 4
NAMES = ["Red", "Blue", "Green", "Yellow"]
MOVES = ["UP", "DOWN", "LEFT", "RIGHT"]

BACKGROUND = (0, 0, 0)
GRID_LINE = (120, 120, 120)
EMPTY = (28, 31, 38)
FOOD = (240, 200, 60)
SNAKE_BODY = [(200, 70, 70), (70, 120, 220), (70, 180, 90), (210, 180, 50)]
SNAKE_HEAD = [(150, 40, 40), (40, 80, 170), (40, 130, 60), (160, 130, 20)]
EYE = (255, 255, 255)
PUPIL = (0, 0, 0)
TITLE_TEXT = (255, 210, 80)
INFO_TEXT = (230, 230, 230)
REPLY_TEXT = (150, 220, 150)

CELL = 640 // SIZE
MARGIN = 10
PANEL_W = 400
BOARD_PX = SIZE * CELL
PANEL_X = BOARD_PX + 2 * MARGIN
WINDOW_W = PANEL_X + PANEL_W
WINDOW_H = BOARD_PX + 2 * MARGIN

RULES = f"""You control one snake on a {SIZE}x{SIZE} board shared with 3 other snakes. Everyone moves at the same time.
Row 0 is the top, column 0 is the left.
Moves: UP (row-1), DOWN (row+1), LEFT (col-1), RIGHT (col+1).
You die if you hit a wall or any snake body (yours too). You cannot reverse into your own neck.
Eating food makes you longer. If two heads move onto the same cell, the longer snake survives.
A dead snake turns into food.
Goal: be the longest snake, or the last one alive."""

gate = threading.Lock()
last_call = [0.0]


def wait_for_turn():
    with gate:
        delay = last_call[0] + MIN_GAP - time.time()
        if delay > 0:
            time.sleep(delay)
        last_call[0] = time.time()


def first_step(env, start, goals, blocked):
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
    seen, stack = {start}, [start]
    while stack and len(seen) < limit:
        r, c = stack.pop()
        for dr, dc in DIRS.values():
            nxt = (r + dr, c + dc)
            if nxt not in seen and env.inside(nxt) and nxt not in blocked:
                seen.add(nxt)
                stack.append(nxt)
    return len(seen)


def algo_move(env, i, mode):
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
            ahead = (env.snakes[j][0][0] + dr, env.snakes[j][0][1] + dc)
            if env.inside(ahead) and ahead not in blocked:
                goals = {ahead}

    move = first_step(env, head, goals, blocked | (danger - goals)) if goals else None
    if move in safe and room[move] >= length:
        return move
    return roomiest


def build_prompt(env, i, feedback):
    head = env.snakes[i][0]
    food = env.nearest_food(i)
    if food:
        food_text = (f"{abs(food[0])} rows {'down' if food[0] > 0 else 'up'}, "
                     f"{abs(food[1])} columns {'right' if food[1] > 0 else 'left'}")
    else:
        food_text = "none"

    hints = ""
    if USE_HINTS:
        lines = [f"  {m}: {env.look(i, m)}" for m in MOVES]
        hints = "\nWhat is next to your head right now (only true for your FIRST move):\n" + "\n".join(lines) + "\n"

    board = "\n".join(f"  {NAMES[j]}: length {len(env.snakes[j])}" + ("" if env.alive[j] else " (dead)")
                      for j in range(env.n))
    return f"""{RULES}

        You are the {NAMES[i]} snake. You are at row {head[0]}, column {head[1]} and last moved {env.facing[i]}.
        Your length: {len(env.snakes[i])}. Nearest food: {food_text}.
        {hints}
        Scoreboard:
        {board}

        Your surroundings (11x11 window, H = your head, o = your body, X = rival head, x = rival body, F = food, # = wall):
        {env.view(i)}

        Result of your last plan:
        {feedback}

        Reply with ONLY one line and no explanation. Each part is a direction and a number of steps, at most {MAX_PLAN_STEPS} steps in total:
        PLAN: UP 4, LEFT 3, DOWN 2"""


def parse_plan(text):
    found = re.findall(r"PLAN:(.*)", text.upper())
    line = found[-1] if found else (text.upper() if len(text) < 100 else "")
    plan = []
    for name, count in re.findall(r"(UP|DOWN|LEFT|RIGHT)\s*(\d*)", line):
        plan += [name] * min(int(count or 1), MAX_PLAN_STEPS)
    return plan[:MAX_PLAN_STEPS]


def ask_snake(st, i, prompt, facing, logger, game, step):
    wait_for_turn()
    start = time.time()
    reply = ask_llm(prompt)
    plan = parse_plan(reply)
    valid = bool(plan)
    if not plan:
        st["invalid"] += 1
        plan = [facing]
    st["reply"] = f"[{NAMES[i]}] {reply or '(empty reply)'}"
    st["latency"] = time.time() - start
    st["calls"] += 1
    logger.log(game=game, step=step, snake=NAMES[i], prompt=prompt, reply=reply,
               plan=plan, valid=valid, latency=st["latency"])
    print(f"  {NAMES[i]} planned {len(plan)} moves in {st['latency']:.1f}s")
    st["planned"][i], st["done"][i], st["fresh"][i] = len(plan), 0, True
    st["plans"][i] = plan
    st["thinking"][i] = False


def draw(screen, env, info, reply):
    screen.fill(BACKGROUND)
    pygame.draw.rect(screen, EMPTY, (MARGIN, MARGIN, BOARD_PX, BOARD_PX))

    def square(cell):
        return pygame.Rect(MARGIN + cell[1] * CELL, MARGIN + cell[0] * CELL, CELL, CELL)

    for cell in env.food:
        pygame.draw.rect(screen, FOOD, square(cell).inflate(-CELL // 3, -CELL // 3))
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
                pygame.draw.circle(screen, EYE, center, max(CELL // 7, 2))
                pygame.draw.circle(screen, PUPIL, center, max(CELL // 14, 1))

    draw_panel(screen, PANEL_X, PANEL_W - MARGIN, "Snake Arena", info, reply,
               TITLE_TEXT, INFO_TEXT, REPLY_TEXT)
    pygame.display.flip()


def play_game(screen, env, logger, game):
    env.reset()
    n = env.n
    st = {"plans": [[] for _ in range(n)], "thinking": [False] * n, "fresh": [False] * n,
          "planned": [0] * n, "done": [0] * n, "feedback": ["This is your first plan."] * n,
          "reply": "No LLM answer yet.", "latency": 0.0, "calls": 0, "invalid": 0, "cut": 0}
    clock = pygame.time.Clock()
    step = 0

    def info_lines(status):
        lines = [f"Game: {game}/{NUM_GAMES}   Step: {step}/{MAX_STEPS}"]
        for i in range(n):
            kind = "LLM" if i in LLM_SNAKES else "algo"
            if not env.alive[i]:
                lines.append(f"{NAMES[i]} ({kind}): DEAD ({env.death[i]})")
            elif st["thinking"][i]:
                lines.append(f"{NAMES[i]} ({kind}): length {len(env.snakes[i])}  thinking...")
            elif i in LLM_SNAKES:
                lines.append(f"{NAMES[i]} ({kind}): length {len(env.snakes[i])}  {len(st['plans'][i])} moves left")
            else:
                lines.append(f"{NAMES[i]} ({kind}): length {len(env.snakes[i])}")
        lines.append(f"{status} ({st['latency']:.1f}s)")
        return lines

    def near_rival(i):
        hr, hc = env.snakes[i][0]
        return any(abs(env.snakes[j][0][0] - hr) + abs(env.snakes[j][0][1] - hc) <= REPLAN_NEAR
                   for j in range(n) if j != i and env.alive[j])

    while step < MAX_STEPS and not env.done:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
        alive = [i for i in range(n) if env.alive[i]]
        llm_alive = [i for i in alive if i in LLM_SNAKES]

        for i in llm_alive:
            if not st["plans"][i] or st["fresh"][i]:
                continue
            crash = env.look(i, st["plans"][i][0])
            if STOP_BEFORE_CRASH and crash in ("WALL", "BODY"):
                st["feedback"][i] = (f"{st['done'][i]} of {st['planned'][i]} moves were carried out, then "
                                     f"{st['plans'][i][0]} would have hit a {crash.lower()}. Plan again from here.")
                st["plans"][i], st["cut"] = [], st["cut"] + 1
            elif st["done"][i] >= 2 and near_rival(i):
                st["feedback"][i] = (f"{st['done'][i]} of {st['planned'][i]} moves were carried out, then a rival "
                                     f"came close. Plan again from here.")
                st["plans"][i], st["cut"] = [], st["cut"] + 1

        for i in llm_alive:
            if not st["plans"][i] and not st["thinking"][i]:
                st["thinking"][i] = True
                args = (st, i, build_prompt(env, i, st["feedback"][i]), env.facing[i], logger, game, step)
                threading.Thread(target=ask_snake, args=args, daemon=True).start()

        if any(not st["plans"][i] for i in llm_alive):
            draw(screen, env, info_lines("Waiting for the LLM..."), st["reply"])
            clock.tick(30)
            continue

        moves = {}
        for i in alive:
            if i in LLM_SNAKES:
                moves[i] = st["plans"][i].pop(0)
                st["fresh"][i] = False
                st["done"][i] += 1
                if not st["plans"][i]:
                    st["feedback"][i] = f"All {st['planned'][i]} moves were carried out."
            else:
                moves[i] = algo_move(env, i, ALGO_MODES.get(i, "FOOD"))
        env.step(moves)
        step += 1
        draw(screen, env, info_lines("Playing"), st["reply"])
        pause(MOVE_DELAY)

    lengths = [len(s) for s in env.snakes]
    living = [i for i in range(n) if env.alive[i]]
    winner = living[0] if len(living) == 1 else max(living or range(n), key=lambda i: lengths[i])
    draw(screen, env, info_lines(f"Winner: {NAMES[winner]}"), st["reply"])
    pause(END_PAUSE)
    print(f"LLM calls: {st['calls']}, unreadable answers: {st['invalid']}, plans cut: {st['cut']}")
    return winner, lengths


if __name__ == "__main__":
    screen = open_window("Tier 5 - Snake Arena", WINDOW_W, WINDOW_H)
    env = ArenaEnv(size=SIZE, num_food=NUM_FOOD)
    logger = JsonlLogger("tier5_arena")

    wins = [0] * 4
    llm_total, algo_total = 0, 0
    for g in range(1, NUM_GAMES + 1):
        winner, lengths = play_game(screen, env, logger, g)
        wins[winner] += 1
        llm_total += sum(lengths[i] for i in LLM_SNAKES)
        algo_total += sum(lengths[i] for i in range(4) if i not in LLM_SNAKES)
        print(f"Game {g} finished. Winner: {NAMES[winner]}. Final lengths: {lengths}\n")

    print("Wins: " + ", ".join(f"{NAMES[i]} {wins[i]}" for i in range(4)))
    print(f"Wins by LLM snakes: {sum(wins[i] for i in LLM_SNAKES)} of {NUM_GAMES}")
    print(f"Total final length - LLM snakes: {llm_total}, algorithm snakes: {algo_total}")
    print(f"Log saved to: {logger.path}")
    pygame.quit()
