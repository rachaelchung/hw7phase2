import pygame
import sys
import math

from ghosts import create_ghosts

# --- Constants ---
TILE = 32
COLS = 19
ROWS = 21
WIDTH = COLS * TILE
HEIGHT = ROWS * TILE + 40  # extra space at bottom for score HUD
FPS = 60

# --- Colors (R, G, B) ---
BLACK  = (0,   0,   0)
BLUE   = (33,  33, 222)
YELLOW = (255, 255,   0)
WHITE  = (255, 255, 255)
PINK   = (255, 184, 255)  # dot color

# --- Maze layout ---
# 1 = wall, 0 = open path (dots will be placed on all 0 tiles)
MAZE = [
    [1,0,1,1,1,1,1,1,0,1,0,1,1,1,1,1,1,0,1],  # cols 8 & 10 open: vertical tunnels
    [1,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,1],
    [1,0,1,1,0,1,1,1,0,1,0,1,1,1,0,1,1,0,1],
    [1,0,1,1,0,1,1,1,0,1,0,1,1,1,0,1,1,0,1],
    [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
    [1,0,1,1,0,1,0,1,1,1,1,1,0,1,0,1,1,0,1],
    [1,0,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0,0,1],
    [1,1,1,1,0,1,1,1,0,1,0,1,1,1,0,1,1,1,1],
    [1,1,1,1,0,1,0,0,0,0,0,0,0,1,0,1,1,1,1],
    [1,1,1,1,0,1,0,1,1,0,1,1,0,1,0,1,1,1,1],
    [0,0,0,0,0,0,0,1,2,2,2,1,0,0,0,0,0,0,0],
    [1,1,1,1,0,1,0,1,1,1,1,1,0,1,0,1,1,1,1],
    [1,1,1,1,0,1,0,0,0,0,0,0,0,1,0,1,1,1,1],
    [1,1,1,1,0,1,0,1,1,1,1,1,0,1,0,1,1,1,1],
    [1,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,1],
    [1,0,1,1,0,1,1,1,0,1,0,1,1,1,0,1,1,0,1],
    [1,0,0,1,0,0,0,0,0,0,0,0,0,0,0,1,0,0,1],
    [1,1,0,1,0,1,0,1,1,1,1,1,0,1,0,1,0,1,1],
    [1,0,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0,0,1],
    [1,0,1,1,1,1,1,1,0,1,0,1,1,1,1,1,1,0,1],
    [1,0,1,1,1,1,1,1,0,1,0,1,1,1,1,1,1,0,1],  # cols 8 & 10 open: vertical tunnels
]

# Bonus fruit — (col, row); must be MAZE[row][col] == 0 (row 13 col 9 is a wall)
FRUIT_SPAWN_TILE = (9, 12)
assert MAZE[FRUIT_SPAWN_TILE[1]][FRUIT_SPAWN_TILE[0]] == 0, "FRUIT_SPAWN_TILE must be open maze cell"

FRUIT_SEQUENCE = [
    ("CHERRY", 100, (220, 40, 60), (50, 160, 70)),
    ("STRAWBERRY", 300, (240, 80, 100), (34, 139, 34)),
    ("ORANGE", 500, (255, 140, 0), (40, 90, 40)),
    ("APPLE", 700, (200, 40, 40), (139, 69, 19)),
    ("MELON", 1000, (50, 200, 100), (240, 230, 140)),
    ("GALAXIAN", 2000, (255, 200, 60), (80, 120, 255)),
    ("BELL", 3000, (255, 215, 0), (180, 140, 40)),
    ("KEY", 5000, (200, 200, 220), (255, 215, 0)),
]
FRUIT_LIFETIME_FRAMES = 10 * FPS

# Tiles where dots should NOT be placed (Pacman's start tile and the ghost house area)
NO_DOT_TILES = {
    (9, 16),                                      # Pacman start position
    (9, 8), (9, 9),                               # ghost house corridor above pen
    # (9,10), (8,10), (10,10) are MAZE value 2 — dots excluded automatically
    (8, 0), (10, 0), (8, 20), (10, 20),           # vertical tunnel openings
    FRUIT_SPAWN_TILE,                             # bonus fruit lane (no pellet underneath)
}

# Power pellet positions — four corners, classic Pac-Man style
POWER_PELLETS = frozenset({(1, 3), (17, 3), (1, 16), (17, 16)})


def build_dots():
    """Return a set of (col, row) positions for every open tile that should have a dot.
    Power pellet tiles are excluded — they are tracked separately."""
    dots = set()
    for r in range(ROWS):
        for c in range(COLS):
            if MAZE[r][c] == 0 and (c, r) not in NO_DOT_TILES and (c, r) not in POWER_PELLETS:
                dots.add((c, r))
    return dots


def build_fruit_thresholds(total_dots):
    """Return sorted dot-eaten totals that trigger a bonus fruit (one wave per milestone)."""
    if total_dots < 14:
        return []
    return sorted({max(10, int(total_dots * p)) for p in (0.28, 0.52, 0.76)})


def draw_bonus_fruit(screen, kind_index):
    """Simple pixel-arcade fruit mark at the fixed spawn cell."""
    col, row = FRUIT_SPAWN_TILE
    t = pygame.time.get_ticks()
    bob = int(2.2 * math.sin(t / 165))
    cx = col * TILE + TILE // 2
    cy = row * TILE + TILE // 2 + bob
    _, _, body, accent = FRUIT_SEQUENCE[kind_index % len(FRUIT_SEQUENCE)]
    r = TILE // 3
    glow = tuple(min(255, c + 45) for c in body)
    pygame.draw.circle(screen, glow, (cx, cy), r + 4, 2)
    pygame.draw.circle(screen, body, (cx, cy), r)
    pygame.draw.circle(screen, accent, (cx - r // 2 + 1, cy - r // 3), max(3, r // 3))
    pygame.draw.circle(screen, accent, (cx + r // 2 - 1, cy - r // 4), max(3, r // 4))
    pygame.draw.line(screen, accent, (cx, cy - r - 1), (cx + 3, cy - r - 8), 3)
    pygame.draw.line(screen, (30, 30, 30), (cx - r - 2, cy + r // 2), (cx + r + 2, cy + r // 2), 1)


class Pacman:
    def __init__(self, col, row):
        self.px = col * TILE + TILE // 2
        self.py = row * TILE + TILE // 2

        self.col = col
        self.row = row
        self.target_col = col
        self.target_row = row

        self.dir = (0, 0)

        self.next_dir = (0, 0)
        self.speed = 2
        self.mouth_angle = 45
        self.mouth_open = True

    def set_direction(self, d):
        self.next_dir = d

    def _try_dir(self, dcol, drow, maze):
        """Return (nc, nr, wrapped) if moving in (dcol, drow) is valid, else None.

        Wraparound is allowed only when the current edge cell and the destination
        edge cell are both open (not walls).
        """
        nc = self.col + dcol
        nr = self.row + drow
        wrapped = False

        if nc < 0:
            nc = COLS - 1
            wrapped = True
        elif nc >= COLS:
            nc = 0
            wrapped = True

        if nr < 0:
            nr = ROWS - 1
            wrapped = True
        elif nr >= ROWS:
            nr = 0
            wrapped = True

        if maze[nr][nc] != 1:
            return nc, nr, wrapped
        return None

    def _enter_from_edge(self, dcol, drow):
        """Teleport px/py to the opposite screen edge so the slide into the
        wrapped tile looks correct (Pacman exits one side, enters the other)."""
        if dcol == -1:
            self.px = COLS * TILE + TILE // 2
        elif dcol == 1:
            self.px = -TILE // 2
        if drow == -1:
            self.py = ROWS * TILE + TILE // 2
        elif drow == 1:
            self.py = -TILE // 2

    def move(self, maze):
        tcx = self.target_col * TILE + TILE // 2
        tcy = self.target_row * TILE + TILE // 2

        dx, dy = self.dir

        if self.px != tcx or self.py != tcy:
            self.px += dx * self.speed
            self.py += dy * self.speed

            if dx > 0 and self.px > tcx: self.px = tcx
            if dx < 0 and self.px < tcx: self.px = tcx
            if dy > 0 and self.py > tcy: self.py = tcy
            if dy < 0 and self.py < tcy: self.py = tcy

        if self.px == tcx and self.py == tcy:
            self.col, self.row = self.target_col, self.target_row

            ndx, ndy = self.next_dir
            result = self._try_dir(ndx, ndy, maze) if (ndx != 0 or ndy != 0) else None
            if result:
                nc, nr, wrapped = result
                self.dir = self.next_dir
                if wrapped:
                    self._enter_from_edge(ndx, ndy)
                self.target_col, self.target_row = nc, nr
            else:
                result = self._try_dir(dx, dy, maze) if (dx != 0 or dy != 0) else None
                if result:
                    nc, nr, wrapped = result
                    if wrapped:
                        self._enter_from_edge(dx, dy)
                    self.target_col, self.target_row = nc, nr
                else:
                    self.dir = (0, 0)
        # Animations
        if self.mouth_open:
            self.mouth_angle -= 2
            if self.mouth_angle <= 0:
                self.mouth_open = False
        else:
            self.mouth_angle += 2
            if self.mouth_angle >= 45:
                self.mouth_open = True

    def get_tile(self):
        """Return the tile (col, row) Pacman's center is currently on."""
        col = self.px // TILE
        row = self.py // TILE
        return col, row

    def draw(self, screen):
        cx, cy = self.px, self.py
        angle_map = {(1,0): 0, (-1,0): 180, (0,-1): 90, (0,1): 270}
        start_angle = angle_map.get(self.dir, 0)
        r = TILE // 2 - 2
        points = [(cx, cy)]
        for a in range(self.mouth_angle, 360 - self.mouth_angle + 1, 2):
            rad = math.radians(a + start_angle)
            points.append((cx + r * math.cos(rad),
                            cy - r * math.sin(rad)))
        if len(points) > 2:
            pygame.draw.polygon(screen, YELLOW, points)


SCORE_POP_DURATION = 42  # ~0.7 s at 60 FPS
SCORE_POP_RISE = 1.1     # pixels per frame upward drift


def _update_score_pops(pops):
    """Age and drift floating point pop-ups; drop expired entries."""
    alive = []
    for p in pops:
        p["age"] += 1
        p["y"] -= SCORE_POP_RISE
        if p["age"] < p["duration"]:
            alive.append(p)
    pops[:] = alive


def _draw_score_pops(screen, font, pops):
    """Draw pop-ups with a quick float-up + fade toward the background."""
    for p in pops:
        t = p["age"] / max(1, p["duration"] - 1)
        r0, g0, b0 = p["color"]
        # Blend toward maze black so text "dissolves"
        r = int(r0 + (12 - r0) * t)
        g = int(g0 + (0 - g0) * t)
        b = int(b0 + (28 - b0) * t)
        out = (
            int(20 + (12 - 20) * t),
            int(20 + (0 - 20) * t),
            int(40 + (28 - 40) * t),
        )
        _draw_retro_text(screen, font, p["text"], (r, g, b), (int(p["x"]), int(p["y"])), outline=out)


def _spawn_score_pop(pops, x, y, points, color):
    pops.append({
        "text": str(points),
        "x": float(x),
        "y": float(y),
        "age": 0,
        "duration": SCORE_POP_DURATION,
        "color": color,
    })


def _draw_retro_text(screen, font, text, color, center_xy, outline=(0, 0, 0)):
    """Chunky arcade outline: shadow offsets then fill."""
    cx, cy = center_xy
    surf = font.render(text, True, color)
    ox = max(2, font.get_height() // 18)
    for dx, dy in (
        (-ox, 0), (ox, 0), (0, -ox), (0, ox),
        (-ox, -ox), (ox, -ox), (-ox, ox), (ox, ox),
    ):
        o = font.render(text, True, outline)
        r = surf.get_rect(center=(cx + dx, cy + dy))
        screen.blit(o, r)
    screen.blit(surf, surf.get_rect(center=(cx, cy)))


def _draw_arcade_frame(screen, rect, c1, c2):
    """Nested neon-style border like a cocktail cabinet bezel."""
    x, y, w, h = rect
    pygame.draw.rect(screen, c1, (x, y, w, h), width=4)
    pygame.draw.rect(screen, c2, (x + 6, y + 6, w - 12, h - 12), width=2)
    pygame.draw.rect(screen, (10, 10, 30), (x + 12, y + 12, w - 24, h - 24))


def _draw_scanlines(surface):
    t = pygame.time.get_ticks()
    sh = surface.get_height()
    for ly in range(0, sh, 3):
        a = 35 + int(15 * math.sin((ly + t * 0.02) * 0.05))
        s = pygame.Surface((surface.get_width(), 2), pygame.SRCALPHA)
        s.fill((0, 0, 0, a))
        surface.blit(s, (0, ly))


def draw_game_over_screen(screen, fonts, score):
    """Retro arcade cabinet style game-over overlay."""
    font_title, font_sub, font_hint = fonts
    t = pygame.time.get_ticks()

    dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    dim.fill((12, 0, 28, 220))
    screen.blit(dim, (0, 0))

    frame = pygame.Rect(24, 48, WIDTH - 48, HEIGHT - 88)
    pulse = 0.5 + 0.5 * math.sin(t / 200)
    c_outer = (int(255 * pulse), 40, 80)
    c_inner = (255, 120, 180)
    _draw_arcade_frame(screen, frame, c_outer, c_inner)

    cx, cy = WIDTH // 2, HEIGHT // 2 - 26
    _draw_retro_text(screen, font_title, "GAME OVER", (255, 60, 60), (cx, cy - 28))
    _draw_retro_text(screen, font_sub, f"SCORE {score}", (255, 255, 180), (cx, cy + 24))

    blink = (t // 500) % 2 == 0
    if blink:
        _draw_retro_text(
            screen, font_hint, "PRESS  R  TO  CONTINUE",
            (130, 255, 200), (cx, cy + 62), outline=(0, 40, 30),
        )
    _draw_retro_text(
        screen, font_hint, "ESC  EXIT",
        (180, 180, 200), (cx, cy + 92), outline=(20, 20, 40),
    )

    v = screen.copy()
    _draw_scanlines(v)
    # re-blit scanline layer only inside frame inner area for CRT pocket
    inner = pygame.Rect(frame.x + 12, frame.y + 12, frame.w - 24, frame.h - 24)
    sub = v.subsurface(inner)
    screen.blit(sub, inner.topleft)


def draw_win_screen(screen, fonts, score, total):
    """Retro high-score / stage clear style overlay."""
    font_title, font_sub, font_hint = fonts
    t = pygame.time.get_ticks()

    dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    dim.fill((0, 22, 18, 215))
    screen.blit(dim, (0, 0))

    frame = pygame.Rect(24, 48, WIDTH - 48, HEIGHT - 88)
    pulse = 0.5 + 0.5 * math.sin(t / 180)
    c_outer = (40, int(220 * pulse), 255)
    c_inner = (255, 220, 80)
    _draw_arcade_frame(screen, frame, c_outer, c_inner)

    cx, cy = WIDTH // 2, HEIGHT // 2 - 26
    hue = int(110 + 40 * math.sin(t / 300))
    _draw_retro_text(screen, font_title, "PLAYER 1", (255, hue, 40), (cx, cy - 44))
    _draw_retro_text(screen, font_sub, "STAGE CLEAR", (80, 255, 200), (cx, cy - 6))
    _draw_retro_text(screen, font_sub, f"SCORE {score}", WHITE, (cx, cy + 26))
    _draw_retro_text(
        screen, font_hint, f"DOTS CLEARED {total}",
        (200, 240, 255), (cx, cy + 54), outline=(20, 30, 60),
    )

    blink = (t // 500) % 2 == 0
    if blink:
        _draw_retro_text(
            screen, font_hint, "PRESS  R  FOR NEW GAME",
            (255, 255, 120), (cx, cy + 88), outline=(60, 80, 0),
        )

    v = screen.copy()
    _draw_scanlines(v)
    inner = pygame.Rect(frame.x + 12, frame.y + 12, frame.w - 24, frame.h - 24)
    sub = v.subsurface(inner)
    screen.blit(sub, inner.topleft)


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Pacman")
    clock = pygame.time.Clock()

    font_large = pygame.font.SysFont("courier new", 46, bold=True)
    font_small = pygame.font.SysFont("courier new", 28, bold=True)
    font_hud   = pygame.font.SysFont("courier new", 24, bold=True)
    font_pop   = pygame.font.SysFont("courier new", 34, bold=True)
    arcade_fonts = (font_large, font_small, font_hud)

    def reset():
        pacman              = Pacman(9, 16)
        dots                = build_dots()
        total_dots          = len(dots)
        score               = 0
        won                 = False
        game_over           = False
        ghosts              = create_ghosts()
        power_pellets       = set(POWER_PELLETS)
        ghost_eat_score     = 200
        fruit_thresholds    = build_fruit_thresholds(total_dots)
        fruit_milestone_idx = 0
        fruits_spawned      = 0
        active_fruit        = None  # None or {"kind": int, "ttl": int}
        score_pops          = []   # floating "+points" animations
        return (
            pacman, dots, total_dots, score, won, game_over, ghosts, power_pellets, ghost_eat_score,
            fruit_thresholds, fruit_milestone_idx, fruits_spawned, active_fruit, score_pops,
        )

    (
        pacman, dots, total_dots, score, won, game_over, ghosts, power_pellets, ghost_eat_score,
        fruit_thresholds, fruit_milestone_idx, fruits_spawned, active_fruit, score_pops,
    ) = reset()

    while True:
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:
                    pacman.set_direction((-1, 0))
                elif event.key == pygame.K_RIGHT:
                    pacman.set_direction((1, 0))
                elif event.key == pygame.K_UP:
                    pacman.set_direction((0, -1))
                elif event.key == pygame.K_DOWN:
                    pacman.set_direction((0, 1))
                elif event.key == pygame.K_r and (won or game_over):
                    (
                        pacman, dots, total_dots, score, won, game_over, ghosts, power_pellets, ghost_eat_score,
                        fruit_thresholds, fruit_milestone_idx, fruits_spawned, active_fruit, score_pops,
                    ) = reset()
                elif event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()

        if not won and not game_over:
            pacman.move(MAZE)

            # --- Dot collection ---
            tile = pacman.get_tile()
            if tile in dots:
                dots.remove(tile)
                score += 1
                if len(dots) == 0 and len(power_pellets) == 0:
                    won = True

            # --- Power pellet collection ---
            if tile in power_pellets:
                power_pellets.remove(tile)
                score += 5
                ghost_eat_score = 200          # reset eat-score multiplier
                for ghost in ghosts:
                    ghost.frighten()
                if len(dots) == 0 and len(power_pellets) == 0:
                    won = True

            # --- Ghost updates and collision ---
            blinky = ghosts[0]
            for ghost in ghosts:
                ghost.update(MAZE, pacman, blinky)
            for ghost in ghosts:
                if ghost.collides_with(pacman):
                    if ghost.is_dangerous():
                        game_over = True
                        break
                    elif ghost.frightened:
                        pts = ghost_eat_score
                        ghost.eat()
                        score += pts
                        _spawn_score_pop(
                            score_pops, ghost.px, ghost.py - TILE // 4, pts,
                            (180, 255, 255),
                        )
                        ghost_eat_score = min(1600, ghost_eat_score * 2)

            # --- Bonus fruit (milestones + timed despawn) ---
            eaten = total_dots - len(dots)
            if active_fruit is not None:
                active_fruit["ttl"] -= 1
                if tile == FRUIT_SPAWN_TILE:
                    _, pts, _, _ = FRUIT_SEQUENCE[active_fruit["kind"]]
                    score += pts
                    fc, fr = FRUIT_SPAWN_TILE
                    _spawn_score_pop(
                        score_pops,
                        fc * TILE + TILE // 2,
                        fr * TILE + TILE // 2 - TILE // 4,
                        pts,
                        (255, 230, 120),
                    )
                    active_fruit = None
                elif active_fruit["ttl"] <= 0:
                    active_fruit = None
            while (
                active_fruit is None
                and fruit_milestone_idx < len(fruit_thresholds)
                and eaten >= fruit_thresholds[fruit_milestone_idx]
            ):
                active_fruit = {
                    "kind": fruits_spawned % len(FRUIT_SEQUENCE),
                    "ttl": FRUIT_LIFETIME_FRAMES,
                }
                fruits_spawned += 1
                fruit_milestone_idx += 1

        _update_score_pops(score_pops)

        # --- Draw ---
        screen.fill(BLACK)

        # Draw maze walls
        for r in range(ROWS):
            for c in range(COLS):
                x, y = c * TILE, r * TILE
                if MAZE[r][c] == 1:
                    pygame.draw.rect(screen, BLUE, (x+1, y+1, TILE-2, TILE-2), border_radius=4)

        # Draw dots
        for (dc, dr) in dots:
            cx = dc * TILE + TILE // 2
            cy = dr * TILE + TILE // 2
            pygame.draw.circle(screen, PINK, (cx, cy), 3)

        # Draw power pellets — larger, gently pulsing
        pulse_r = int(7 + 2 * math.sin(pygame.time.get_ticks() / 250))
        for (pc, pr) in power_pellets:
            cx = pc * TILE + TILE // 2
            cy = pr * TILE + TILE // 2
            pygame.draw.circle(screen, PINK, (cx, cy), pulse_r)

        # Draw ghosts (behind Pac-Man)
        for ghost in ghosts:
            ghost.draw(screen)

        # Draw Pacman
        pacman.draw(screen)

        _draw_score_pops(screen, font_pop, score_pops)

        if active_fruit is not None:
            draw_bonus_fruit(screen, active_fruit["kind"])

        # --- HUD: score bar at the bottom ---
        hud_y = ROWS * TILE
        pygame.draw.rect(screen, (20, 20, 20), (0, hud_y, WIDTH, 40))
        score_surf = font_hud.render(f"SCORE {score}", True, WHITE)
        remaining_surf = font_hud.render(f"DOTS {len(dots)}", True, (180, 255, 200))
        screen.blit(score_surf,     (10, hud_y + 8))
        screen.blit(remaining_surf, (WIDTH - remaining_surf.get_width() - 10, hud_y + 8))
        if active_fruit is not None:
            name, pts, _, _ = FRUIT_SEQUENCE[active_fruit["kind"]]
            bonus_surf = font_hud.render(f"{name} {pts}", True, (255, 220, 120))
            screen.blit(bonus_surf, ((WIDTH - bonus_surf.get_width()) // 2, hud_y + 8))

        # Game-over / win overlays
        if game_over:
            draw_game_over_screen(screen, arcade_fonts, score)
        elif won:
            draw_win_screen(screen, arcade_fonts, score, total_dots)

        pygame.display.flip()


if __name__ == "__main__":
    main()