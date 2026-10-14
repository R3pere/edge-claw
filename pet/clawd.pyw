"""Clawd: a tiny desktop pet that walks around the edges of the screen.

Started by the edge-claw mod's button in Claude Code. It reads the mod's
state files to know what Claude is doing: works while any conversation is
working, jumps for joy when a reply lands, dozes after a while of quiet.

Clawd keeps its feet on an edge: along the taskbar, up the right side,
upside down along the top and down the left side, turning at the corners.
Dropped near an edge it clings to it; dropped in the open it falls.

The animations in clawd_sprites.json are Clawd's own pixel sprites, decoded
from the Claude desktop app for personal use.

Left-drag to move, double-click to make it dance, right-click for the menu.
"""

import ctypes
import json
import os
import random
import socket
import sys
import time
import tkinter as tk

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.join(os.path.expanduser("~"), ".claude", "edge-claw")
STATE_FILE = os.path.join(HOME, "state.json")
ALIVE_FILE = os.path.join(HOME, "alive.json")
MEMORY_FILE = os.path.join(HOME, "memory.json")  # what Clawd remembers across days
LOCK_PORT = 47391

# Each Claude session keeps a session-<id>.json there, refreshed every few
# seconds while it works. Clawd works while any of them does.
SESSION_FRESH_S = 30  # a working session silent this long has gone away
SESSION_FORGET_S = 24 * 3600  # files untouched this long are cleared out
BUSY_GRACE_S = 3.0  # rides over a file caught half-written, and between transcript reads

# Sessions that keep no fresh session file (an older mod, or one reloaded in
# the middle of a turn) are read from their transcripts instead: a turn whose
# last word is not Claude's closing answer is still going.
PROJECTS = os.path.join(os.path.expanduser("~"), ".claude", "projects")
TRANSCRIPT_ACTIVE_S = 30 * 60  # a transcript untouched this long is not running
TRANSCRIPT_EVERY_S = 2.0
TRANSCRIPT_TAIL = 256 * 1024

SCALE = 2  # screen pixels per sprite pixel
WIN = 48 * SCALE  # square so every rotation fits, wide enough for the desktop computer
KEY = "#010203"  # the transparent colour
TICK_MS = 40
SLEEP_AFTER_S = 90
CLING_DISTANCE = 80  # a drop this close to an edge clings to it

WALK_SPEED = 0.7  # screen pixels per tick

# Clawd scuttles sideways like a crab. The clip opens on four standing frames;
# [start, end) is the scuttle that repeats, so moving loops only that and the
# feet always move with the body. Running is the same scuttle, faster.
SCUTTLE = "CrabWalking"
SCUTTLE_LOOP = (4, 12)

# Dozing off: the middle of Disappointed, eyes shut and slumped low, swaying a
# little. It sinks down, nods in a loop, and stands back up when woken.
DOZE_OPEN, DOZE_LOOP, DOZE_WAKE = (6, 14), (14, 36), (36, 39)
DOZE_TEMPO = 0.4  # the nodding plays this much slower than the clip, sleepy and calm

# While Claude works, Clawd strolls and stops now and then to think or to lie
# down and code on its laptop. Each pose clip has an opening, a middle that
# loops for as long as the stop lasts, and a closing before it walks on:
# (opening start, loop start, loop end, closing start, closing end).
POSES = {
    "Laptop": (4, 17, 20, 32, 41),
    "Thinking": (4, 4, 37, 37, 38),  # no opening: POSE_LOOPS starts it
    "Lightbulb": (4, 11, 41, 41, 44),
    "Desktop": (3, 16, 78, 78, 85),
}
WORK_POSES = ("Laptop", "Thinking", "Desktop")
# A pose whose middle is not one run of frames loops this sequence instead.
# Thinking has two halves: standing with the bubble on one side (4-5 the
# bubble pops up, 6-19 its dots count one, two, three) and, after a little hop
# (20), crouched with the bubble on the other (21-22 pops up, 23-36 dots).
# Held, each side counts its dots twice before hopping over to the other.
THINK_DOTS = 2
POSE_LOOPS = {
    "Thinking": (4, 5, *tuple(range(6, 20)) * THINK_DOTS, 20,
                 21, 22, *tuple(range(23, 37)) * THINK_DOTS, 20),
}
POSE_HOLD_S = (10.0, 20.0)
WORK_STROLL = 300  # how far it wanders between poses while working (900 when idle)

