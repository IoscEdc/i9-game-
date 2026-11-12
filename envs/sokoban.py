import random
from collections import deque

import numpy as np
from gym_sokoban.envs.sokoban_env import SokobanEnv

DIRS = {"UP": (-1, 0), "DOWN": (1, 0), "LEFT": (0, -1), "RIGHT": (0, 1)}
CODES = {"UP": 1, "DOWN": 2, "LEFT": 3, "RIGHT": 4}  


class SokobanGame:
    def __init__(self, size=7, num_boxes=1):
        self.size = size
        self.env = SokobanEnv(dim_room=(size, size), max_steps=1000, num_boxes=num_boxes)

    def reset(self, seed):
        random.seed(seed)
        np.random.seed(seed)
        self.env.reset()

    def _cells(self, grid, values):
        return {(int(r), int(c)) for r, c in np.argwhere(np.isin(grid, values))}

    def walls(self):
        return self._cells(self.env.room_fixed, [0])

    def targets(self):
        return self._cells(self.env.room_fixed, [2])

    def boxes(self):
        return self._cells(self.env.room_state, [3, 4])

    def player(self):
        return self._cells(self.env.room_state, [5]).pop()

    def solved(self):
        return self.boxes() == self.targets()

    def _corner(self, cell):
        r, c = cell
        walls = self.walls()
        vertical = (r - 1, c) in walls or (r + 1, c) in walls
        horizontal = (r, c - 1) in walls or (r, c + 1) in walls
        return vertical and horizontal

    def stuck_boxes(self):
        """Boxes that sit in a corner and are not on a target. They can never move again."""
        targets = self.targets()
        return [b for b in self.boxes() if b not in targets and self._corner(b)]

    def look(self, move):
        """What happens if we go this way?"""
        dr, dc = DIRS[move]
        pr, pc = self.player()
        nxt = (pr + dr, pc + dc)
        walls, boxes = self.walls(), self.boxes()
        if nxt in walls:
            return "WALL"
        if nxt not in boxes:
            return "FREE"
        beyond = (nxt[0] + dr, nxt[1] + dc)
        if beyond in walls or beyond in boxes:
            return "BOX_BLOCKED"
        if beyond not in self.targets() and self._corner(beyond):
            return "PUSH_BOX_INTO_CORNER (deadlock!)"
        return "PUSH_BOX"

    def step(self, move):
        """Returns BLOCKED (nothing changed), MOVED, or PUSHED."""
        before_player, before_boxes = self.player(), self.boxes()
        self.env.step(CODES[move])
        if self.player() == before_player:
            return "BLOCKED"
        return "PUSHED" if self.boxes() != before_boxes else "MOVED"

    def state_to_text(self):
        walls, targets, boxes, player = self.walls(), self.targets(), self.boxes(), self.player()
        lines = []
        for r in range(self.size):
            row = []
            for c in range(self.size):
                cell = (r, c)
                if cell == player:
                    row.append("P")
                elif cell in boxes and cell in targets:
                    row.append("X")
                elif cell in boxes:
                    row.append("B")
                elif cell in targets:
                    row.append("T")
                elif cell in walls:
                    row.append("#")
                else:
                    row.append(".")
            lines.append(" ".join(row))
        return "\n".join(lines)

    def solve(self, limit=200000):
        walls, targets = self.walls(), self.targets()
        start = (self.player(), frozenset(self.boxes()))
        queue = deque([(start, [])])
        seen = {start}
        while queue and len(seen) < limit:
            (player, boxes), path = queue.popleft()
            if boxes == targets:
                return path
            for name, (dr, dc) in DIRS.items():
                nxt = (player[0] + dr, player[1] + dc)
                if nxt in walls:
                    continue
                new_boxes = boxes
                if nxt in boxes:
                    beyond = (nxt[0] + dr, nxt[1] + dc)
                    if beyond in walls or beyond in boxes:
                        continue
                    new_boxes = (boxes - {nxt}) | {beyond}
                state = (nxt, new_boxes)
                if state not in seen:
                    seen.add(state)
                    queue.append((state, path + [name]))
        return None
