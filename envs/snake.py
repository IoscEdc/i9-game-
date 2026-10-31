import random

DIRECTIONS = {"UP": (-1, 0), "DOWN": (1, 0), "LEFT": (0, -1), "RIGHT": (0, 1)}


class SnakeEnv:
    def __init__(self, size=8, seed=None):
        self.size = size
        self.rng = random.Random(seed)
        self.snake = []  
        self.food = None
        self.score = 0

    def reset(self):
        mid = self.size // 2
        self.snake = [(mid, 2), (mid, 1), (mid, 0)]
        self.score = 0
        self.food = self._place_food()

    def _place_food(self):
        free = [(r, c) for r in range(self.size) for c in range(self.size)
                if (r, c) not in self.snake]
        return self.rng.choice(free) if free else None

    @property
    def head(self):
        return self.snake[0]

    def _inside(self, r, c):
        return 0 <= r < self.size and 0 <= c < self.size

    def look(self, move):
        dr, dc = DIRECTIONS[move]
        r, c = self.head[0] + dr, self.head[1] + dc
        if not self._inside(r, c):
            return "WALL"
        if (r, c) in self.snake[:-1]: 
            return "BODY"
        if (r, c) == self.food:
            return "FOOD"
        return "SAFE"

    def step(self, move):
        status = self.look(move)
        if status in ("WALL", "BODY"):
            return -1, True

        dr, dc = DIRECTIONS[move]
        new_head = (self.head[0] + dr, self.head[1] + dc)
        self.snake.insert(0, new_head)

        if status == "FOOD":
            self.score += 1
            self.food = self._place_food()
            if self.food is None:      # board is full, you win
                return 1, True
            return 1, False

        self.snake.pop()               # no food: the tail moves forward
        return 0, False

    def state_to_text(self):
        lines = []
        for r in range(self.size):
            row = []
            for c in range(self.size):
                if (r, c) == self.head:
                    row.append("H")
                elif (r, c) in self.snake:
                    row.append("o")
                elif (r, c) == self.food:
                    row.append("F")
                else:
                    row.append(".")
            lines.append(" ".join(row))
        return "\n".join(lines)

    