# Playing with Clawd. Stroke it (move the mouse back and forth over it) and it
# squints happily; click it and it hops, click it too often and it facepalms.
# Rest the cursor near it and it looks at the cursor, then points at it.
PET_REVERSALS = 3  # back-and-forth turns of the mouse over Clawd that count as stroking
PET_WINDOW_S = 1.5
CLICK_MAX_S, CLICK_MAX_MOVE = 0.35, 5  # a press shorter and stiller than this is a click
POKES_TO_FACEPALM, POKE_WINDOW_S = 5, 2.5
WATCH_RADIUS = 170  # how near the resting cursor must be (window pixels)
WATCH_AFTER_S, POINT_AFTER_S = 0.4, 3.0  # how long the cursor rests before each
POINT_OPEN, POINT_LOOP = (6, 20), (20, 33)  # Pointing: raise the claw, then hold it out
DANCES = ("DancingHappy", "Hula", "Swaying", "BreakDancing")

# Idle fidgets: at some of its stops while Claude is quiet, Clawd does a little
# something on its own instead of just looking around. They are not company:
# it still dozes off SLEEP_AFTER_S after anyone last played with it.
IDLE_FIDGETS = {"Meditating": 3, "Swaying": 2, "Jumping": 2, "Excited": 2, "DancingHappy": 1}
IDLE_FIDGET_CHANCE = 0.4

# LookingAroundEyesOnly holds still and moves only the eyes: the frame with the
# eyes shifted by (dx, dy) sprite pixels, dx -1..1 (towards Clawd's front),
# dy -1..2 (down).
EYES = {(0, 0): 0, (1, 0): 6, (1, -1): 9, (0, -1): 12, (-1, -1): 15, (-1, 0): 18,
        (-1, 1): 21, (-1, 2): 24, (0, 2): 27, (0, 1): 27, (1, 2): 30, (1, 1): 33}

# Clawd stands in for Claude's notifications. A permission or a question holds
# up the lightbulb in place until it is answered; a finished task makes Clawd
# jump and wave in place, a warning-yellow "!!!" flashing at the top of each
# jump, until the Claude window is brought to the front (or Clawd is clicked).
ATTENTION_DELAY_S = 1.0  # an ask settled faster than this (by a rule or mode) shows nothing
ACK_AFTER_S = 1.5  # the shortest a finished-task announcement shows
ALERT_YELLOW = "#FFC107"

# Little celebrations. A task that ran this long pops confetti before the
# finished-task alert; the sparkler comes out on the first summon of the day,
# on Friday evenings, and for every few tasks finished in a day.
LONG_TASK_MS = 5 * 60 * 1000
FRIDAY_EVENING_HOUR = 18
SPARK_EVERY_TASKS = 5

# The edges in the order Clawd walks them when it moves forward (facing +1):
# left to right along the bottom, up the right, right to left along the top,
# down the left. Each rotates the sprite so its feet point at that edge.
EDGES = ("bottom", "right", "top", "left")


def work_area():
    """The desktop rectangle without the taskbar: (left, top, right, bottom)."""
    try:
        rect = (ctypes.c_long * 4)()
        ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, rect, 0)  # SPI_GETWORKAREA
        return rect[0], rect[1], rect[2], rect[3]
    except Exception:
        root = tk._default_root
        return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight() - 48


def claude_in_front():
    """True when the window in front belongs to Claude (the desktop app)."""
    try:
        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), ctypes.byref(pid))
        handle = kernel32.OpenProcess(0x1000, False, pid.value)  # QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = ctypes.c_ulong(len(buf))
            if not kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return False
            return os.path.basename(buf.value).lower() == "claude.exe"
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return False


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def read_sessions(now, written=None):
    """The Claude sessions working right now; clears out files long forgotten.

    `written`, when given, collects each session id's file time.
    """
    working = []
    try:
        names = os.listdir(HOME)
    except OSError:
        return working
    for name in names:
        if not (name.startswith("session-") and name.endswith(".json")):
            continue
        path = os.path.join(HOME, name)
        try:
            modified = os.path.getmtime(path)
            if now - modified > SESSION_FORGET_S:
                os.remove(path)
                continue
        except OSError:
            continue
        if written is not None:
            written[name[len("session-"):-len(".json")]] = modified
        session = read_json(path)
        if session.get("status") == "working" and now - session.get("ts", 0) / 1000 < SESSION_FRESH_S:
            working.append(session)
    return working


def turn_open(path):
    """True while the transcript's last turn has not ended."""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - TRANSCRIPT_TAIL))
            tail = f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return False
    for line in reversed(tail):
        try:
            record = json.loads(line)
        except ValueError:
            continue  # cut off by the tail, or half-written
        kind = record.get("type")
        if kind == "system" and record.get("subtype") == "stop_hook_summary":
            return False
        if kind == "assistant":
            return (record.get("message") or {}).get("stop_reason") == "tool_use"
        if kind == "user":
            if record.get("isMeta"):
                continue
            content = (record.get("message") or {}).get("content")
            texts = [c.get("text", "") for c in content if isinstance(c, dict)] if isinstance(content, list) else [content]
            ended = ("[Request interrupted", "<command-name>", "<local-command-")  # Esc, or a slash command
            return not any(isinstance(t, str) and t.lstrip().startswith(ended) for t in texts)
    return True  # nothing readable near the end: a huge tool result, mid-turn


