import random

DIRECTIONS = {"UP": (-1, 0), "DOWN": (1, 0), "LEFT": (0, -1), "RIGHT": (0, 1)}
OPPOSITES = {"UP": "DOWN", "DOWN": "UP", "LEFT": "RIGHT", "RIGHT": "LEFT"}


class SnakeGame:
    def __init__(self, size=8):
        self.size = size
        self.reset()

    def reset(self):
        m = self.size // 2
        self.snake = [(m, m), (m, m - 1), (m, m - 2)]
        self.current_direction, self.score, self.steps, self.game_over = "RIGHT", 0, 0, False
        self.food = self._spawn_food()

    def _spawn_food(self):
        empty = [(r, c) for r in range(self.size) for c in range(self.size) if (r, c) not in self.snake]
        return random.choice(empty) if empty else (0, 0)

    def get_safe_moves(self):
        hr, hc = self.snake[0]
        neck = self.snake[1] if len(self.snake) > 1 else None
        safe = []
        for d, (dr, dc) in DIRECTIONS.items():
            nr, nc = hr + dr, hc + dc
            if (neck and (nr, nc) == neck) or not (0 <= nr < self.size and 0 <= nc < self.size) or (nr, nc) in self.snake[:-1]:
                continue
            safe.append(d)
        return safe

    def get_board_text(self):
        return "\n".join(
            " ".join("H" if (r, c) == self.snake[0] else ("B" if (r, c) in self.snake else ("F" if (r, c) == self.food else ".")) for c in range(self.size))
            for r in range(self.size)
        )

    def step(self, d):
        if self.game_over:
            return False
        d = d.strip().upper() if d else self.current_direction
        if d not in DIRECTIONS or (len(self.snake) > 1 and d == OPPOSITES.get(self.current_direction)):
            d = self.current_direction
        self.current_direction = d
        dr, dc = DIRECTIONS[d]
        nh = (self.snake[0][0] + dr, self.snake[0][1] + dc)
        self.steps += 1
        if not (0 <= nh[0] < self.size and 0 <= nh[1] < self.size) or nh in self.snake:
            self.game_over = True
            return False
        self.snake.insert(0, nh)
        if nh == self.food:
            self.score += 1
            if len(self.snake) == self.size * self.size:
                self.game_over = True
                return False
            self.food = self._spawn_food()
        else:
            self.snake.pop()
        return True
