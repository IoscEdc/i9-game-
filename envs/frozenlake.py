import gymnasium as gym

ACTIONS = {"LEFT": 0, "DOWN": 1, "RIGHT": 2, "UP": 3}


class FrozenLakeEnv:
    def __init__(self, slippery=False):
        self.env = gym.make("FrozenLake-v1", map_name="4x4", is_slippery=slippery)
        self.size = 4
        self.state = None

    def reset(self):
        self.state, _ = self.env.reset()

    def step(self, action_name):
        self.state, reward, terminated, truncated, _ = self.env.step(ACTIONS[action_name])
        return reward, (terminated or truncated)

    def position(self):
        return divmod(self.state, self.size)  # (row, col)

    def state_to_text(self):
        grid = self.env.unwrapped.desc  # the map
        player_row, player_col = self.position()
        lines = []
        for r in range(self.size):
            row = []
            for c in range(self.size):
                tile = grid[r][c].decode()
                row.append("P" if (r, c) == (player_row, player_col) else tile)
            lines.append(" ".join(row))
        return "\n".join(lines)

