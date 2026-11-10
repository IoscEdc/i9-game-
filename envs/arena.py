import random

DIRS = {"UP": (-1, 0), "DOWN": (1, 0), "LEFT": (0, -1), "RIGHT": (0, 1)}


class ArenaEnv:
    def __init__(self, size=20, num_food=25, dead_to_food=True, seed=None):
        self.size = size
        self.num_food = num_food
        self.dead_to_food = dead_to_food
        self.rng = random.Random(seed)

    def reset(self):
        s = self.size
        starts = [((4, 6), "RIGHT"), ((6, s - 5), "DOWN"),
                  ((s - 5, s - 7), "LEFT"), ((s - 7, 4), "UP")]
        self.n = len(starts)
        self.snakes, self.facing = [], []
        for (r, c), name in starts:
            dr, dc = DIRS[name]
            self.snakes.append([(r - k * dr, c - k * dc) for k in range(3)])
            self.facing.append(name)
        self.alive = [True] * self.n
        self.death = [""] * self.n
        self.steps = 0
        self.food = set()
        self._refill_food()

    def inside(self, cell):
        return 0 <= cell[0] < self.size and 0 <= cell[1] < self.size

    def occupied(self):
        return {cell for i in range(self.n) if self.alive[i] for cell in self.snakes[i]}

    def _refill_food(self):
        taken = self.occupied() | self.food
        while len(self.food) < self.num_food:
            cell = (self.rng.randrange(self.size), self.rng.randrange(self.size))
            if cell not in taken:
                self.food.add(cell)
                taken.add(cell)

    @property
    def done(self):
        return sum(self.alive) <= 1

    def step(self, moves):
        self.steps += 1
        alive = [i for i in range(self.n) if self.alive[i]]

        new_head = {}
        for i in alive:
            self.facing[i] = moves.get(i, self.facing[i])
            dr, dc = DIRS[self.facing[i]]
            head = self.snakes[i][0]
            new_head[i] = (head[0] + dr, head[1] + dc)
        growing = {i for i in alive if new_head[i] in self.food}

        blocked = set()
        for i in alive:
            blocked.update(self.snakes[i] if i in growing else self.snakes[i][:-1])

        dead = {}
        for i in alive:
            if not self.inside(new_head[i]):
                dead[i] = "hit the wall"
            elif new_head[i] in blocked:
                dead[i] = "hit a snake"
        for i in alive:
            rivals = [j for j in alive if j != i and new_head[j] == new_head[i]]
            if rivals and len(self.snakes[i]) <= max(len(self.snakes[j]) for j in rivals):
                dead[i] = "lost a head-on crash"

        for i in alive:
            if i in dead:
                self.alive[i], self.death[i] = False, dead[i]
                if self.dead_to_food:
                    self.food.update(self.snakes[i][::2])
                self.snakes[i] = []
                continue
            self.snakes[i].insert(0, new_head[i])
            if i in growing:
                self.food.discard(new_head[i])
            else:
                self.snakes[i].pop()
        self._refill_food()

    def look(self, i, move):
        dr, dc = DIRS[move]
        head = self.snakes[i][0]
        cell = (head[0] + dr, head[1] + dc)
        if not self.inside(cell):
            return "WALL"
        if cell in self.occupied() - {self.snakes[i][-1]}:
            return "BODY"
        return "FOOD" if cell in self.food else "SAFE"

    def nearest_food(self, i):
        hr, hc = self.snakes[i][0]
        if not self.food:
            return None
        r, c = min(self.food, key=lambda f: abs(f[0] - hr) + abs(f[1] - hc))
        return r - hr, c - hc

    def view(self, i, radius=5):
        hr, hc = self.snakes[i][0]
        lines = []
        for r in range(hr - radius, hr + radius + 1):
            row = []
            for c in range(hc - radius, hc + radius + 1):
                cell = (r, c)
                owner = next((j for j in range(self.n) if cell in self.snakes[j]), None)
                if not self.inside(cell):
                    row.append("#")
                elif owner == i:
                    row.append("H" if cell == self.snakes[i][0] else "o")
                elif owner is not None:
                    row.append("X" if cell == self.snakes[owner][0] else "x")
                elif cell in self.food:
                    row.append("F")
                else:
                    row.append(".")
            lines.append(" ".join(row))
        return "\n".join(lines)