"""Draws Edge Claw's own (original) animations into pet/custom_sprites.json.

Same format as clawd_sprites.json: each frame is a w*h string, '.' transparent,
otherwise a base-36 index into the palette. Run: python tools/draw_custom.py

Everything plays at 12 fps like the official clips, moves at most a pixel or
two a frame, and starts and ends on Clawd's plain standing frame (the same
pixels as CrabWalking's first frame), so it cuts in and out of walking cleanly.
"""
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "pet", "custom_sprites.json")

PALETTE = [
    "#141413",  # 0 ink: eyes
    "#be684d",  # 1 shade
    "#d97757",  # 2 Clawd
    "#8b8b8b",  # 3 fishing line
    "#f0eee6",  # 4 white: bobber top, splash, stripes
    "#c84b31",  # 5 red: bobber bottom
    "#7a5230",  # 6 rod
    "#9cc3d5",  # 7 ripple
    "#c9a77c",  # 8 cod
    "#8a6a48",  # 9 cod dark
    "#e6d3b0",  # a cod belly
    "#c0453b",  # b salmon
    "#7a2e2a",  # c salmon dark
    "#9aa391",  # d salmon belly
    "#ef8a2a",  # e tropical fish
    "#e5c13b",  # f pufferfish
    "#9c7e22",  # g pufferfish spines
    "#a8743f",  # h dock planks
    "#6b4626",  # i dock posts, plank gaps
    "#5fa8dc",  # j bubbles
]
INK, SHADE, BODY, LINE, WHITE, RED, ROD, RIPPLE = range(8)
FPS = 12


