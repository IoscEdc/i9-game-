import random

import gymnasium as gym
import numpy as np
import ale_py

if hasattr(gym, "register_envs"):
    gym.register_envs(ale_py)

ACTIONS = {"NOOP": 0, "FIRE": 1, "RIGHT": 2, "LEFT": 3}


def bounce(x, left, right):
    """Fold x back into [left, right], as if the ball bounced off the side walls."""
    width = right - left
    u = (x - left) % (2 * width)
    return left + (2 * width - u if u > width else u)


class BreakoutEnv:
    def __init__(self, frameskip=1):
        self.env = gym.make("ALE/Breakout-v5", frameskip=frameskip, repeat_action_probability=0.0)

    def reset(self):
        self.frame, info = self.env.reset()
        self.score, self.lives, self.done = 0, info["lives"], False
        self._calibrate()
        self.ball = self.vel = self.target = None   
        self.paddle_x = self.paddle_v = None
        self.paddle_w = 16
        self.unseen = 0
        self.cleared, self._empty = 0, False
        self._look()
        for _ in range(random.randint(0, 30)):      
            self.step("NOOP")

    def step(self, action_name):
        self.frame, reward, term, trunc, info = self.env.step(ACTIONS[action_name])
        self.score += int(reward)
        self.lives = info["lives"]
        self.done = term or trunc
        self._look()
        self._count_clears() 

    def _count_clears(self):
        """The game has two brick screens. Count each time the bricks run out."""
        lit = self.frame[self.brick_top:self.brick_bot + 1, self.left:self.right].any(axis=2).sum()
        if lit < 30 and not self._empty:
            self._empty = True
            self.cleared += 1
        elif lit >= 30:
            self._empty = False

    def _calibrate(self):
        f = self.frame
        cols = np.nonzero(f[120].any(axis=1))[0]            
        self.left = int(cols[cols < 80].max()) + 1           
        self.right = int(cols[cols >= 80].min())             
        rows = np.nonzero(f[:, self.left:self.right].any(axis=2).any(axis=1))[0]
        runs, start = [], rows[0]
        for a, b in zip(rows[:-1], rows[1:]):
            if b != a + 1:
                runs.append((int(start), int(a)))
                start = b
        runs.append((int(start), int(rows[-1])))
        self.pad_top, self.pad_bot = runs[-1]                
        self.brick_top, self.brick_bot = runs[-2]            
        top_wall_bot = runs[-3][1]
        self.bands = [(top_wall_bot + 1, self.brick_top), (self.brick_bot + 1, self.pad_top)]

    def _look(self):
        l, r = self.left, self.right

        cols = np.nonzero(self.frame[self.pad_top:self.pad_bot + 1, l:r].any(axis=2).any(axis=0))[0]
        if len(cols):
            x = l + (cols.min() + cols.max() + 1) / 2
            self.paddle_v = 0 if self.paddle_x is None else x - self.paddle_x
            self.paddle_x = x
            self.paddle_w = int(cols.max() - cols.min() + 1)   

        found = None
        for y0, y1 in self.bands:
            ys, xs = np.nonzero(self.frame[y0:y1, l:r].any(axis=2))
            if len(xs):
                found = (l + xs.mean() + 0.5, y0 + ys.mean() + 0.5)

        if found is None:
            self.unseen += 1
            self.vel = None if self.unseen > 1 else self.vel
            return
        if self.ball is not None and self.unseen == 0:
            self.vel = (found[0] - self.ball[0], found[1] - self.ball[1])
        else:
            self.vel = None                                   
        self.ball, self.unseen = found, 0
        self._predict()

    def _predict(self):
        """Where will the ball cross the paddle row? Follows wall bounces."""
        if self.vel is None or self.vel[1] == 0:
            return
        (x, y), (vx, vy) = self.ball, self.vel
        if vy > 0:
            dist = self.pad_top - y
        else:                                                 
            dist = (y - self.brick_bot) + (self.pad_top - self.brick_bot)
        self.target = bounce(x + vx * dist / abs(vy), self.left + 1, self.right - 1)

    def bricks_left(self):
        """Percent of bricks remaining in the left, middle and right third."""
        area = self.frame[self.brick_top:self.brick_bot + 1, self.left:self.right].any(axis=2)
        return [int(100 * part.mean()) for part in np.array_split(area, 3, axis=1)]

    def state_to_text(self):
        left, mid, right = self.bricks_left()
        if self.ball and self.vel:
            dx = "right" if self.vel[0] > 0 else "left" if self.vel[0] < 0 else "straight"
            dy = "down" if self.vel[1] > 0 else "up"
            ball = f"x={self.ball[0]:.0f}, y={self.ball[1]:.0f}, moving {dx} and {dy}"
        else:
            ball = "hidden (inside the bricks or not launched)"
        return (f"Ball: {ball}\n"
                f"Bricks left: LEFT third {left}%, MIDDLE third {mid}%, RIGHT third {right}%\n"
                f"Score: {self.score}, lives: {self.lives}")
