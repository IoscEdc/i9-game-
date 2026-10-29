import sys, time, threading, pygame
from game import SnakeGame, DIRECTIONS
from agent import SnakeLLMAgent, AgentResult

BG, CARD, CARD_BD = (236, 247, 234), (255, 255, 255), (195, 222, 185)
GRASS_A, GRASS_B, GRASS_BD = (170, 215, 81), (162, 209, 73), (120, 175, 55)
SNAKE_BODY, SNAKE_OUTLINE, SNAKE_HEAD = (80, 185, 105), (42, 118, 58), (88, 195, 115)
APPLE, TEXT, MUTED = (235, 65, 65), (45, 65, 45), (110, 140, 110)

W, H, GRID_PX, OFF_X, OFF_Y = 600, 740, 480, 60, 80
CELL = GRID_PX // 8


def txt(surf, s, x, y, sz=14, bold=True, col=TEXT, center=False):
    f = pygame.font.SysFont("dejavusans", sz, bold=bold)
    r = f.render(str(s), True, col)
    rc = r.get_rect(center=(x, y)) if center else r.get_rect(topleft=(x, y))
    surf.blit(r, rc)
    return rc


class SnakeApp:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Doodle Snake AI")
        self.screen, self.clock = pygame.display.set_mode((W, H)), pygame.time.Clock()
        self.game, self.agent = SnakeGame(size=8), SnakeLLMAgent()
        self.state, self.paused, self.thinking = "HOME", False, False
        self.last_step, self.delay = time.time(), 0.32
        self.res = AgentResult(self.game.current_direction, "Ready.", "LIVE_API", 0, self.agent.model_name, self.agent.get_masked_key())
        self.btn_play, self.btn_pause, self.btn_again, self.btn_home = [pygame.Rect(0, 0, 0, 0)] * 4

    def ask_ai(self):
        if self.thinking or self.game.game_over:
            return
        self.thinking = True

        def run():
            try:
                r = self.agent.choose_move(self.game)
                self.res = r
                if r.status == "ERROR" or not r.direction:
                    self.paused = True
                elif not self.game.step(r.direction):
                    self.state = "OVER"
            finally:
                self.thinking, self.last_step = False, time.time()

        threading.Thread(target=run, daemon=True).start()

    def draw_hud(self):
        rc = pygame.Rect(OFF_X, 12, GRID_PX, 56)
        pygame.draw.rect(self.screen, CARD, rc, border_radius=12)
        pygame.draw.rect(self.screen, CARD_BD, rc, width=2, border_radius=12)
        txt(self.screen, f"APPLES: {self.game.score:02d}", rc.x + 16, rc.y + 12, 13, True, APPLE)
        txt(self.screen, f"LENGTH: {len(self.game.snake):02d}", rc.x + 120, rc.y + 12, 13, True, SNAKE_BODY)
        txt(self.screen, f"TOKENS: {self.res.total_tokens}", rc.x + 16, rc.y + 32, 11, False, MUTED)
        txt(self.screen, f"TOTAL: {self.res.cumulative_tokens}", rc.x + 120, rc.y + 32, 11, False, MUTED)
        self.btn_pause = pygame.Rect(rc.right - 95, rc.y + 10, 85, 36)
        col = (235, 155, 30) if self.paused else (75, 180, 85)
        pygame.draw.rect(self.screen, (244, 250, 242), self.btn_pause, border_radius=8)
        pygame.draw.rect(self.screen, col, self.btn_pause, width=2, border_radius=8)
        txt(self.screen, "RESUME" if self.paused else "PAUSE", self.btn_pause.centerx, self.btn_pause.centery, 11, True, col, True)

    def draw_board(self):
        pygame.draw.rect(self.screen, GRASS_BD, pygame.Rect(OFF_X, OFF_Y, GRID_PX, GRID_PX).inflate(6, 6), border_radius=12)
        for r in range(8):
            for c in range(8):
                pygame.draw.rect(self.screen, GRASS_A if (r + c) % 2 == 0 else GRASS_B, (OFF_X + c * CELL, OFF_Y + r * CELL, CELL, CELL))
        fx, fy = OFF_X + self.game.food[1] * CELL + CELL // 2, OFF_Y + self.game.food[0] * CELL + CELL // 2
        pygame.draw.circle(self.screen, APPLE, (fx, fy), CELL // 3)
        pygame.draw.circle(self.screen, (255, 170, 180), (fx - 4, fy - 4), 3)
        pygame.draw.rect(self.screen, (130, 85, 45), (fx - 1, fy - CELL // 3 - 4, 3, 5))
        body = self.game.snake
        for i in range(len(body) - 1, 0, -1):
            p1 = (OFF_X + body[i][1] * CELL + CELL // 2, OFF_Y + body[i][0] * CELL + CELL // 2)
            p2 = (OFF_X + body[i - 1][1] * CELL + CELL // 2, OFF_Y + body[i - 1][0] * CELL + CELL // 2)
            rad = max(6, int(CELL * 0.32 * (0.6 + 0.4 * (1 - i / len(body)))))
            pygame.draw.circle(self.screen, SNAKE_OUTLINE, p1, rad + 2)
            pygame.draw.line(self.screen, SNAKE_OUTLINE, p1, p2, (rad + 2) * 2)
            pygame.draw.circle(self.screen, SNAKE_BODY, p1, rad)
            pygame.draw.line(self.screen, SNAKE_BODY, p1, p2, rad * 2)
        hx, hy = OFF_X + body[0][1] * CELL + CELL // 2, OFF_Y + body[0][0] * CELL + CELL // 2
        pygame.draw.circle(self.screen, SNAKE_OUTLINE, (hx, hy), CELL // 2 - 2)
        pygame.draw.circle(self.screen, SNAKE_HEAD, (hx, hy), CELL // 2 - 4)
        dr, dc = DIRECTIONS.get(self.game.current_direction, (0, 1))
        for sx, sy in ((-dc * 7 + dr * 5, -dr * 7 + dc * 5), (dc * 7 + dr * 5, dr * 7 + dc * 5)):
            ex, ey = hx + int(sx), hy + int(sy)
            pygame.draw.circle(self.screen, (255, 255, 255), (ex, ey), 5)
            pygame.draw.circle(self.screen, TEXT, (ex + dc * 2, ey + dr * 2), 2)

    def draw_thought(self):
        rc = pygame.Rect(OFF_X, OFF_Y + GRID_PX + 12, GRID_PX, 95)
        pygame.draw.rect(self.screen, CARD, rc, border_radius=12)
        pygame.draw.rect(self.screen, CARD_BD, rc, width=2, border_radius=12)
        txt(self.screen, "AI THOUGHT", rc.x + 14, rc.y + 10, 12, True, SNAKE_BODY)
        txt(self.screen, self.res.direction or "PAUSED", rc.right - 70, rc.y + 10, 12, True, TEXT)
        msg = f"[ERROR] {self.res.thought}" if self.res.status == "ERROR" else (
            "Game paused. Click RESUME or press SPACE." if self.paused else ("Thinking..." if self.thinking else f'"{self.res.thought}"')
        )
        col = (225, 75, 65) if self.res.status == "ERROR" else (MUTED if self.thinking else TEXT)
        f, line, ly = pygame.font.SysFont("dejavusans", 12), "", rc.y + 34
        for w in msg.split():
            if f.size(line + w)[0] < rc.width - 28:
                line += w + " "
            else:
                txt(self.screen, line, rc.x + 14, ly, 12, False, col)
                line, ly = w + " ", ly + 18
        if line:
            txt(self.screen, line, rc.x + 14, ly, 12, False, col)
        txt(self.screen, "SPACE: Pause  |  R: Restart  |  Q: Quit", rc.centerx, rc.bottom - 12, 10, False, MUTED, True)

    def draw_home(self):
        self.screen.fill(BG)
        card = pygame.Rect(W // 2 - 220, H // 2 - 210, 440, 420)
        pygame.draw.rect(self.screen, CARD, card, border_radius=20)
        pygame.draw.rect(self.screen, CARD_BD, card, width=2, border_radius=20)
        txt(self.screen, "DOODLE SNAKE AI", card.centerx, card.y + 35, 22, True, TEXT, True)
        txt(self.screen, "Grassland Edition • OpenRouter", card.centerx, card.y + 70, 12, False, MUTED, True)
        txt(self.screen, f"Model: {self.agent.model_name.split('/')[-1]}", card.centerx, card.y + 100, 11, True, (75, 180, 85), True)
        info = pygame.Rect(card.x + 30, card.y + 130, card.width - 60, 115)
        pygame.draw.rect(self.screen, (244, 250, 242), info, border_radius=12)
        bullets = ["- Full 8x8 Board state sent to LLM", "- Real-time wall & self collision safety", "- 100% Autonomous LLM reasoning", "- Continuous play until game over"]
        for idx, b in enumerate(bullets):
            txt(self.screen, b, info.x + 15, info.y + 12 + idx * 24, 11, False, MUTED)
        self.btn_play = pygame.Rect(card.centerx - 45, card.y + 275, 90, 90)
        pygame.draw.circle(self.screen, (115, 205, 85) if self.btn_play.collidepoint(pygame.mouse.get_pos()) else (100, 195, 75), self.btn_play.center, 44)
        pygame.draw.polygon(self.screen, (255, 255, 255), [(self.btn_play.centerx - 12, self.btn_play.centery - 20), (self.btn_play.centerx + 18, self.btn_play.centery), (self.btn_play.centerx - 12, self.btn_play.centery + 20)])
        txt(self.screen, "START GAME", card.centerx, card.y + 380, 13, True, (60, 140, 45), True)

    def draw_over(self):
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((40, 60, 40, 130))
        self.screen.blit(ov, (0, 0))
        box = pygame.Rect(W // 2 - 180, H // 2 - 130, 360, 260)
        pygame.draw.rect(self.screen, CARD, box, border_radius=16)
        pygame.draw.rect(self.screen, CARD_BD, box, width=2, border_radius=16)
        txt(self.screen, "GAME OVER", box.centerx, box.y + 25, 20, True, TEXT, True)
        txt(self.screen, f"Apples: {self.game.score}   Length: {len(self.game.snake)}   Tokens: {self.res.cumulative_tokens}", box.centerx, box.y + 70, 12, True, TEXT, True)
        self.btn_again = pygame.Rect(box.x + 30, box.y + 120, 140, 42)
        pygame.draw.rect(self.screen, (100, 195, 75), self.btn_again, border_radius=10)
        txt(self.screen, "PLAY AGAIN", self.btn_again.centerx, self.btn_again.centery, 12, True, (255, 255, 255), True)
        self.btn_home = pygame.Rect(box.right - 170, box.y + 120, 140, 42)
        pygame.draw.rect(self.screen, (235, 245, 235), self.btn_home, border_radius=10)
        pygame.draw.rect(self.screen, CARD_BD, self.btn_home, width=2, border_radius=10)
        txt(self.screen, "HOME", self.btn_home.centerx, self.btn_home.centery, 12, True, TEXT, True)
        txt(self.screen, "Click Play Again or press R to restart", box.centerx, box.bottom - 20, 11, False, MUTED, True)

    def run(self):
        while True:
            self.clock.tick(60)
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_q):
                    pygame.quit()
                    sys.exit(0)
                elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    if self.state == "HOME" and self.btn_play.collidepoint(ev.pos):
                        self.state, self.paused = "PLAY", False
                        self.game.reset()
                    elif self.state == "PLAY" and self.btn_pause.collidepoint(ev.pos):
                        self.paused = not self.paused
                    elif self.state == "OVER":
                        if self.btn_again.collidepoint(ev.pos):
                            self.state, self.paused = "PLAY", False
                            self.game.reset()
                        elif self.btn_home.collidepoint(ev.pos):
                            self.state = "HOME"
                elif ev.type == pygame.KEYDOWN:
                    if ev.key in (pygame.K_SPACE, pygame.K_RETURN):
                        if self.state == "HOME":
                            self.state, self.paused = "PLAY", False
                            self.game.reset()
                        elif self.state == "PLAY":
                            self.paused = not self.paused
                    elif ev.key == pygame.K_r:
                        self.state, self.paused = "PLAY", False
                        self.game.reset()
                    elif ev.key == pygame.K_h:
                        self.state = "HOME"

            if self.state == "PLAY" and not self.paused and not self.game.game_over:
                if not self.thinking and time.time() - self.last_step >= self.delay:
                    self.ask_ai()

            if self.state == "HOME":
                self.draw_home()
            else:
                self.screen.fill(BG)
                self.draw_hud()
                self.draw_board()
                self.draw_thought()
                if self.state == "OVER" or self.game.game_over:
                    self.draw_over()
            pygame.display.flip()


if __name__ == "__main__":
    SnakeApp().run()
