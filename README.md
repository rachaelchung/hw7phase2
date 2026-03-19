# Collaboration Pacman

This is a Pacman remake that features an animated Pacman, points, four ghosts, and fruits.
The game is over when a ghost catches you and you can win by clearing all the dots on the map.

Additional features include:
- An animated game win/lose screen
- Staggered ghost exits and individual ghost characteristics
- Power pellets that let you eat the ghosts for a period of time
- Animations for points gained from eating ghosts or fruits
- Fruits that appear on the board for extra points

---

The game uses the four classic Pac-Man ghosts, each with a distinct color and chase personality inspired by the arcade original:

- Blinky (red) — Always targets Pac-Man’s current tile.
- Pinky (pink) — Targets a tile four squares ahead of Pac-Man in the direction he’s facing (clamped to the maze).
- Inky (cyan) — Uses Blinky’s position: it takes a point two tiles ahead of Pac-Man, reflects that point through Blinky’s tile, and chases that reflected target (so Inky’s path depends on both Pac-Man and Blinky).
- Clyde (orange) — Ambush-style: if he is more than eight Manhattan tiles from Pac-Man he chases him; if closer, he acts like scatter and heads for his own corner instead of hugging Pac-Man.


---

To run:
```bash
pip install pygame
python3 pacman.py
```