class Grid:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = [["."] * w for _ in range(h)]

    def put(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = "." if c is None else _b36(c)

    def rect(self, x, y, w, h, c):
        for j in range(h):
            for i in range(w):
                self.put(x + i, y + j, c)

    def line(self, x0, y0, x1, y1, c):
        n = max(abs(x1 - x0), abs(y1 - y0), 1)
        for k in range(n + 1):
            self.put(round(x0 + (x1 - x0) * k / n), round(y0 + (y1 - y0) * k / n), c)

    def frame(self):
        return "".join("".join(r) for r in self.px)


def _b36(c):
    return "0123456789abcdefghijklmnopqrstuvwxyz"[c]


def clip(frames, w, h, fps=FPS):
    """Clawd stands in the middle of the canvas, feet on the bottom row."""
    return {"w": w, "h": h, "fps": fps, "palette": PALETTE, "ax": w // 2, "ay": h, "frames": frames}


# --- Clawd -------------------------------------------------------------------

def sitter(g, feet, legs=4, lean=0, eyes="open", left_arm=0, right_arm=0, x0=0):
    """Clawd standing (legs 4) or sunk down onto its legs (legs 1), feet on row `feet`.

    lean shifts the body (not the feet) sideways; left_arm/right_arm raise (-) or
    lower (+) an arm by pixels; x0 is Clawd's left edge. Returns the right claw's
    grip point.
    """
    top = feet - legs - 11
    x = x0 + lean
    g.rect(x + 4, top, 16, 12, BODY)
    g.rect(x, top + 4 + left_arm, 4, 4, BODY)
    g.rect(x + 20, top + 4 + right_arm, 4, 4, BODY)
    for lx in (4, 8, 14, 18):
        g.rect(x0 + lx, feet - legs + 1, 2, legs, BODY)
    ex, ey = x + 6, top + 2
    if eyes == "open":
        g.rect(ex, ey, 2, 2, INK)
        g.rect(ex + 8, ey, 2, 2, INK)
    elif eyes == "stare":  # fixed on where the line goes in: down and forward
        g.rect(ex + 2, ey + 2, 2, 2, INK)
        g.rect(ex + 10, ey + 2, 2, 2, INK)
    elif eyes == "stare_closed":  # blinking mid-stare
        g.rect(ex + 2, ey + 3, 2, 1, INK)
        g.rect(ex + 10, ey + 3, 2, 1, INK)
    elif eyes == "look":  # forward and down
        g.rect(ex + 1, ey + 1, 2, 2, INK)
        g.rect(ex + 9, ey + 1, 2, 2, INK)
    elif eyes == "wide":  # a bite! eyes up and tall
        g.rect(ex, ey - 1, 2, 3, INK)
        g.rect(ex + 8, ey - 1, 2, 3, INK)
    elif eyes == "closed":
        g.rect(ex, ey + 1, 2, 1, INK)
        g.rect(ex + 8, ey + 1, 2, 1, INK)
    elif eyes == "happy":  # ^ ^
        for bx in (ex, ex + 8):
            g.put(bx - 1, ey + 1, INK)
            g.rect(bx, ey, 2, 1, INK)
            g.put(bx + 2, ey + 1, INK)
    return x + 22, top + 5 + right_arm


# --- stretching --------------------------------------------------------------
#
# Eyes shut, the claws come up a pixel at a time until they are straight up,
# Clawd grows taller and goes up on tiptoe, shivers at the top of the stretch
# with a big yawn, then lets it all go and sags with a sigh, blowing a bubble
# that floats up and pops, before standing normally again.

SW, SH = 24, 34  # room above the head for the sigh bubble

# Arm positions: (left edge offset, top offset from the body's top, width, height)
ARMS = [(0, 4, 4, 4), (0, 3, 4, 4), (1, 1, 3, 5), (1, -2, 3, 7), (1, -5, 3, 9)]


def stretcher(g, arms=0, tall=0, tiptoe=0, eyes="open", yawn=0, shake=0):
    """Clawd standing on the bottom row; arms 0 (out) .. 4 (straight up), tall
    stretches the body, tiptoe lifts it onto the tips of its legs, yawn opens
    a mouth that many pixels tall, shake shifts it sideways."""
    feet = SH - 1
    legs = 4 + tiptoe
    top = feet - legs - 11 - tall
    x = shake
    g.rect(x + 4, top, 16, 12 + tall, BODY)
    ax, ay, aw, ah = ARMS[arms]
    g.rect(x + ax, top + ay, aw, ah, BODY)
    g.rect(x + 24 - ax - aw, top + ay, aw, ah, BODY)
    for lx in (4, 8, 14, 18):
        g.rect(lx, feet - legs + 1, 2, legs, BODY)
        if tiptoe:  # only the tips touch: the outer column lifts
            g.put(lx + (0 if lx < 12 else 1), feet, None)
    ex, ey = x + 6, top + 2
    if eyes == "open":
        g.rect(ex, ey, 2, 2, INK)
        g.rect(ex + 8, ey, 2, 2, INK)
    elif eyes == "closed":
        g.rect(ex, ey + 1, 2, 1, INK)
        g.rect(ex + 8, ey + 1, 2, 1, INK)
    elif eyes == "squeeze":  # screwed shut: > <
        for bx, d in ((ex, 1), (ex + 8, -1)):
            g.put(bx + (0 if d > 0 else 1), ey, INK)
            g.put(bx + (1 if d > 0 else 0), ey + 1, INK)
            g.put(bx + (0 if d > 0 else 1), ey + 2, INK)
    if yawn:
        g.rect(x + 11, top + 5, 2, yawn, INK)


def sigh_bubble(g, cx, cy, size):
    """The bubble Clawd blows out with its sigh, centred on (cx, cy): 1 small,
    2 grown, 3 popping."""
    if size == 1:
        for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
            g.put(cx + dx, cy + dy, BUBBLE)
        g.put(cx, cy, WHITE)
    elif size == 2:
        for dx in (-1, 0, 1):
            g.put(cx + dx, cy - 2, BUBBLE)
            g.put(cx + dx, cy + 2, BUBBLE)
        for dy in (-1, 0, 1):
            g.put(cx - 2, cy + dy, BUBBLE)
            g.put(cx + 2, cy + dy, BUBBLE)
        g.put(cx - 1, cy - 1, WHITE)  # the shine
    else:
        for dx, dy in ((-2, -2), (2, -2), (-3, 0), (3, 0), (-2, 2), (2, 2)):
            g.put(cx + dx, cy + dy, BUBBLE)


def stretching():
    S = "squeeze"
    top4 = dict(eyes=S, arms=4, tall=2, tiptoe=1)
    seq = (
        [{}] * 4
        + [dict(eyes="closed")] * 2
        # the claws come up, a pixel at a time
        + [dict(eyes="closed", arms=a) for a in (1, 1, 2, 2, 3, 3, 4, 4)]
        # reaching higher: taller, then up on tiptoe
        + [dict(eyes=S, arms=4, tall=t) for t in (1, 1, 2, 2)]
        + [top4] * 4
        # the shiver at the top, with a big yawn
        + [dict(top4, shake=s, yawn=y) for s, y in
           ((1, 1), (-1, 1), (1, 2), (-1, 2), (1, 3), (-1, 3), (1, 3), (-1, 3),
            (1, 3), (-1, 3), (0, 3), (0, 3), (0, 3), (0, 2), (0, 1))]
        + [top4] * 3
        # let go, slowly
        + [dict(eyes="closed", arms=4, tall=2), dict(eyes="closed", arms=4, tall=1),
           dict(eyes="closed", arms=4), dict(eyes="closed", arms=3), dict(eyes="closed", arms=3),
           dict(eyes="closed", arms=2), dict(eyes="closed", arms=2), dict(eyes="closed", arms=1),
           dict(eyes="closed")]
    )
    # the sigh: it sags, and a bubble comes out of its mouth, floats up and pops
    sigh = [(1, 1, (12, 0, 1)), (1, 1, (12, -2, 1)), (1, 0, (12, -4, 2)), (1, 0, (12, -6, 2)),
            (1, 0, (13, -8, 2)), (1, 0, (13, -10, 2)), (0, 0, (12, -12, 2)), (0, 0, (11, -14, 2)),
            (0, 0, (11, -16, 2)), (0, 0, (12, -18, 2)), (0, 0, (12, -19, 3)), (0, 0, None)]
    frames = []
    for kw in seq:
        g = Grid(SW, SH)
        stretcher(g, **kw)
        frames.append(g.frame())
    for sag, yawn, bub in sigh:
        g = Grid(SW, SH)
        stretcher(g, eyes="closed", tall=-sag, yawn=yawn)
        if bub:  # relative to the top of Clawd's head
            cx, dy, size = bub
            sigh_bubble(g, cx, SH - 16 + 5 + dy, size)
        frames.append(g.frame())
    for kw in [dict(eyes="closed"), {}, {}, {}, dict(eyes="closed"), {}, {}, {}, {}]:
        g = Grid(SW, SH)
        stretcher(g, **kw)
        frames.append(g.frame())
    return clip(frames, SW, SH)


# --- fishing -----------------------------------------------------------------
#
# A little wooden dock slides in from behind Clawd while it hops in place, so it
# lands on it. It sits at the dock's end and fishes in the taskbar: the line
# goes down past the end of the dock, and bubbles come up where it meets the
# taskbar's top edge. Afterwards Clawd hops off and the dock slides away.
#
# The canvas is wider than the window normally is (the pet widens its window
# while fishing): Clawd stands in the middle, with room behind for the dock to
# slide in from and room in front for the line.

WOOD, POST, BUBBLE = 17, 18, 19
FW, FH = 80, 30
F = FH - 1  # the taskbar's top edge (Clawd's feet row when on it)
X0 = 28  # Clawd's left edge; its middle is the canvas middle
DOCK_H = 4  # planks two rows, posts two rows
DOCK_TOP = F - DOCK_H  # Clawd's feet row when on the dock
DOCK_LEN = 33
DOCK_HOME = X0 + 22 - DOCK_LEN  # Clawd sits right at the dock's end
ROD_LEN = 16
REST = 35  # the rod's angle while waiting
LINE_X = 63  # where the line meets the taskbar

# Fish, drawn facing left; letters are palette indices, * the eye, 0 the mouth.
FISH = {
    "cod": (["..999...",
             ".98889.9",
             "0*88889.",
             ".aaaa999",
             "..aaa..9"]),
    "salmon": (["..cccc...",
                ".cbbbbc.c",
                "0*bbbbbcc",
                ".ddddddcc",
                "..dddd..c"]),
    "tropical": (["..ee..e",
                  ".e4e4ee",
                  "0*4e4e.",
                  ".e4e4ee",
                  "..ee..e"]),
    "pufferfish": ([".g.g.g.",
                    "gffffg.",
                    "0*fffff",
                    "fffffgg",
                    "gffffg.",
                    ".g.g.g."]),
}


def draw_fish(g, kind, x, bottom, flip=False, squash=False):
    """The fish with its left edge at x and its lowest row on `bottom`; returns its mouth."""
    rows = list(FISH[kind])
    if squash:  # flattened as it smacks down
        below = next(j for j, r in enumerate(rows) if "0" in r) + 1  # keep the mouth row
        rows = rows[:below] + rows[below + 1:]
    if flip:
        rows = [r[::-1] for r in rows]
    top = bottom - len(rows) + 1
    for j, r in enumerate(rows):
        for i, ch in enumerate(r):
            if ch in ".0":  # 0 is the mouth: a notch the line hooks into
                continue
            g.put(x + i, top + j, INK if ch == "*" else int(ch, 36))
    mouth_row = next(j for j, r in enumerate(rows) if "0" in r)
    return (x + rows[mouth_row].index("0"), top + mouth_row)


def dock(g, left):
    g.rect(left, DOCK_TOP + 1, DOCK_LEN, 2, WOOD)
    for i in range(5, DOCK_LEN, 6):  # gaps between the planks
        g.put(left + i, DOCK_TOP + 1, POST)
    for px in (2, DOCK_LEN // 2, DOCK_LEN - 4):
        g.rect(left + px, DOCK_TOP + 3, 2, 2, POST)


def bubble(g, x, y, size):
    """size 1: a dot; 2: a little ring; 3: popping."""
    if size == 1:
        g.put(x, y, BUBBLE)
    elif size == 2:
        for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
            g.put(x + dx, y + dy, BUBBLE)
        g.put(x, y, WHITE)
    else:
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            g.put(x + dx, y + dy, BUBBLE)


def bubble_at(age, x):
    """A bubble `age` frames after it came up at x, or None once it has popped."""
    if age < 0 or age > 12:
        return None
    y = F - 1 - age // 2
    return (x + (1 if age // 4 % 2 else 0), y, 1 if age < 4 else 3 if age == 12 else 2)


def frame(feet=DOCK_TOP, legs=1, lean=0, eyes="stare", angle=REST, length=ROD_LEN,
          left_arm=0, right_arm=0, dock_x=DOCK_HOME, line_end=None, fish=None, hooked=False,
          dangle=0, bubbles=(), splash=()):
    """One frame. line_end: where the cast line ends; hooked: the line goes to the fish's
    mouth; dangle: the reeled-in line hanging this long from the rod tip."""
    g = Grid(FW, FH)
    if dock_x is not None:
        dock(g, dock_x)
    top = feet - legs - 11
    grip = (X0 + lean + 22, top + 5 + right_arm)
    tip = grip
    if length > 0:  # behind Clawd: it comes out of the claw
        a = math.radians(angle)
        tip = (round(grip[0] + length * math.cos(a)), round(grip[1] - length * math.sin(a)))
        g.line(grip[0], grip[1], tip[0], tip[1], ROD)
    sitter(g, feet, legs, lean, eyes, left_arm, right_arm, X0)
    mouth = None
    if fish:
        kind, fx, fbottom, flip, squash = fish
        mouth = draw_fish(g, kind, fx, fbottom, flip, squash)
    end = mouth if hooked else line_end
    if end is not None and length > 0:
        g.line(tip[0], tip[1] + 1, end[0], end[1], LINE)
    if dangle:
        g.line(tip[0], tip[1] + 1, tip[0], tip[1] + dangle, LINE)
    for b in bubbles:
        if b:
            bubble(g, *b)
    for sx, sy in splash:
        g.put(sx, sy, WHITE)
    return g.frame()


def standing(**kw):
    return frame(feet=F, legs=4, eyes="open", length=0, **kw)


# Hopping onto the dock: crouch, up, and down onto the planks as the dock
# slides in underneath, then a squash on landing. (feet height above the
# taskbar, legs, where the dock's left end is)
HOP_ON = [(0, 3, -53), (0, 2, -39), (3, 4, -27), (6, 4, -17), (8, 4, -8), (9, 4, 0), (9, 4, 6),
          (8, 4, 11), (7, 4, 14), (5, 4, 16), (4, 2, 17), (4, 3, 17), (4, 4, 17)]
HOP_OFF = [(4, 3, 17), (4, 2, 17), (7, 4, 17), (10, 4, 16), (12, 4, 12), (13, 4, 5), (13, 4, -5),
           (12, 4, -17), (10, 4, -31), (7, 4, -47), (4, 4, -63), (1, 4, None), (0, 2, None),
           (0, 3, None)]


def hop(steps, eyes="open"):
    return [frame(feet=F - h, legs=l, eyes=eyes, length=0, dock_x=d) for h, l, d in steps]


def sit_down():
    return [frame(legs=l, eyes="open", length=0) for l in (3, 2, 1)]


def stand_up():
    return [frame(legs=l, eyes="open", length=0) for l in (2, 3, 4)]


def put_away(start_angle):
    """The rod swings back behind Clawd and goes away."""
    out = [frame(angle=start_angle + d, length=n, eyes="open")
           for d, n in ((25, 16), (60, 14), (100, 11), (140, 7), (170, 3))]
    return out + [frame(length=0, eyes="open")]


def leave():
    """Rod away: stand, hop off, the dock slides off behind, back on the taskbar."""
    return stand_up() + hop(HOP_OFF) + [standing(dock_x=None)] * 2


def wait_bubbles(i, n=48):
    return [bubble_at((i - 2) % n, LINE_X - 2), bubble_at((i - 26) % n, LINE_X + 2)]


def fishing_cast():
    frames = [standing(dock_x=None)] + hop(HOP_ON) + sit_down() + [frame(eyes="open", length=0)]
    # takes the rod out from behind and lifts it
    for angle, length in ((250, 3), (225, 7), (195, 10), (165, 13), (135, 16), (115, 16), (102, 16)):
        frames.append(frame(eyes="open", angle=angle, length=length, right_arm=-1))
    # winds up, leaning back...
    frames += [frame(eyes="open", angle=108, lean=-1, right_arm=-1)] * 3
    # ...and casts: the rod whips forward, the line flies out and drops in
    frames.append(frame(eyes="open", angle=80, right_arm=-1))
    flight = [(54, F - 27), (60, F - 25), (64, F - 20), (65, F - 14), (64, F - 8), (LINE_X, F - 3)]
    for end, angle, lean in zip(flight, (45, 22, 26, 31, 34, 35), (1, 1, 0, 0, 0, 0)):
        frames.append(frame(eyes="stare", angle=angle, lean=lean, line_end=end))
    end = (LINE_X, F)
    frames.append(frame(line_end=end, splash=((LINE_X - 1, F - 2), (LINE_X + 2, F - 3))))
    frames.append(frame(line_end=end, bubbles=[(LINE_X - 1, F - 1, 2), (LINE_X + 2, F - 2, 1)]))
    frames.append(frame(line_end=end, bubbles=[(LINE_X - 1, F - 2, 3), (LINE_X + 2, F - 3, 2)]))
    frames.append(frame(line_end=end, bubbles=[None, (LINE_X + 2, F - 4, 3)]))
    frames += [frame(line_end=end)] * 2
    return clip(frames, FW, FH)


def fishing_wait():
    """A 4 second loop: bubbles come up by the line, the rod sways, Clawd watches and blinks."""
    frames = []
    for i in range(48):
        angle = {24: 36, 25: 37, 26: 38, 27: 38, 28: 37, 29: 36}.get(i, REST)
        eyes = "stare_closed" if i in (36, 37) else "stare"
        frames.append(frame(angle=angle, eyes=eyes, line_end=(LINE_X, F), bubbles=wait_bubbles(i)))
    return clip(frames, FW, FH)


def fishing_stow():
    """Interrupted: reel the line in, put the rod away and leave."""
    frames = [frame(angle=a, eyes="open", line_end=(LINE_X - k, F - 4 * k * k))
              for k, a in enumerate((REST, 45, 55, 65))]
    frames += [frame(angle=70, eyes="open", dangle=3)]
    return clip(frames + put_away(70) + leave(), FW, FH)


def fishing_catch(kind):
    end = (LINE_X, F)
    frames = []
    # a nibble, another, then it bites
    for angle, eyes in ((REST, "stare"), (31, "stare"), (REST, "stare"), (REST, "stare"), (32, "stare"),
                        (30, "stare"), (REST, "stare"), (28, "wide"), (27, "wide")):
        bub = [(LINE_X - 1, F - 1, 2), (LINE_X + 2, F - 2, 1)] if angle < REST else []
        frames.append(frame(angle=angle, eyes=eyes, line_end=end, bubbles=bub))
    frames.append(frame(angle=27, eyes="wide", legs=2, line_end=end,
                        bubbles=[(LINE_X - 1, F - 2, 3), (LINE_X + 2, F - 1, 2)]))  # a startled hop
    # yank! the fish comes out of the taskbar and flies up and lands on the taskbar
    path = [(61, F + 3), (61, F - 4), (60, F - 11), (59, F - 16), (58, F - 19), (57, F - 20),
            (56, F - 19), (55, F - 16), (54, F - 12), (53, F - 8), (52, F - 5), (52, F)]
    angles = [60, 85, 100, 104, 104, 102, 98, 92, 86, 80, 74, 70]
    leans = [-1, -1, -1, -1, 0, 0, 0, 0, 0, 0, 0, 0]
    for k, ((fx, fb), angle, lean) in enumerate(zip(path, angles, leans)):
        splash = ((LINE_X - 2, F - 1), (LINE_X + 2, F - 2)) if k == 1 else ()
        frames.append(frame(angle=angle, lean=lean, eyes="wide", right_arm=-1, hooked=True,
                            fish=(kind, fx, fb, True, False), splash=splash))
    # off the hook: it smacks down on the taskbar and bounces twice
    hops = [0, 2, 4, 5, 5, 4, 2, "squash", 0, 2, 3, 3, 2, "squash", 0, 0, 0]
    for k, h in enumerate(hops):
        squash = h == "squash"
        frames.append(frame(angle=70, eyes="wide" if k < 3 else "open", dangle=4,
                            fish=(kind, 52, F - (0 if squash else h), k < 4, squash)))
    # Clawd is delighted
    for k in range(10):
        frames.append(frame(angle=70, eyes="happy", dangle=4, left_arm=-1 if k % 4 < 2 else 0,
                            fish=(kind, 52, F, False, False)))
    # the fish hops back to where the line was and dives in
    for fx, fb in ((54, F - 6), (56, F - 8), (58, F - 9), (60, F - 8), (61, F - 6), (62, F - 3),
                   (62, F), (63, F + 2), (63, F + 4), (63, F + 6)):
        frames.append(frame(angle=70, eyes="open", dangle=4, fish=(kind, fx, fb, False, False)))
    frames.append(frame(angle=70, eyes="open", dangle=4,
                        splash=((LINE_X - 1, F - 2), (LINE_X + 3, F - 3), (LINE_X + 5, F - 1))))
    frames.append(frame(angle=70, eyes="open", dangle=4, bubbles=[(LINE_X + 1, F - 1, 2)],
                        splash=((LINE_X, F - 3), (LINE_X + 5, F - 2))))
    frames.append(frame(angle=70, eyes="open", dangle=4,
                        bubbles=[(LINE_X + 1, F - 2, 2), (LINE_X + 4, F - 1, 1)]))
    frames.append(frame(angle=70, eyes="open", dangle=4,
                        bubbles=[(LINE_X + 2, F - 3, 3), (LINE_X + 4, F - 2, 2)]))
    frames.append(frame(angle=70, eyes="open", dangle=4, bubbles=[None, (LINE_X + 5, F - 3, 3)]))
    frames += [frame(angle=70, eyes="happy", dangle=d) for d in (3, 2, 1)]
    return clip(frames + put_away(70) + leave(), FW, FH)


if __name__ == "__main__":
    clips = {"Stretching": stretching(), "FishingCast": fishing_cast(), "FishingWait": fishing_wait(),
             "FishingStow": fishing_stow()}
    for kind in FISH:
        clips["FishingCatch-" + kind] = fishing_catch(kind)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(clips, f)
    for n, c in clips.items():
        print(n, "%dx%d" % (c["w"], c["h"]), len(c["frames"]), "frames", "%.1fs" % (len(c["frames"]) / c["fps"]))
