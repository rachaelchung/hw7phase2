import pygame
from collections import deque

# Mirror the constants from pacman.py — no circular import needed
TILE = 32
COLS = 19
ROWS = 21

BLACK = (0, 0, 0)

# Classic ghost colors
GHOST_COLORS = {
    "blinky": (255,   0,   0),   # red
    "pinky":  (255, 184, 255),   # pink
    "inky":   (  0, 255, 255),   # cyan
    "clyde":  (255, 184,  82),   # orange
}

# Scatter-mode corner targets — must be open (non-wall) tiles.
# Row 0 and row 20 are solid walls in this maze, so we use row 1 / row 19.
SCATTER_TARGETS = {
    "blinky": (COLS - 2, 1),   # top-right
    "pinky":  (1, 1),           # top-left
    "inky":   (COLS - 2, 19),  # bottom-right
    "clyde":  (1, 19),          # bottom-left
}

SCATTER_FRAMES = 7  * 60   # 7 s
CHASE_FRAMES   = 20 * 60   # 20 s

FRIGHTENED_FRAMES      = 7  * 60   # total frightened duration
FRIGHTENED_FLASH_START = 2  * 60   # start flashing 2 s before end

FRIGHTENED_COLOR       = (0,   0, 180)    # dark blue body
FRIGHTENED_FLASH_COLOR = (220, 220, 220)  # near-white for flash

# Ghost-house geometry
#   The pen is the 3-cell area at row 10, cols 8-10 (marked with 2s in MAZE).
#   It sits inside the horizontal tunnel, enclosed by walls on all four sides
#   except the single entrance at (9,9) directly above (9,10).
#   On release a ghost climbs: (9,10) → (9,9) → (9,8) → main maze.
PEN_LEFT          = (8,  10)  # left cell of the pen
PEN_RIGHT         = (10, 10)  # right cell of the pen
GHOST_EXIT_TARGET = (9,   8)  # open corridor tile just above the pen entrance

# Cardinal directions in priority order used by BFS
_DIRS = [(0, -1), (0, 1), (-1, 0), (1, 0)]


def bfs_next_dir(maze, sc, sr, tc, tr, forbidden=None):
    """Return the first (dcol, drow) step on the shortest path from (sc,sr)
    to (tc,tr) via BFS.  Pass forbidden=(rdx, rdy) to block reversing.
    Returns (0, 0) when already at target or no path found.
    """
    if sc == tc and sr == tr:
        return (0, 0)

    visited = {(sc, sr)}
    queue = deque()

    for d in _DIRS:
        if d == forbidden:
            continue
        nc, nr = (sc + d[0]) % COLS, (sr + d[1]) % ROWS
        if maze[nr][nc] != 1:
            queue.append((nc, nr, d))
            visited.add((nc, nr))

    while queue:
        c, r, first = queue.popleft()
        if c == tc and r == tr:
            return first
        for d in _DIRS:
            nc, nr = (c + d[0]) % COLS, (r + d[1]) % ROWS
            if maze[nr][nc] != 1 and (nc, nr) not in visited:
                visited.add((nc, nr))
                queue.append((nc, nr, first))

    # No path with forbidden constraint — retry without it
    return (0, 0)


