import sys
import pygame

FONT = None
BIG_FONT = None


def open_window(title, width, height):
    global FONT, BIG_FONT
    pygame.init()
    pygame.display.set_caption(title)
    FONT = pygame.font.SysFont("consolas,menlo,monospace", 18)
    BIG_FONT = pygame.font.SysFont("consolas,menlo,monospace", 28, bold=True)
    return pygame.display.set_mode((width, height))


def pause(seconds):
    end = pygame.time.get_ticks() + int(seconds * 1000)
    while pygame.time.get_ticks() < end:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
        pygame.time.wait(50)


def draw_grid_lines(screen, size, cell, x, y, color):
    for i in range(size + 1):
        pygame.draw.line(screen, color, (x + i * cell, y), (x + i * cell, y + size * cell), 2)
        pygame.draw.line(screen, color, (x, y + i * cell), (x + size * cell, y + i * cell), 2)


def wrap_text(text, width):
    lines = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split(" "):
            test = (line + " " + word).strip()
            if FONT.size(test)[0] <= width:
                line = test
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


def draw_panel(screen, x, width, title, info_lines, reply, title_color, info_color, reply_color):
    y = 15
    screen.blit(BIG_FONT.render(title, True, title_color), (x, y))
    y += 45

    for line in info_lines:
        screen.blit(FONT.render(line, True, info_color), (x, y))
        y += 24

    y += 12
    screen.blit(FONT.render("LLM answer:", True, title_color), (x, y))
    y += 28

    room = (screen.get_height() - y - 10) // 22
    for line in wrap_text(reply, width)[-room:]:
        screen.blit(FONT.render(line, True, reply_color), (x, y))
        y += 22