def transcripts_working(now, fresh):
    """How many sessions without a fresh session file are in the middle of a turn."""
    count = 0
    try:
        projects = os.listdir(PROJECTS)
    except OSError:
        return 0
    for project in projects:
        folder = os.path.join(PROJECTS, project)
        try:
            names = os.listdir(folder)
        except OSError:
            continue
        for name in names:
            if not name.endswith(".jsonl"):
                continue
            path = os.path.join(folder, name)
            try:
                modified = os.path.getmtime(path)
            except OSError:
                continue
            if now - modified > TRANSCRIPT_ACTIVE_S:
                continue
            if fresh.get(name[:-len(".jsonl")], 0) >= modified - 15:
                continue  # its session file speaks for it
            if turn_open(path):
                count += 1
    return count


def write_json(path, value):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(value, f)
        os.replace(tmp, path)
    except Exception:
        pass


def rotate(rows, edge):
    """Turns a grid of colours (rows of columns) so the sprite's feet face `edge`."""
    h, w = len(rows), len(rows[0])
    if edge == "bottom":
        return rows
    if edge == "top":
        return [row[::-1] for row in rows[::-1]]
    if edge == "right":  # sprite (x, y) -> (y, w - 1 - x): feet right, forward up
        return [[rows[y][w - 1 - yy] for y in range(h)] for yy in range(w)]
    # left: sprite (x, y) -> (h - 1 - y, x): feet left, forward down
    return [[rows[h - 1 - xx][yy] for xx in range(h)] for yy in range(w)]


def turn(vector, edge):
    """A direction in Clawd's own frame (x forward, y down) as it points on screen."""
    x, y = vector
    return {"bottom": (x, y), "right": (y, -x), "top": (-x, -y), "left": (-y, x)}[edge]


def unturn(vector, edge):
    """A direction on screen as Clawd sees it on `edge` (x forward, y down): turn's inverse."""
    x, y = vector
    return {"bottom": (x, y), "right": (-y, x), "top": (-x, -y), "left": (y, -x)}[edge]


# Text turned the way the sprite is turned (degrees, counter-clockwise).
TEXT_ANGLE = {"bottom": 0, "right": 90, "top": 180, "left": 270}


def rotate_point(x, y, w, h, edge):
    """Where sprite point (x, y) lands once the w x h sprite is rotated for `edge`."""
    if edge == "bottom":
        return x, y
    if edge == "top":
        return w - x, h - y
    if edge == "right":
        return y, w - x
    return h - y, x


