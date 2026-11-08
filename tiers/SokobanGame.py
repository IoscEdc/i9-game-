import re
import pygame

from core.llm import ask_llm
from core.logger import JsonlLogger
from core.viewer import open_window, pause, draw_grid_lines, draw_panel
from envs.sokoban import SokobanGame

NUM_LEVELS = 3
MAX_ATTEMPTS = 2        
MAX_CALLS = 10          
PLAN_LEN = 4            
PAUSE_SECONDS = 0.5      
MOVE_PAUSE = 0.4        
END_PAUSE = 3
USE_SAFETY_HINTS = False    
USE_SOLVER_HINT = False     
MOVES = ["UP", "DOWN", "LEFT", "RIGHT"]

BACKGROUND = (0, 0, 0)
GRID_LINE = (20, 20, 25)
FLOOR = (225, 215, 190)
WALL = (90, 90, 100)
TARGET = (200, 70, 70)
BOX = (160, 100, 50)
BOX_ON_TARGET = (80, 170, 90)
PLAYER = (50, 100, 220)
TITLE_TEXT = (255, 210, 80)
INFO_TEXT = (230, 230, 230)
REPLY_TEXT = (150, 220, 150)

BOARD_PX = 480
MARGIN = 10
PANEL_W = 400
PANEL_X = BOARD_PX + 2 * MARGIN
WINDOW_W = PANEL_X + PANEL_W
WINDOW_H = BOARD_PX + 2 * MARGIN

RULES = """You are playing Sokoban on a 7x7 grid.
Legend: P = you, B = box, T = target spot, X = box already on a target, # = wall, . = floor.
Row 0 is the top, column 0 is the left.
Moves: UP (row-1), DOWN (row+1), LEFT (col-1), RIGHT (col+1).
Walking into a box pushes it one cell in that direction.
You can only push a box if the cell behind it is free (no wall, no other box). You cannot pull boxes.
A box pushed into a corner (and not on a target) is stuck forever and the level is lost.
Goal: push every box onto a target."""


def build_prompt(game, feedback, lessons):
    pr, pc = game.player()
    box_text = ", ".join(str(b) for b in sorted(game.boxes()))
    target_text = ", ".join(str(t) for t in sorted(game.targets()))

    hints = ""
    if USE_SAFETY_HINTS:
        lines = [f"  {m}: {game.look(m)}" for m in MOVES]
        hints += "\nWhat happens for each move right now:\n" + "\n".join(lines) + "\n"
    if USE_SOLVER_HINT:
        solution = game.solve()
        if solution:
            hints += (f"\nA solver says a solution exists with {len(solution)} moves. "
                      f"It starts with: {', '.join(solution[:3])}\n")

    lesson_text = "\n".join(f"- {l}" for l in lessons) if lessons else "None yet"

    return f"""{RULES}

        Current grid:
        {game.state_to_text()}

        You are at row {pr}, column {pc}.
        Boxes (not yet solved) are at: {box_text}
        Targets are at: {target_text}
        {hints}
        Lessons from earlier failed attempts:
        {lesson_text}

        Result of your last plan:
        {feedback}

        Think about where each box must go, then plan up to {PLAN_LEN} moves.
        Finish with exactly one line in this format:
        PLAN: UP, UP, LEFT"""


def parse_plan(text):
    matches = re.findall(r"PLAN:\s*([A-Za-z ,]+)", text)
    if not matches:
        return []
    words = re.findall(r"[A-Za-z]+", matches[-1].upper())
    return [w for w in words if w in MOVES][:PLAN_LEN]


