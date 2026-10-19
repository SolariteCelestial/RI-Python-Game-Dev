import os
import sys
import math
import random
from collections import deque

import pygame

# ── Headless / Codespaces environment fixes (same as game.py) ────────────────
if sys.platform.startswith("linux"):
    if not os.environ.get("DISPLAY"):
        os.environ["DISPLAY"] = ":99"
    if not os.environ.get("XDG_RUNTIME_DIR"):
        os.environ["XDG_RUNTIME_DIR"] = "/tmp/runtime-vscode"
        os.makedirs("/tmp/runtime-vscode", exist_ok=True)
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

# ─────────────────────────────────────────
# INITIALISE pygame
# ─────────────────────────────────────────
pygame.init()

SCREEN_WIDTH = 640
SCREEN_HEIGHT = 640
TITLE = "Cube Knight: Card Maze"

screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption(TITLE)
clock = pygame.time.Clock()
FPS = 60

FONT_S = pygame.font.Font(None, 20)
FONT_M = pygame.font.Font(None, 26)
FONT_L = pygame.font.Font(None, 64)
FONT_XL = pygame.font.Font(None, 48)

# ─────────────────────────────────────────
# COLOURS (original palette + a few extras)
# ─────────────────────────────────────────
BLACK = (15, 15, 20)
WHITE = (240, 240, 240)
GRAY = (40, 40, 40)
RED = (220, 50, 50)
ORANGE = (255, 150, 50)
CYAN = (150, 255, 255)
YELLOW = (255, 255, 100)
GREEN = (90, 210, 120)
BLUE = (90, 140, 255)
PURPLE = (200, 90, 230)
DARKRED = (150, 30, 40)
WALL = (58, 58, 72)
FLOOR = (20, 20, 27)
PANEL = (28, 28, 36)

# ─────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────
TILE = 32
COLS, ROWS = 19, 13                      # must both be odd
MAZE_X = (SCREEN_WIDTH - COLS * TILE) // 2
MAZE_Y = 40
MAZE_RECT = pygame.Rect(MAZE_X, MAZE_Y, COLS * TILE, ROWS * TILE)

HAND_SIZE = 5
START_HP = 10
ATTACK_DMG = 2
CARD_W, CARD_H, CARD_Y = 112, 124, 496

DIRS = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}
KEY_DIR = {
    pygame.K_UP: "UP", pygame.K_w: "UP",
    pygame.K_DOWN: "DOWN", pygame.K_s: "DOWN",
    pygame.K_LEFT: "LEFT", pygame.K_a: "LEFT",
    pygame.K_RIGHT: "RIGHT", pygame.K_d: "RIGHT",
}

ALL_CARDS = [(k, n) for k in ("move", "attack") for n in range(1, 6)]
START_DECK = [("move", 1), ("move", 1), ("move", 2), ("move", 2), ("move", 3), ("move", 4),
              ("attack", 1), ("attack", 1), ("attack", 2), ("attack", 2), ("attack", 3), ("attack", 4)]

# Enemy roster. A new type unlocks each round, in this order.
ENEMY_TYPES = {
    "walker": dict(name="Walker", hp=2, color=RED,     glyph="W", inset=3),
    "bat":    dict(name="Bat",    hp=2, color=PURPLE,  glyph="B", inset=7),
    "archer": dict(name="Archer", hp=2, color=GREEN,   glyph="A", inset=3),
    "rook":   dict(name="Rook",   hp=3, color=BLUE,    glyph="R", inset=3),
    "brute":  dict(name="Brute",  hp=5, color=DARKRED, glyph="H", inset=1),
}
UNLOCK_ORDER = ["walker", "bat", "archer", "rook", "brute"]