class Sprite:
    """One animation. Frames are turned into images on first use, per facing and edge."""

    def __init__(self, data):
        self.w, self.h, self.fps = data["w"], data["h"], data["fps"]
        self.ax, self.ay = data["ax"], data["ay"]
        palette = data["palette"]
        self.rows = []
        self.tops = []  # per frame, the highest painted row: where the head is
        for frame in data["frames"]:
            self.rows.append([
                [KEY if ch == "." else palette[int(ch, 36)] for ch in frame[y * self.w:(y + 1) * self.w]]
                for y in range(self.h)
            ])
            painted = [i // self.w for i, ch in enumerate(frame) if ch != "."]
            self.tops.append(min(painted) if painted else 0)
        self.cache = {}

    def image(self, index, facing, edge):
        key = (index, facing, edge)
        if key not in self.cache:
            rows = self.rows[index]
            if facing < 0:
                rows = [row[::-1] for row in rows]
            rows = rotate(rows, edge)
            img = tk.PhotoImage(width=len(rows[0]), height=len(rows))
            img.put(" ".join("{" + " ".join(row) + "}" for row in rows), to=(0, 0))
            self.cache[key] = img.zoom(SCALE, SCALE)
        return self.cache[key]

    def anchor(self, facing, edge):
        """The feet point in screen pixels inside the rotated, scaled image."""
        ax = self.ax if facing > 0 else self.w - self.ax
        x, y = rotate_point(ax, self.ay, self.w, self.h, edge)
        return x * SCALE, y * SCALE

    def __len__(self):
        return len(self.rows)


class Clawd:
    def __init__(self, root):
        self.root = root
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.configure(bg=KEY)
        root.attributes("-transparentcolor", KEY)
        self.canvas = tk.Canvas(root, width=WIN, height=WIN, bg=KEY, highlightthickness=0)
        self.canvas.pack()

        with open(os.path.join(HERE, "clawd_sprites.json"), "r", encoding="utf-8") as f:
            self.sprites = {name: Sprite(data) for name, data in json.load(f).items()}
        self.image_id = self.canvas.create_image(0, 0, anchor="nw")
        self.zzz_id = self.canvas.create_text(0, 0, text="", fill="#D97757",
                                              font=("Segoe UI", 9, "bold"))

        self.left, self.top, self.right, self.bottom = work_area()
        self.lengths = {
            "bottom": self.right - self.left - WIN,
            "right": self.bottom - self.top - WIN,
            "top": self.right - self.left - WIN,
            "left": self.bottom - self.top - WIN,
        }
        self.loop = sum(self.lengths.values())

        # p is the distance walked along the loop of edges from the bottom-left corner
        self.p = random.uniform(100, self.lengths["bottom"] - 100)
        self.target = self.p
        self.facing = 1
        self.pause_until = time.time() + 2.5
        self.x, self.y = self.position(self.p)
        self.edge = "bottom"
        self.dragging = None
        self.falling = False
        self.vy = 0.0

        self.mode = "idle"  # idle | working | sleep
        self.last_activity = time.time()
        self.anim = None
        self.anim_start = 0.0
        self.oneshot = None  # an animation that plays once over everything else
        self.oneshot_queue = []  # the ones that play after it, in order
        self.done_alert = False  # announcing a finished task until acknowledged
        self.done_since = 0.0
        self.attention = None  # "permission" or "question" while Claude waits on you
        self.attention_since = 0.0
        self.last_fidget = None
        self.busy_seen = 0.0  # when a working session was last seen
        self.transcripts_read = 0.0
        self.legacy_working = False  # state.json itself says "working" (an older mod, dev.ps1)
        self.legacy_attention = None
        self.pose = None  # "Thinking" or "Laptop" while stopped during work
        self.pose_start = 0.0
        self.pose_leaving = None  # when the closing of the pose began
        self.sleep_start = 0.0
        self.wake_start = -1.0  # when it last stood up from a doze
        self.watching = None  # "eyes" or "point" while the resting cursor holds its gaze
        self.watch_start = 0.0
        self.eye_frame = 0
        self.cursor = (0, 0)
        self.cursor_still_since = time.time()
        self.stroke_turns = []  # when the mouse turned back over Clawd, for stroking
        self.stroke_dir = 0
        self.stroke_x = None
        self.pokes = []  # when Clawd was clicked, for the facepalm
        self.press = None  # (time, x, y) of the button press, to tell a click from a drag
        self.memory = read_json(MEMORY_FILE)
        if self.memory.get("firstSummon") != self.today():  # the first time out today
            self.remember("firstSummon", self.today())
            self.play_once("Spark", then=["Waving"])
        else:
            self.play_once("Waving")

        state = read_json(STATE_FILE)
        self.seen_cmd = state.get("cmdId", 0)
        self.seen_ts = state.get("ts", 0)

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Motion>", self.on_hover)
        self.canvas.bind("<Button-3>", self.on_menu)
        self.menu = tk.Menu(root, tearoff=0)
        self.menu.add_command(label="跳舞", command=lambda: self.play_once(random.choice(DANCES)))
        self.menu.add_command(label="挥手", command=lambda: self.play_once("Waving"))
        self.menu.add_command(label="回到任务栏", command=self.go_home)
        self.menu.add_separator()
        self.menu.add_command(label="收起 Clawd", command=self.quit)

        self.place()
        self.tick()
        self.heartbeat()
        self.poll_state()

    # --- the loop of edges -------------------------------------------------

    def wrap(self, p):
        return p % self.loop

    def edge_of(self, p):
        p = self.wrap(p)
        for edge in EDGES:
            if p < self.lengths[edge]:
                return edge, p
            p -= self.lengths[edge]
        return "left", self.lengths["left"]

    def position(self, p):
        """The window's top-left corner for a point on the loop."""
        edge, t = self.edge_of(p)
        if edge == "bottom":
            return self.left + t, self.bottom - WIN
        if edge == "right":
            return self.right - WIN, self.bottom - WIN - t
        if edge == "top":
            return self.right - WIN - t, self.top
        return self.left, self.top + t

    def nearest(self, x, y):
        """The loop point and edge distance closest to a window at (x, y)."""
        x = min(max(x, self.left), self.right - WIN)
        y = min(max(y, self.top), self.bottom - WIN)
        lb, lr, lt = self.lengths["bottom"], self.lengths["right"], self.lengths["top"]
        options = [
            (self.bottom - WIN - y, x - self.left),
            (self.right - WIN - x, lb + (self.bottom - WIN - y)),
            (y - self.top, lb + lr + (self.right - WIN - x)),
            (x - self.left, lb + lr + lt + (y - self.top)),
        ]
        return min(options)

    # --- input -----------------------------------------------------------

    def on_press(self, e):
        self.press = (time.time(), e.x_root, e.y_root, self.done_alert)
        self.done_alert = False  # a click acknowledges a finished task
        self.watching = None
        self.falling = False
        self.wake()

    def on_drag(self, e):
        if not self.press:
            return
        if not self.dragging:
            if abs(e.x_root - self.press[1]) + abs(e.y_root - self.press[2]) < CLICK_MAX_MOVE:
                return  # not moved enough yet to be a drag
            self.dragging = (self.press[1] - self.x, self.press[2] - self.y)
            if self.pose != "Lightbulb":
                self.end_pose()
            self.oneshot, self.oneshot_queue = None, []
        self.x = e.x_root - self.dragging[0]
        self.y = e.y_root - self.dragging[1]
        self.place()

    def on_release(self, _e):
        press, self.press = self.press, None
        if not self.dragging:
            # a click: acknowledges a finished task, or is a poke
            if press and not press[3] and time.time() - press[0] <= CLICK_MAX_S:
                self.poke()
            return
        self.dragging = None
        distance, p = self.nearest(self.x, self.y)
        if distance <= CLING_DISTANCE:
            self.land(p)
        else:
            self.falling = True
            self.vy = 0.0

    def poke(self):
        if self.pose == "Lightbulb":
            return  # it is holding up a question for you; clicks don't distract it
        now = time.time()
        self.pokes = [t for t in self.pokes if now - t < POKE_WINDOW_S] + [now]
        if len(self.pokes) >= POKES_TO_FACEPALM:
            self.pokes = []
            self.play_once("Facepalm")
        elif self.oneshot != "Facepalm":
            self.play_once("Jumping")

    def on_hover(self, e):
        """Moving the mouse back and forth over Clawd strokes it."""
        if self.dragging or self.press:
            return
        now = time.time()
        if self.stroke_x is not None:
            dx = e.x - self.stroke_x
            if abs(dx) >= 3:
                direction = 1 if dx > 0 else -1
                if self.stroke_dir and direction != self.stroke_dir:
                    self.stroke_turns = [t for t in self.stroke_turns if now - t < PET_WINDOW_S] + [now]
                self.stroke_dir = direction
                self.stroke_x = e.x
        else:
            self.stroke_x = e.x
        busy = self.pose == "Lightbulb" or self.done_alert or self.oneshot in ("Excited",) + DANCES
        if len(self.stroke_turns) >= PET_REVERSALS and not busy:
            self.stroke_turns = []
            self.play_once("Excited")

    def on_menu(self, e):
        self.menu.tk_popup(e.x_root, e.y_root)

    def land(self, p):
        self.falling = False
        self.p = self.target = self.wrap(p)
        self.pause_until = time.time() + 1.0
        self.x, self.y = self.position(self.p)
        self.place()

    def go_home(self):
        self.wake()
        self.land(min(max(self.x - self.left, 0), self.lengths["bottom"]))

    # --- behaviour -------------------------------------------------------

    def wake(self):
        self.last_activity = time.time()
        if self.mode == "sleep":
            self.mode = "idle"
            self.wake_start = self.last_activity  # stand back up before anything else

    def play_once(self, name, then=()):
        self.wake()
        self.end_pose()
        self.done_alert = False
        self.oneshot = name
        self.oneshot_queue = list(then)
        self.anim_start = time.time()

    def announce_done(self, duration_ms=0):
        """A task finished: stop and jump and wave, over and over, until acknowledged.

        A long task pops confetti first; every few tasks of the day, the sparkler.
        """
        today = self.today()
        done_today = self.memory.get("doneToday", {})
        count = (done_today.get("n", 0) if done_today.get("date") == today else 0) + 1
        self.remember("doneToday", {"date": today, "n": count})
        if duration_ms >= LONG_TASK_MS:
            first = ["Confetti"]
        elif count % SPARK_EVERY_TASKS == 0:
            first = ["Spark"]
        else:
            first = []
        sequence = first + ["JumpingHappy", "Waving"]
        self.play_once(sequence[0], then=sequence[1:])
        self.done_alert = True
        self.done_since = time.time()

    def friday_evening_spark(self, now):
        """Once on a Friday evening, when Clawd is free, the sparkler comes out."""
        local = time.localtime(now)
        free = (self.mode == "idle" and not self.oneshot and not self.pose and not self.watching
                and not self.done_alert and not self.attention and not self.dragging)
        if (local.tm_wday == 4 and local.tm_hour >= FRIDAY_EVENING_HOUR and free
                and self.memory.get("fridaySpark") != self.today()):
            self.remember("fridaySpark", self.today())
            self.play_once("Spark")

    @staticmethod
    def today():
        return time.strftime("%Y-%m-%d")

    def remember(self, key, value):
        self.memory[key] = value
        write_json(MEMORY_FILE, self.memory)

    def raise_lightbulb(self, now):
        self.wake()
        self.oneshot = None
        self.oneshot_queue = []
        self.done_alert = False
        self.pose = "Lightbulb"
        self.pose_start = now
        self.pose_leaving = None
        self.pause_until = float("inf")  # held until the ask is answered

    def lower_lightbulb(self, now):
        if self.pose == "Lightbulb" and self.pose_leaving is None:
            self.pause_until = now  # the closing plays, then Clawd walks on

    def end_pose(self):
        self.pose = None
        self.pose_leaving = None

    def poll_state(self):
        state = read_json(STATE_FILE)
        cmd = state.get("cmdId", 0)
        if cmd != self.seen_cmd:
            self.seen_cmd = cmd
            if state.get("cmd") == "quit":
                self.quit()
                return
            if state.get("cmd") == "play" and state.get("anim") in self.sprites:
                self.play_once(state["anim"], then=[a for a in state.get("then", []) if a in self.sprites])
            if state.get("cmd") == "pose" and state.get("anim") in POSES:  # hold a pose, for showing it off
                self.wake()
                self.oneshot, self.oneshot_queue, self.done_alert = None, [], False
                self.pose, self.pose_start, self.pose_leaving = state["anim"], time.time(), None
                self.pause_until = time.time() + 20
            if state.get("cmd") == "doze":  # nod off now, for showing it off
                self.end_pose()
                self.oneshot, self.oneshot_queue, self.done_alert = None, [], False
                self.mode, self.sleep_start = "sleep", time.time()
        now = time.time()
        written = {}
        sessions = read_sessions(now, written)
        if sessions:
            self.busy_seen = now
        if now - self.transcripts_read >= TRANSCRIPT_EVERY_S:
            self.transcripts_read = now
            if transcripts_working(now, written):
                self.busy_seen = now
        ts = state.get("ts", 0)
        if ts != self.seen_ts and not state.get("cmd"):  # news from the conversation that spoke last (a cmd is no news)
            self.seen_ts = ts
            status = state.get("status", "idle")
            self.legacy_working = status == "working"
            self.legacy_attention = state.get("attention") if self.legacy_working else None
            self.wake()
            if status == "working":
                self.done_alert = False  # a new turn: the finished one was seen
            elif status == "done":
                self.announce_done(state.get("durationMs") or 0)
            elif status == "interrupted":
                if self.pose != "Lightbulb":  # stopped with Esc, or ended on an error
                    self.play_once("Disappointed")
            elif self.pose != "Lightbulb":
                self.end_pose()
        started = max((s.get("since", 0) for s in sessions), default=0) / 1000
        if self.done_alert and started > self.done_since:
            self.done_alert = False  # a new turn began: the finished one was seen

        kinds = [s.get("attention") for s in sessions] + [self.legacy_attention]
        attention = "question" if "question" in kinds else "permission" if "permission" in kinds else None
        if attention != self.attention:
            self.wake()
            self.attention = attention
            self.attention_since = now
            if attention is None:
                self.lower_lightbulb(now)

        busy = self.legacy_working or now - self.busy_seen < BUSY_GRACE_S
        if busy and self.mode != "working":
            self.wake()
            if self.pose != "Lightbulb" and not self.oneshot:
                self.end_pose()
                self.pause_until = 0.0
            self.mode = "working"
        elif not busy and self.mode == "working":
            self.mode = "idle"
            self.last_activity = now
            if self.pose in WORK_POSES and self.pose_leaving is None:
                self.pause_until = now  # finish the pose's closing, then stroll
        if self.done_alert and now - self.done_since >= ACK_AFTER_S and claude_in_front():
            self.done_alert = False  # seen: finish this jump or wave, then walk on
        self.friday_evening_spark(now)
        self.root.after(400, self.poll_state)

    def heartbeat(self):
        write_json(ALIVE_FILE, {"ts": int(time.time() * 1000), "pid": os.getpid()})
        self.root.after(1000, self.heartbeat)

    def choose_anim(self, now):
        while self.oneshot:
            sprite = self.sprites[self.oneshot]
            if (now - self.anim_start) * sprite.fps < len(sprite):
                return self.oneshot
            if self.oneshot_queue:
                self.oneshot = self.oneshot_queue.pop(0)
            elif self.done_alert:
                self.oneshot, self.oneshot_queue = "JumpingHappy", ["Waving"]
            else:
                self.oneshot = None
            self.anim_start = now
        if self.dragging or self.falling:
            return "Dizzy"
        if self.mode == "sleep":
            return "Disappointed"  # dozing (see frame_index)
        if self.waking(now):
            return "Disappointed"
        if self.pose:
            return self.pose
        if self.watching:
            return "Pointing" if self.watching == "point" else "LookingAroundEyesOnly"
        moving = now >= self.pause_until and abs(self.target - self.p) > 0.5
        return SCUTTLE if moving else "LookingAround"

    def waking(self, now):
        return 0 <= now - self.wake_start < (DOZE_WAKE[1] - DOZE_WAKE[0]) / 12

    def update_watch(self, now):
        """Looks at a cursor resting nearby, then points at it; lets go when it moves off."""
        px, py = self.root.winfo_pointerxy()
        if (px, py) != self.cursor:
            self.cursor, self.cursor_still_since = (px, py), now
        free = (self.mode == "idle" and not self.oneshot and not self.pose and not self.dragging
                and not self.falling and not self.done_alert and not self.attention)
        vx, vy = px - (self.x + WIN / 2), py - (self.y + WIN / 2)
        over = 0 <= px - self.x < WIN and 0 <= py - self.y < WIN  # on Clawd: that's stroking
        near = (vx * vx + vy * vy) ** 0.5 <= WATCH_RADIUS
        rested = now - self.cursor_still_since
        if not (free and near and not over and rested >= WATCH_AFTER_S):
            if self.watching:
                self.watching = None
                self.pause_until = now + 0.6
            return
        fx, fy = unturn((vx, vy), self.edge)  # the cursor as Clawd sees it
        if self.watching != "point" and rested >= POINT_AFTER_S:
            self.watching, self.watch_start = "point", now
            self.facing = 1 if fx >= 0 else -1  # turn to the cursor, claw first
        elif self.watching is None:
            self.watching, self.watch_start = "eyes", now
        if self.watching == "eyes":
            length = max((fx * fx + fy * fy) ** 0.5, 1)
            ux, uy = fx / length, fy / length
            dx = (1 if ux > 0.38 else -1 if ux < -0.38 else 0) * self.facing  # the sprite may be mirrored
            dy = -1 if uy < -0.35 else 2 if uy > 0.8 else 1 if uy > 0.35 else 0
            self.eye_frame = EYES[(dx, dy)]
        self.pause_until = max(self.pause_until, now + 0.3)

    def pick_target(self, now):
        span = WORK_STROLL if self.mode == "working" else 900
        self.target = self.p + random.uniform(-span, span)
        if self.mode == "working":
            self.pose = random.choice(WORK_POSES)
            self.pose_start = now
            self.pose_leaving = None
            self.pause_until = now + random.uniform(*POSE_HOLD_S)
        else:
            self.pause_until = now + random.uniform(2.0, 6.0)
            if random.random() < IDLE_FIDGET_CHANCE:
                self.fidget(now)

    def fidget(self, now):
        """Does one idle fidget, never the same twice running, without waking anything."""
        choices = {n: w for n, w in IDLE_FIDGETS.items() if n in self.sprites and n != self.last_fidget}
        if not choices:
            return
        self.last_fidget = random.choices(list(choices), weights=list(choices.values()))[0]
        self.oneshot, self.oneshot_queue, self.anim_start = self.last_fidget, [], now

    def pose_done(self, now):
        """Moves a pose on to its closing once the stop is over; True when it has ended."""
        if not self.pose:
            return True
        if self.pose_leaving is None:
            if now < self.pause_until:
                return False
            self.pose_leaving = now
        _, _, _, close_start, close_end = POSES[self.pose]
        if (now - self.pose_leaving) * self.sprites[self.pose].fps >= close_end - close_start:
            self.end_pose()
            return True
        return False

    def tick(self):
        now = time.time()
        bulb_up = self.pose == "Lightbulb" and self.pose_leaving is None
        if (self.attention and not bulb_up and not self.dragging and not self.falling
                and now - self.attention_since >= ATTENTION_DELAY_S):
            self.raise_lightbulb(now)
        if self.mode == "idle" and not self.oneshot and now - self.last_activity > SLEEP_AFTER_S:
            self.mode = "sleep"
            self.sleep_start = now
        self.update_watch(now)

        if self.falling:
            self.vy += 0.9
            self.y += self.vy
            if self.y >= self.bottom - WIN:
                self.land(min(max(self.x - self.left, 0), self.lengths["bottom"]))
            else:
                self.place()
        elif not self.dragging:
            can_move = (self.mode in ("idle", "working") and not self.oneshot and not self.watching
                        and not self.waking(now))
            if can_move and now >= self.pause_until and self.pose_done(now):
                speed = WALK_SPEED
                if abs(self.target - self.p) <= speed:
                    self.p = self.target
                    self.pick_target(now)
                else:
                    self.facing = 1 if self.target > self.p else -1
                    self.p += speed * self.facing
                # keep p and target in one lap so wrapping stays seamless
                if self.p >= self.loop or self.p < 0:
                    shift = self.loop if self.p >= self.loop else -self.loop
                    self.p -= shift
                    self.target -= shift
                self.x, self.y = self.position(self.p)
            self.edge = self.edge_of(self.p)[0]
            self.place()

        self.draw(now)
        self.root.after(TICK_MS, self.tick)

    # --- drawing ---------------------------------------------------------

    def place(self):
        self.root.geometry(f"{WIN}x{WIN}+{int(self.x)}+{int(self.y)}")

    def frame_index(self, name, now):
        sprite = self.sprites[name]
        fps = sprite.fps
        if name == SCUTTLE:
            start, end = SCUTTLE_LOOP
            return start + int((now - self.anim_start) * fps) % (end - start)
        if name == self.pose:
            open_start, loop_start, loop_end, close_start, close_end = POSES[name]
            if self.pose_leaving is not None:
                n = int((now - self.pose_leaving) * fps)
                return min(close_start + n, close_end - 1)
            n = int((now - self.pose_start) * fps)
            if n < loop_start - open_start:
                return open_start + n
            n -= loop_start - open_start
            if name in POSE_LOOPS:
                loop = POSE_LOOPS[name]
                return loop[n % len(loop)]
            return loop_start + n % (loop_end - loop_start)
        if name == "Disappointed" and self.oneshot != "Disappointed":  # dozing, not disappointed
            if self.mode == "sleep":
                (open_start, open_end), (loop_start, loop_end) = DOZE_OPEN, DOZE_LOOP
                t = now - self.sleep_start
                opening = (open_end - open_start) / fps
                if t < opening:
                    return open_start + int(t * fps)
                return loop_start + int((t - opening) * fps * DOZE_TEMPO) % (loop_end - loop_start)
            n = int((now - self.wake_start) * fps)
            return min(DOZE_WAKE[0] + n, DOZE_WAKE[1] - 1)
        if self.watching and name == "LookingAroundEyesOnly":
            return self.eye_frame
        if self.watching and name == "Pointing":
            n = int((now - self.watch_start) * fps)
            (open_start, open_end), (loop_start, loop_end) = POINT_OPEN, POINT_LOOP
            if n < open_end - open_start:
                return open_start + n
            return loop_start + (n - (open_end - open_start)) % (loop_end - loop_start)
        return int((now - self.anim_start) * fps) % len(sprite)

    def draw(self, now):
        name = self.choose_anim(now)
        if name != self.anim and name != self.oneshot:
            self.anim = name
            self.anim_start = now
        elif name == self.oneshot:
            self.anim = name
        sprite = self.sprites[name]
        # while held or falling Clawd is upright; otherwise its feet face its edge
        edge = "bottom" if (self.dragging or self.falling) else self.edge
        index = self.frame_index(name, now)
        image = sprite.image(index, self.facing, edge)
        fx, fy = sprite.anchor(self.facing, edge)
        # put the feet on the middle of the window side that touches the edge
        foot = {"bottom": (WIN / 2, WIN), "top": (WIN / 2, 0),
                "right": (WIN, WIN / 2), "left": (0, WIN / 2)}[edge]
        self.canvas.coords(self.image_id, foot[0] - fx, foot[1] - fy)
        self.canvas.itemconfigure(self.image_id, image=image)

        # A word over the head, turned with Clawd so it keeps its place on every
        # edge: a yellow "!!!" right above the head at the top of each jump while
        # announcing a finished task (so it flashes), "zZZ" up front while asleep.
        up = turn((0, -1), edge)
        ahead = turn((self.facing, 0), edge)
        at_top = name == "JumpingHappy" and sprite.tops[index] <= min(sprite.tops) + 1
        if self.done_alert and at_top:
            head = (sprite.ay - sprite.tops[index]) * SCALE
            text, lift, shift, size, colour = "!!!", head + 9, 0, 12, ALERT_YELLOW
        elif self.mode == "sleep" and name == "Disappointed":
            # up and to Clawd's own right (whichever way it last walked), just off the head
            ahead = turn((1, 0), edge)
            head = (sprite.ay - sprite.tops[index]) * SCALE  # it sinks as it dozes off
            text, lift, shift, size, colour = ("z" + "Z" * (int(now * 1.5) % 3),
                                               head + 6, 11 * SCALE, 9, "#D97757")
        else:
            text = None
        if text:
            self.canvas.coords(self.zzz_id, foot[0] + up[0] * lift + ahead[0] * shift,
                               foot[1] + up[1] * lift + ahead[1] * shift)
            self.canvas.itemconfigure(self.zzz_id, text=text, angle=TEXT_ANGLE[edge], fill=colour,
                                      font=("Segoe UI", size, "bold"))
        else:
            self.canvas.itemconfigure(self.zzz_id, text="")

    def quit(self):
        try:
            os.remove(ALIVE_FILE)
        except Exception:
            pass
        self.root.destroy()


def main():
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(("127.0.0.1", LOCK_PORT))
    except OSError:
        return  # another Clawd is already out
    os.makedirs(HOME, exist_ok=True)
    root = tk.Tk()
    root.title("Clawd")
    Clawd(root)
    root.mainloop()
    lock.close()


if __name__ == "__main__":
    sys.exit(main())