def draw(screen, game, info, reply):
    screen.fill(BACKGROUND)
    cell = BOARD_PX // game.size
    walls, targets, boxes, player = game.walls(), game.targets(), game.boxes(), game.player()

    for r in range(game.size):
        for c in range(game.size):
            pos = (r, c)
            square = pygame.Rect(MARGIN + c * cell, MARGIN + r * cell, cell, cell)
            inner = square.inflate(-cell // 2, -cell // 2)   
            big = square.inflate(-cell // 6, -cell // 6)
            if pos in walls:
                pygame.draw.rect(screen, WALL, square)
                continue
            pygame.draw.rect(screen, FLOOR, square)
            if pos in targets:
                pygame.draw.rect(screen, TARGET, inner, 4)       
            if pos in boxes:
                color = BOX_ON_TARGET if pos in targets else BOX
                pygame.draw.rect(screen, color, big)
            if pos == player:
                pygame.draw.rect(screen, PLAYER, inner)

    draw_grid_lines(screen, game.size, cell, MARGIN, MARGIN, GRID_LINE)
    draw_panel(screen, PANEL_X, PANEL_W - MARGIN, "Sokoban", info, reply,
               TITLE_TEXT, INFO_TEXT, REPLY_TEXT)
    pygame.display.flip()


def play_level(screen, game, logger, level):
    """Returns (solved, llm_calls_used)."""
    lessons = []
    total_calls = 0

    for attempt in range(1, MAX_ATTEMPTS + 1):
        game.reset(seed=level)
        feedback = "This is your first plan for this attempt."

        for call in range(1, MAX_CALLS + 1):
            total_calls += 1
            info = [f"Level: {level}/{NUM_LEVELS}",
                    f"Attempt: {attempt}/{MAX_ATTEMPTS}",
                    f"LLM call: {call}/{MAX_CALLS}"]

            draw(screen, game, info + ["Status: asking the LLM..."], "Thinking...")
            prompt = build_prompt(game, feedback, lessons)
            reply = ask_llm(prompt)
            plan = parse_plan(reply)

            status, executed, move = "ok", 0, None
            if not plan:
                status = "invalid"
                feedback = "Your reply had no valid PLAN line. Use: PLAN: UP, DOWN, ..."
            else:
                for move in plan:
                    result = game.step(move)
                    draw(screen, game, info + [f"Move: {move} -> {result}"], reply)
                    pause(MOVE_PAUSE)
                    if result == "BLOCKED":
                        status = "blocked"
                        break
                    executed += 1
                    if game.solved():
                        status = "solved"
                        break
                    if game.stuck_boxes():
                        status = "stuck"
                        break

                if status == "ok":
                    feedback = f"All {executed} moves were carried out. Plan the next moves."
                elif status == "blocked":
                    feedback = (f"{executed} of {len(plan)} moves were carried out, then {move} was "
                                f"blocked (wall or a box that cannot be pushed). Replan from here.")

            logger.log(level=level, attempt=attempt, call=call, prompt=prompt, reply=reply,
                       plan=plan, executed=executed, status=status)
            print(f"Level {level} | attempt {attempt} | call {call} | {plan} | {status}")

            if status == "solved":
                draw(screen, game, info + ["Result: SOLVED"], reply)
                pause(END_PAUSE)
                return True, total_calls
            if status == "stuck":
                box = game.stuck_boxes()[0]
                lessons.append(f"Attempt {attempt}: a box got stuck in a corner at {box} "
                               f"after the plan {plan}. Do not push boxes into corners.")
                draw(screen, game, info + ["Result: STUCK - restarting level"], reply)
                pause(END_PAUSE)
                break   
            pause(PAUSE_SECONDS)

    return False, total_calls


if __name__ == "__main__":
    screen = open_window("Tier 2 - Sokoban", WINDOW_W, WINDOW_H)
    game = SokobanGame(size=7, num_boxes=2)
    logger = JsonlLogger("tier2_sokoban")

    results = []
    for level in range(1, NUM_LEVELS + 1):
        solved, calls = play_level(screen, game, logger, level)
        results.append(solved)
        print(f"Level {level}: {'SOLVED' if solved else 'FAILED'} using {calls} LLM calls\n")

    print(f"Solved: {sum(results)} / {NUM_LEVELS}")
    print(f"Log saved to: {logger.path}")
    pygame.quit()