# ─────────────────────────────────────────
# MAZE GENERATION (recursive backtracker + a few loops)
# ─────────────────────────────────────────
def make_maze():
    g = [[1] * COLS for _ in range(ROWS)]
    g[1][1] = 0
    stack = [(1, 1)]
    while stack:
        x, y = stack[-1]
        opts = []
        for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2)):
            nx, ny = x + dx, y + dy
            if 1 <= nx < COLS - 1 and 1 <= ny < ROWS - 1 and g[ny][nx] == 1:
                opts.append((nx, ny, dx, dy))
        if opts:
            nx, ny, dx, dy = random.choice(opts)
            g[y + dy // 2][x + dx // 2] = 0
            g[ny][nx] = 0
            stack.append((nx, ny))
        else:
            stack.pop()
    # Knock out a few wall segments so the maze has loops (less dead-endy)
    for y in range(1, ROWS - 1):
        for x in range(1, COLS - 1):
            if g[y][x] == 1 and (x + y) % 2 == 1 and random.random() < 0.12:
                if (g[y][x - 1] == 0 and g[y][x + 1] == 0) or (g[y - 1][x] == 0 and g[y + 1][x] == 0):
                    g[y][x] = 0
    return g


def pick_kinds(rnd):
    """Round N spawns N enemies. The newest type is guaranteed to show up."""
    pool = UNLOCK_ORDER[:min(rnd, len(UNLOCK_ORDER))]
    kinds = []
    if 1 < rnd <= len(UNLOCK_ORDER):
        kinds.append(UNLOCK_ORDER[rnd - 1])
    while len(kinds) < rnd:
        kinds.append(random.choice(pool))
    return kinds


# ─────────────────────────────────────────
# CLASSES
# ─────────────────────────────────────────
class Enemy:
    def __init__(self, kind, x, y):
        t = ENEMY_TYPES[kind]
        self.kind = kind
        self.x, self.y = x, y
        self.hp = self.max_hp = t["hp"]
        self.windup = None      # Brute: tile it is about to slam
        self.tick = 0


class Spark:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.radius = 6
        self.life = 10

    def update(self):
        self.radius += 2
        self.life -= 1

    def draw(self, surface):
        if self.life > 0:
            pygame.draw.circle(surface, YELLOW, (int(self.x), int(self.y)), int(self.radius), 2)


def draw_text(surf, text, font, color, center=None, topleft=None):
    img = font.render(text, True, color)
    r = img.get_rect()
    if center:
        r.center = center
    elif topleft:
        r.topleft = topleft
    surf.blit(img, r)


def sign(v):
    return (v > 0) - (v < 0)


# ─────────────────────────────────────────
# GAME
# ─────────────────────────────────────────
class Game:
    def __init__(self):
        self.show_help = True
        self.reset()

    # ---------- setup ----------
    def reset(self):
        self.max_hp = START_HP
        self.hp = START_HP
        self.deck = list(START_DECK)
        self.round = 1
        self.state = "play"          # play / reward / dead
        self.start_round()
        self.say("Pick a card, then a direction.")

    def start_round(self):
        self.grid = make_maze()
        floors = [(x, y) for y in range(ROWS) for x in range(COLS) if self.grid[y][x] == 0]
        self.px, self.py = random.choice(floors)
        self.facing = "RIGHT"

        dist = self.bfs((self.px, self.py))
        kinds = pick_kinds(self.round)
        far = [p for p, d in dist.items() if d >= 8]
        if len(far) < len(kinds):
            far = [p for p, d in dist.items() if d >= 4]
        if len(far) < len(kinds):
            far = [p for p in dist if p != (self.px, self.py)]
        random.shuffle(far)
        kinds = kinds[:len(far)]
        self.enemies = [Enemy(k, *far[i]) for i, k in enumerate(kinds)]

        self.draw_pile = self.deck[:]
        random.shuffle(self.draw_pile)
        self.discard = []
        self.hand = []
        for _ in range(HAND_SIZE):
            self.draw_card()

        self.selected = None
        self.phase = "player"        # player / enemy / clear
        self.timer = 0
        self.beams, self.sparks, self.floats, self.flashes = [], [], [], []
        self.shake = 0
        self.hit_timer = 0
        self.log = []
        self.options = []
        self.say(f"Round {self.round} - kill {len(self.enemies)}!")

    def draw_card(self):
        if not self.draw_pile:
            self.draw_pile = self.discard
            self.discard = []
            random.shuffle(self.draw_pile)
        if self.draw_pile:
            self.hand.append(self.draw_pile.pop())

    # ---------- helpers ----------
    def say(self, text):
        self.msg = text
        self.pmsg = text

    def is_wall(self, x, y):
        return not (0 <= x < COLS and 0 <= y < ROWS) or self.grid[y][x] == 1

    def enemy_at(self, x, y):
        for e in self.enemies:
            if e.x == x and e.y == y:
                return e
        return None

    def free(self, x, y):
        return (not self.is_wall(x, y) and not self.enemy_at(x, y)
                and (x, y) != (self.px, self.py))

    def bfs(self, start):
        d = {start: 0}
        q = deque([start])
        while q:
            x, y = q.popleft()
            for dx, dy in DIRS.values():
                n = (x + dx, y + dy)
                if n not in d and not self.is_wall(*n):
                    d[n] = d[(x, y)] + 1
                    q.append(n)
        return d

    def center(self, x, y):
        return (MAZE_X + x * TILE + TILE // 2, MAZE_Y + y * TILE + TILE // 2)

    def beam(self, a, b, color, life=10, width=3):
        self.beams.append(dict(a=self.center(*a), b=self.center(*b), color=color, life=life, width=width))

    def spark(self, x, y):
        self.sparks.append(Spark(*self.center(x, y)))

    def ftext(self, x, y, text, color):
        cx, cy = self.center(x, y)
        self.floats.append(dict(x=cx, y=cy - 10, text=text, color=color, life=40))

    def line_clear(self, ax, ay, bx, by):
        dx, dy = sign(bx - ax), sign(by - ay)
        x, y = ax + dx, ay + dy
        while (x, y) != (bx, by):
            if self.is_wall(x, y) or self.enemy_at(x, y):
                return False
            x += dx
            y += dy
        return True

    def adjacent(self, e):
        return abs(e.x - self.px) + abs(e.y - self.py) == 1

    def ray(self, d, n, kind):
        """Tiles a card of distance n would cover in direction d."""
        dx, dy = DIRS[d]
        tiles, target = [], None
        x, y = self.px, self.py
        for _ in range(n):
            x += dx
            y += dy
            if self.is_wall(x, y):
                break
            e = self.enemy_at(x, y)
            if e:
                if kind == "attack":
                    tiles.append((x, y))
                    target = e
                break
            tiles.append((x, y))
        return tiles, target

    # ---------- player turn ----------
    def play(self, d):
        kind, n = self.hand[self.selected]
        tiles, target = self.ray(d, n, kind)
        self.facing = d
        if kind == "move":
            if not tiles:
                self.say("Blocked!")
                return
            old = (self.px, self.py)
            self.px, self.py = tiles[-1]
            self.beam(old, (self.px, self.py), (110, 110, 130), 8)
            self.say(f"Moved {len(tiles)}.")
        else:
            end = tiles[-1] if tiles else (self.px, self.py)
            self.beam((self.px, self.py), end, CYAN, 10, 4)
            if target:
                target.hp -= ATTACK_DMG
                self.spark(target.x, target.y)
                self.ftext(target.x, target.y, f"-{ATTACK_DMG}", YELLOW)
                name = ENEMY_TYPES[target.kind]["name"]
                if target.hp <= 0:
                    self.enemies.remove(target)
                    self.say(f"Killed the {name}!")
                else:
                    self.say(f"Hit the {name}.")
            else:
                self.say("Swing and a miss.")
        self.discard.append(self.hand.pop(self.selected))
        self.draw_card()
        self.selected = None
        self.log = []
        if not self.enemies:
            self.phase = "clear"
            self.timer = 35
            self.say("Round cleared!")
        else:
            self.phase = "enemy"
            self.timer = 22

    # ---------- enemy turn ----------
    def hurt(self, dmg, who):
        self.hp -= dmg
        self.hit_timer = 24
        self.shake = 10
        self.spark(self.px, self.py)
        self.ftext(self.px, self.py, f"-{dmg}", RED)
        self.log.append(f"{who} -{dmg}!")

    def step_toward(self, e, dist):
        cur = dist[(e.x, e.y)]
        opts = []
        for dx, dy in DIRS.values():
            n = (e.x + dx, e.y + dy)
            if n in dist and dist[n] < cur and self.free(*n):
                opts.append(n)
        if opts:
            e.x, e.y = random.choice(opts)
            return True
        return False

    def random_step(self, e):
        opts = [(e.x + dx, e.y + dy) for dx, dy in DIRS.values() if self.free(e.x + dx, e.y + dy)]
        if opts:
            e.x, e.y = random.choice(opts)

    def retreat(self, e, dist):
        cur = dist[(e.x, e.y)]
        opts = []
        for dx, dy in DIRS.values():
            n = (e.x + dx, e.y + dy)
            if n in dist and dist[n] > cur and self.free(*n):
                opts.append(n)
        if opts:
            e.x, e.y = random.choice(opts)
            return True
        return False

    def enemy_act(self, e, dist):
        k = e.kind
        d = abs(e.x - self.px) + abs(e.y - self.py)
        aligned = (e.x == self.px or e.y == self.py)
        name = ENEMY_TYPES[k]["name"]

        if k == "walker":                    # steady 1 tile/turn, bites when adjacent
            if d == 1:
                self.hurt(1, name)
            else:
                self.step_toward(e, dist)

        elif k == "bat":                     # fast (2 tiles) but flaky
            for _ in range(2):
                if self.adjacent(e):
                    break
                if random.random() < 0.25:
                    self.random_step(e)
                else:
                    self.step_toward(e, dist)
            if self.adjacent(e):
                self.hurt(1, name)

        elif k == "archer":                  # shoots down straight lines, kites away
            if aligned and 2 <= d <= 5 and self.line_clear(e.x, e.y, self.px, self.py):
                self.beam((e.x, e.y), (self.px, self.py), GREEN, 12, 3)
                self.hurt(1, name)
            elif d == 1:
                if not self.retreat(e, dist):
                    self.hurt(1, name)
            else:
                self.step_toward(e, dist)

        elif k == "rook":                    # charges along straight lines
            if d == 1:
                self.hurt(2, name)
            elif aligned and d <= 6 and self.line_clear(e.x, e.y, self.px, self.py):
                dx, dy = sign(self.px - e.x), sign(self.py - e.y)
                start = (e.x, e.y)
                while self.free(e.x + dx, e.y + dy):
                    e.x += dx
                    e.y += dy
                self.beam(start, (e.x, e.y), BLUE, 10, 5)
                if self.adjacent(e):
                    self.hurt(2, name + " charge")
            else:
                self.step_toward(e, dist)

        elif k == "brute":                   # slow, telegraphs a slam on a tile
            if e.windup:
                tx, ty = e.windup
                e.windup = None
                self.flashes.append(dict(x=tx, y=ty, color=ORANGE, life=14))
                if (self.px, self.py) == (tx, ty):
                    self.hurt(3, name + " slam")
                else:
                    self.log.append("Brute missed!")
            elif d == 1:
                e.windup = (self.px, self.py)
                self.log.append("Brute winds up...")
            else:
                e.tick += 1
                if e.tick % 2 == 1:
                    self.step_toward(e, dist)

    def run_enemies(self):
        dist = self.bfs((self.px, self.py))
        for e in list(self.enemies):
            self.enemy_act(e, dist)
            if self.hp <= 0:
                break
        if self.hp <= 0:
            self.hp = 0
            self.state = "dead"
            self.msg = "You died."
        else:
            self.phase = "player"
            self.msg = self.pmsg + ("   " + " ".join(self.log) if self.log else "")

    # ---------- reward ----------
    def begin_reward(self):
        self.max_hp += 1
        self.hp += 1
        self.options = [("heal", None)] + [("card", c) for c in random.sample(ALL_CARDS, 3)]
        self.state = "reward"

    def choose(self, i):
        kind, val = self.options[i]
        if kind == "heal":
            self.hp = min(self.max_hp, self.hp + 3)
        else:
            self.deck.append(val)
        self.round += 1
        self.state = "play"
        self.start_round()

    # ---------- input ----------
    def card_hit(self, i):
        return pygame.Rect(20 + i * (CARD_W + 10), CARD_Y - 12, CARD_W, CARD_H + 12)

    def reward_rect(self, i):
        return pygame.Rect(56 + i * 136, 240, 120, 150)

    def mouse_dir(self, pos):
        if not MAZE_RECT.collidepoint(pos):
            return None
        cx, cy = self.center(self.px, self.py)
        dx, dy = pos[0] - cx, pos[1] - cy
        if abs(dx) < TILE // 2 and abs(dy) < TILE // 2:
            return None
        if abs(dx) > abs(dy):
            return "RIGHT" if dx > 0 else "LEFT"
        return "DOWN" if dy > 0 else "UP"

    def handle(self, ev):
        if ev.type == pygame.QUIT:
            return False
        if self.show_help:
            if ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                self.show_help = False
            return True
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_h:
                self.show_help = True
                return True
            if ev.key == pygame.K_ESCAPE:
                if self.selected is not None:
                    self.selected = None
                    return True
                return False
            if self.state == "dead" and ev.key == pygame.K_r:
                self.reset()
                return True

        if self.state == "reward":
            if ev.type == pygame.KEYDOWN and pygame.K_1 <= ev.key <= pygame.K_4:
                self.choose(ev.key - pygame.K_1)
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                for i in range(len(self.options)):
                    if self.reward_rect(i).collidepoint(ev.pos):
                        self.choose(i)
                        break
        elif self.state == "play" and self.phase == "player":
            if ev.type == pygame.KEYDOWN:
                if pygame.K_1 <= ev.key <= pygame.K_5:
                    i = ev.key - pygame.K_1
                    if i < len(self.hand):
                        self.selected = None if self.selected == i else i
                elif ev.key in KEY_DIR and self.selected is not None:
                    self.play(KEY_DIR[ev.key])
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                for i in range(len(self.hand)):
                    if self.card_hit(i).collidepoint(ev.pos):
                        self.selected = None if self.selected == i else i
                        return True
                if self.selected is not None:
                    d = self.mouse_dir(ev.pos)
                    if d:
                        self.play(d)
        return True

    # ---------- update ----------
    def update(self):
        for s in self.sparks[:]:
            s.update()
            if s.life <= 0:
                self.sparks.remove(s)
        for b in self.beams[:]:
            b["life"] -= 1
            if b["life"] <= 0:
                self.beams.remove(b)
        for f in self.flashes[:]:
            f["life"] -= 1
            if f["life"] <= 0:
                self.flashes.remove(f)
        for f in self.floats[:]:
            f["life"] -= 1
            f["y"] -= 0.6
            if f["life"] <= 0:
                self.floats.remove(f)
        if self.hit_timer > 0:
            self.hit_timer -= 1

        if self.state != "play":
            return
        if self.phase == "enemy":
            self.timer -= 1
            if self.timer <= 0:
                self.run_enemies()
        elif self.phase == "clear":
            self.timer -= 1
            if self.timer <= 0:
                self.begin_reward()

    # ---------- drawing ----------
    def tile_rect(self, x, y):
        return pygame.Rect(MAZE_X + x * TILE, MAZE_Y + y * TILE, TILE, TILE)

    def tint(self, surf, tiles, color, alpha):
        ov = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
        ov.fill((*color, alpha))
        for (x, y) in tiles:
            surf.blit(ov, self.tile_rect(x, y).topleft)

    def draw_card_face(self, surf, rect, card, key, selected=False):
        kind, n = card
        col = CYAN if kind == "move" else ORANGE
        pygame.draw.rect(surf, PANEL, rect, border_radius=6)
        pygame.draw.rect(surf, YELLOW if selected else col, rect, 3 if selected else 2, border_radius=6)
        draw_text(surf, str(key), FONT_S, GRAY if not selected else YELLOW, topleft=(rect.x + 8, rect.y + 6))
        draw_text(surf, kind.upper(), FONT_M, col, center=(rect.centerx, rect.y + 24))
        draw_text(surf, str(n), FONT_L, WHITE, center=(rect.centerx, rect.centery + 2))
        sub = "tiles" if kind == "move" else f"range - {ATTACK_DMG} dmg"
        draw_text(surf, sub, FONT_S, (150, 150, 165), center=(rect.centerx, rect.bottom - 14))

    def draw_help(self, surf):
        ov = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 215))
        surf.blit(ov, (0, 0))
        draw_text(surf, "CARD MAZE", FONT_XL, WHITE, center=(SCREEN_WIDTH // 2, 50))
        lines = [
            ("Pick a card (1-5 or click) - it sets the DISTANCE.", WHITE),
            ("Pick a direction (arrows / WASD, or click the maze).", WHITE),
            ("One card per turn, then every enemy acts.", WHITE),
            ("Kill every enemy to clear the round. Each round adds one.", WHITE),
            ("", WHITE),
            ("Walker  - walks 1 tile, bites when adjacent", RED),
            ("Bat     - moves 2 tiles, a bit erratic", PURPLE),
            ("Archer  - shoots down open lines, backs away", GREEN),
            ("Rook    - charges along open lines for 2 dmg", BLUE),
            ("Brute   - slow. Orange tile = slam next turn. MOVE!", ORANGE),
            ("", WHITE),
            ("Thin lines show Archer/Rook lanes aimed at you.", (170, 170, 185)),
            ("After each round: +1 max HP, then heal 3 OR take a card.", (170, 170, 185)),
            ("", WHITE),
            ("H = help    ESC = cancel / quit    R = restart (when dead)", (170, 170, 185)),
            ("Press any key to start", YELLOW),
        ]
        y = 100
        for text, col in lines:
            draw_text(surf, text, FONT_M, col, center=(SCREEN_WIDTH // 2, y))
            y += 28

    def draw(self, surf):
        surf.fill(BLACK)

        # ---- maze ----
        for y in range(ROWS):
            for x in range(COLS):
                r = self.tile_rect(x, y)
                if self.grid[y][x]:
                    pygame.draw.rect(surf, WALL, r)
                    pygame.draw.rect(surf, (40, 40, 52), r, 1)
                else:
                    pygame.draw.rect(surf, FLOOR, r)
                    pygame.draw.rect(surf, GRAY, r, 1)

        # ---- enemy intent: lanes & slam tiles ----
        for e in self.enemies:
            aligned = (e.x == self.px or e.y == self.py)
            d = abs(e.x - self.px) + abs(e.y - self.py)
            if e.kind == "archer" and aligned and 2 <= d <= 5 and self.line_clear(e.x, e.y, self.px, self.py):
                pygame.draw.line(surf, GREEN, self.center(e.x, e.y), self.center(self.px, self.py), 1)
            if e.kind == "rook" and aligned and 2 <= d <= 6 and self.line_clear(e.x, e.y, self.px, self.py):
                pygame.draw.line(surf, BLUE, self.center(e.x, e.y), self.center(self.px, self.py), 1)
            if e.windup:
                self.tint(surf, [e.windup], ORANGE, 120)
                pygame.draw.rect(surf, ORANGE, self.tile_rect(*e.windup), 2)
        for f in self.flashes:
            self.tint(surf, [(f["x"], f["y"])], f["color"], 200)

        # ---- card previews ----
        if self.selected is not None and self.state == "play" and self.phase == "player":
            kind, n = self.hand[self.selected]
            hover = self.mouse_dir(pygame.mouse.get_pos())
            for d in DIRS:
                tiles, target = self.ray(d, n, kind)
                col = CYAN if kind == "move" else YELLOW
                self.tint(surf, tiles, col, 95 if d == hover else 45)
                if tiles and kind == "move":
                    pygame.draw.rect(surf, col, self.tile_rect(*tiles[-1]), 2)
                if target:
                    pygame.draw.rect(surf, RED, self.tile_rect(target.x, target.y), 3)

        # ---- enemies ----
        for e in self.enemies:
            t = ENEMY_TYPES[e.kind]
            r = self.tile_rect(e.x, e.y).inflate(-2 * t["inset"], -2 * t["inset"])
            color = ORANGE if e.windup else t["color"]
            pygame.draw.rect(surf, color, r)
            if e.kind == "brute":
                pygame.draw.rect(surf, BLACK, r, 2)
            draw_text(surf, t["glyph"], FONT_S, BLACK, center=r.center)
            bar = pygame.Rect(r.x, r.y - 5, r.w, 3)
            pygame.draw.rect(surf, GRAY, bar)
            pygame.draw.rect(surf, WHITE, (bar.x, bar.y, int(bar.w * e.hp / e.max_hp), bar.h))

        # ---- player ----
        if not (self.hit_timer > 0 and (self.hit_timer // 4) % 2 == 0):
            pr = self.tile_rect(self.px, self.py).inflate(-6, -6)
            pygame.draw.rect(surf, WHITE, pr)
            ex, ey = pr.centerx, pr.centery
            if self.facing == "RIGHT":
                ex += 6
            elif self.facing == "LEFT":
                ex -= 10
            elif self.facing == "UP":
                ey -= 10
            else:
                ey += 6
            pygame.draw.rect(surf, BLACK, (ex - 2, ey - 2, 4, 4))

        # ---- effects ----
        for b in self.beams:
            pygame.draw.line(surf, b["color"], b["a"], b["b"], b["width"])
        for s in self.sparks:
            s.draw(surf)
        for f in self.floats:
            draw_text(surf, f["text"], FONT_M, f["color"], center=(int(f["x"]), int(f["y"])))

        # ---- HUD ----
        pygame.draw.rect(surf, GRAY, (10, 12, 200, 18))
        if self.max_hp > 0:
            pygame.draw.rect(surf, RED, (10, 12, int(200 * max(self.hp, 0) / self.max_hp), 18))
        draw_text(surf, f"HP {max(self.hp, 0)}/{self.max_hp}", FONT_M, WHITE, center=(110, 21))
        draw_text(surf, f"Round {self.round}    Enemies {len(self.enemies)}", FONT_M, WHITE, topleft=(440, 14))

        # ---- message bar ----
        draw_text(surf, self.msg, FONT_M, (210, 210, 225), center=(SCREEN_WIDTH // 2, 472))

        # ---- hand ----
        for i, card in enumerate(self.hand):
            sel = (i == self.selected)
            rect = pygame.Rect(20 + i * (CARD_W + 10), CARD_Y - (12 if sel else 0), CARD_W, CARD_H)
            self.draw_card_face(surf, rect, card, i + 1, sel)
        if self.selected is not None:
            hint = "Pick a direction: arrows / WASD / click the maze"
        else:
            hint = "Pick a card: 1-5 or click"
        draw_text(surf, f"{hint}      Draw {len(self.draw_pile)}  Discard {len(self.discard)}",
                  FONT_S, (150, 150, 165), center=(SCREEN_WIDTH // 2, 630))

        # ---- reward overlay ----
        if self.state == "reward":
            ov = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 200))
            surf.blit(ov, (0, 0))
            draw_text(surf, f"ROUND {self.round} CLEARED", FONT_XL, WHITE, center=(SCREEN_WIDTH // 2, 150))
            draw_text(surf, "+1 max HP    -    heal 3, or take a card", FONT_M, YELLOW, center=(SCREEN_WIDTH // 2, 195))
            for i, (kind, val) in enumerate(self.options):
                r = self.reward_rect(i)
                if kind == "heal":
                    pygame.draw.rect(surf, PANEL, r, border_radius=6)
                    pygame.draw.rect(surf, GREEN, r, 2, border_radius=6)
                    draw_text(surf, str(i + 1), FONT_S, GRAY, topleft=(r.x + 8, r.y + 6))
                    draw_text(surf, "HEAL", FONT_M, GREEN, center=(r.centerx, r.y + 24))
                    draw_text(surf, "+3", FONT_L, WHITE, center=(r.centerx, r.centery + 2))
                    draw_text(surf, f"HP ({self.hp}/{self.max_hp})", FONT_S, (150, 150, 165),
                              center=(r.centerx, r.bottom - 14))
                else:
                    self.draw_card_face(surf, r, val, i + 1)

        # ---- death overlay ----
        if self.state == "dead":
            pygame.draw.rect(surf, (100, 0, 0), (0, SCREEN_HEIGHT // 2 - 50, SCREEN_WIDTH, 100))
            draw_text(surf, "YOU DIED", FONT_XL, WHITE, center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 15))
            draw_text(surf, f"Reached round {self.round}  -  press R to restart", FONT_M, WHITE,
                      center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 25))

        if self.show_help:
            self.draw_help(surf)


# ─────────────────────────────────────────
# GAME LOOP
# ─────────────────────────────────────────
def main():
    game = Game()
    canvas = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    running = True
    while running:
        for event in pygame.event.get():
            if not game.handle(event):
                running = False

        game.update()
        game.draw(canvas)

        offset = (0, 0)
        if game.shake > 0:
            game.shake -= 1
            offset = (random.randint(-5, 5), random.randint(-5, 5))
        screen.fill(BLACK)
        screen.blit(canvas, offset)
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