class Ghost:
    """A single ghost enemy.

    Behaviour summary (matching the original Pac-Man arcade game):
      Blinky  – always targets Pac-Man's current tile.
      Pinky   – targets 4 tiles ahead of Pac-Man's facing direction.
      Inky    – uses Blinky's position: reflect a point 2 tiles ahead of
                Pac-Man through Blinky to get the target.
      Clyde   – chases Pac-Man when far away (>8 tiles), retreats to his
                scatter corner when close.

    All ghosts alternate between *scatter* (go to assigned corner) and *chase*
    modes on a fixed timer.
    """

    def __init__(self, name, col, row, exit_delay=0):
        self.name  = name
        self.color = GHOST_COLORS[name]
        self.scatter_target = SCATTER_TARGETS[name]

        # Tile position
        self.col = col
        self.row = row
        self.target_col = col
        self.target_row = row

        # Pixel position (center of tile)
        self.px = col * TILE + TILE // 2
        self.py = row * TILE + TILE // 2

        self.dir   = (1, 0)    # start moving right so pen bounce looks natural
        self.speed = 2

        self.mode       = "scatter"
        self.mode_timer = SCATTER_FRAMES

        # in_house: True while the ghost is still inside (or exiting) the pen.
        # exit_delay: counts down every frame; when it hits 0 the ghost leaves.
        self.in_house   = True
        self.exit_delay = exit_delay

        # Frightened / eaten state
        self.frightened       = False
        self.frightened_timer = 0
        self.eaten            = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _bounce_in_pen(self):
        """Left-right patrol across the 3-cell pen (row 10, cols 8-10).

        Reverses direction at each end; continues straight through the middle.
        Never calls BFS so the ghost cannot accidentally escape via (9,9).
        """
        if (self.col, self.row) == PEN_RIGHT:
            ndir = (-1, 0)                          # hit right end — go left
        elif (self.col, self.row) == PEN_LEFT:
            ndir = (1, 0)                           # hit left end — go right
        else:
            ndir = self.dir if self.dir[0] != 0 else (1, 0)   # keep going

        nc = self.col + ndir[0]
        if PEN_LEFT[0] <= nc <= PEN_RIGHT[0]:
            self.dir        = ndir
            self.target_col = nc
            self.target_row = PEN_LEFT[1]           # always row 10

    def _get_flee_corner(self, pacman):
        """Return the scatter corner that is farthest from Pac-Man right now."""
        px, py = pacman.col, pacman.row
        return max(SCATTER_TARGETS.values(),
                   key=lambda c: abs(c[0] - px) + abs(c[1] - py))

    def _get_target(self, pacman, blinky):
        """Return the (col, row) target tile for this ghost this frame."""
        if self.eaten:
            return (9, 10)   # pen centre — return home as eyes
        if self.in_house:
            # Released from pen — navigate to the corridor entrance
            return GHOST_EXIT_TARGET
        if self.frightened:
            return self._get_flee_corner(pacman)

        if self.mode == "scatter":
            return self.scatter_target

        # --- Chase mode targeting ---
        px, py   = pacman.col, pacman.row
        pdx, pdy = pacman.dir

        if self.name == "blinky":
            return (px, py)

        if self.name == "pinky":
            tx = max(0, min(COLS - 1, px + pdx * 4))
            ty = max(0, min(ROWS - 1, py + pdy * 4))
            return (tx, ty)

        if self.name == "inky" and blinky is not None:
            # Intermediate point = 2 tiles ahead of Pac-Man
            ax = px + pdx * 2
            ay = py + pdy * 2
            # Reflect through Blinky
            tx = max(0, min(COLS - 1, ax + (ax - blinky.col)))
            ty = max(0, min(ROWS - 1, ay + (ay - blinky.row)))
            return (tx, ty)

        if self.name == "clyde":
            dist = abs(self.col - px) + abs(self.row - py)
            return (px, py) if dist > 8 else self.scatter_target

        return (px, py)

    def _pick_next_tile(self, maze, target):
        """Run BFS and update dir + target tile."""
        dx, dy = self.dir
        # Allow reversals when frightened (flee) or eaten (return to pen)
        if self.frightened or self.eaten:
            forbidden = None
        else:
            forbidden = (-dx, -dy) if (dx or dy) else None

        ndir = bfs_next_dir(maze, self.col, self.row, target[0], target[1], forbidden)
        if ndir == (0, 0):
            # Relax no-reversal when stuck or already at target
            ndir = bfs_next_dir(maze, self.col, self.row, target[0], target[1])

        # Already at target (or truly no path): keep patrolling — pick any
        # valid neighbour so the ghost never freezes in place.
        if ndir == (0, 0):
            for d in _DIRS:
                if d == forbidden:
                    continue
                nc, nr = (self.col + d[0]) % COLS, (self.row + d[1]) % ROWS
                if maze[nr][nc] != 1:
                    ndir = d
                    break

        if ndir == (0, 0):  # absolute last resort: allow reversal
            for d in _DIRS:
                nc, nr = (self.col + d[0]) % COLS, (self.row + d[1]) % ROWS
                if maze[nr][nc] != 1:
                    ndir = d
                    break

        if ndir == (0, 0):
            return  # dead-end tile — genuinely nowhere to go

        new_tc = (self.col + ndir[0]) % COLS
        new_tr = (self.row + ndir[1]) % ROWS

        # Visual teleport when crossing tunnel edges (horizontal)
        if ndir[0] == -1 and self.col == 0:
            self.px = COLS * TILE + TILE // 2
        elif ndir[0] == 1 and self.col == COLS - 1:
            self.px = -TILE // 2

        # Visual teleport when crossing tunnel edges (vertical)
        if ndir[1] == -1 and self.row == 0:
            self.py = ROWS * TILE + TILE // 2
        elif ndir[1] == 1 and self.row == ROWS - 1:
            self.py = -TILE // 2

        self.dir        = ndir
        self.target_col = new_tc
        self.target_row = new_tr

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def frighten(self):
        """Enter frightened mode (called when Pac-Man eats a power pellet)."""
        if self.eaten or self.in_house:
            return
        self.frightened       = True
        self.frightened_timer = FRIGHTENED_FRAMES

    def eat(self):
        """Called when Pac-Man catches this frightened ghost; returns it to the pen."""
        self.frightened       = False
        self.frightened_timer = 0
        self.eaten            = True

    def is_dangerous(self):
        """True when contact with this ghost causes game-over."""
        return not self.frightened and not self.eaten and not self.in_house

    def update(self, maze, pacman, blinky=None):
        """Advance the ghost by one frame.

        Parameters
        ----------
        maze    : 2-D list (same MAZE used in pacman.py)
        pacman  : the Pacman instance
        blinky  : the Blinky Ghost instance (needed for Inky's targeting)
        """
        # Exit delay always ticks — it controls when the ghost leaves the pen
        if self.exit_delay > 0:
            self.exit_delay -= 1

        # Scatter/chase timer only runs after the ghost is fully out of the pen
        if not self.in_house:
            # Tick frightened timer
            if self.frightened:
                self.frightened_timer -= 1
                if self.frightened_timer <= 0:
                    self.frightened = False

            # Scatter/chase timer only ticks when neither frightened nor eaten
            if not self.frightened and not self.eaten:
                self.mode_timer -= 1
                if self.mode_timer <= 0:
                    if self.mode == "scatter":
                        self.mode       = "chase"
                        self.mode_timer = CHASE_FRAMES
                    else:
                        self.mode       = "scatter"
                        self.mode_timer = SCATTER_FRAMES

        # --- Slide toward current target tile ---
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

        # --- At tile centre — choose next tile ---
        if self.px == tcx and self.py == tcy:
            self.col = self.target_col
            self.row = self.target_row

            # Eaten ghost reached the pen centre — reset and wait to re-exit
            if self.eaten and (self.col, self.row) == (9, 10):
                self.eaten      = False
                self.in_house   = True
                self.exit_delay = 3 * 60   # 3 s before re-exiting

            # Once the ghost has left the pen row it is in the main maze
            if self.in_house and self.row < 10:
                self.in_house = False

            if self.in_house and self.exit_delay > 0:
                # Still waiting — patrol left/right inside the pen
                self._bounce_in_pen()
            else:
                target = self._get_target(pacman, blinky)
                self._pick_next_tile(maze, target)

    def get_tile(self):
        """Return the maze tile (col, row) that the ghost's centre is on."""
        return self.px // TILE, self.py // TILE

    def collides_with(self, pacman):
        """True when this ghost shares a tile with Pac-Man."""
        return self.get_tile() == pacman.get_tile()

    def draw(self, screen):
        """Draw the ghost as a classic rounded ghost shape with eyes."""
        cx, cy = self.px, self.py
        r = TILE // 2 - 3   # body radius (≈ 13 px)
        er = max(2, r // 4)
        pdx, pdy = self.dir

        # --- Eaten: eyes only, racing back to pen ---
        if self.eaten:
            for ex_off in (-r // 3, r // 3):
                ey = cy - r // 2
                pygame.draw.circle(screen, (255, 255, 255), (cx + ex_off, ey), er)
                pygame.draw.circle(
                    screen, (0, 0, 200),
                    (cx + ex_off + pdx * (er // 2), ey + pdy * (er // 2)),
                    max(1, er // 2),
                )
            return

        # --- Choose body color (normal / frightened / flashing) ---
        if self.frightened:
            flashing = (self.frightened_timer <= FRIGHTENED_FLASH_START
                        and (self.frightened_timer // 10) % 2 == 0)
            body_color = FRIGHTENED_FLASH_COLOR if flashing else FRIGHTENED_COLOR
        else:
            body_color = self.color

        # --- Body: dome on top + rectangular torso ---
        pygame.draw.circle(screen, body_color, (cx, cy - 2), r)
        pygame.draw.rect(screen, body_color, (cx - r, cy - 2, r * 2, r + 4))

        # --- Wavy skirt: three concave scoops cut from the bottom ---
        seg = (r * 2) // 3
        for i in range(3):
            bx = cx - r + seg * i + seg // 2
            pygame.draw.circle(screen, BLACK, (bx, cy + r + 2), seg // 2)

        # --- Eyes ---
        if self.frightened:
            # Simple white dots while scared
            for ex_off in (-r // 3, r // 3):
                ey = cy - r // 2
                pygame.draw.circle(screen, (255, 255, 255), (cx + ex_off, ey), er)
        else:
            # Normal: white sclera + blue pupils pointing in travel direction
            for ex_off in (-r // 3, r // 3):
                ey = cy - r // 2
                pygame.draw.circle(screen, (255, 255, 255), (cx + ex_off, ey), er)
                pygame.draw.circle(
                    screen, (0, 0, 200),
                    (cx + ex_off + pdx * (er // 2), ey + pdy * (er // 2)),
                    max(1, er // 2),
                )


def create_ghosts():
    """Return the four classic Pac-Man ghosts with staggered release delays.

    Blinky leaves the pen immediately; the others bounce inside for 5 / 10 / 15
    seconds before being released one at a time.
    """
    return [
        Ghost("blinky",  9, 10, exit_delay=0),          #  0 s — exits right away
        Ghost("pinky",   8, 10, exit_delay=5  * 60),    #  5 s
        Ghost("inky",   10, 10, exit_delay=10 * 60),    # 10 s
        Ghost("clyde",   9, 10, exit_delay=15 * 60),    # 15 s
    ]
