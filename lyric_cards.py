import ctypes
import math
import random
import re
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
import pygame
import time

BASE_DIR = Path(__file__).resolve().parent
AUDIO_FILE = BASE_DIR / "sway.mp3"
LRC_FILE = BASE_DIR / "Lyrics Colorcode - Sway (feat. Sekar Agny).lrc"
LYRICS = []
LRC_LINE = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\](.*)")


def find_lrc():
    if LRC_FILE.is_file():
        return LRC_FILE
    matches = sorted(BASE_DIR.glob("*.lrc"))
    return matches[0] if matches else LRC_FILE


def load_lyrics(path):
    lyrics = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = LRC_LINE.search(line)
        if not match:
            continue
        minutes = int(match.group(1))
        seconds = float(match.group(2))
        text = match.group(3).strip()
        if not text:
            continue
        lyrics.append((minutes * 60 + seconds, text))
    return lyrics

BOX_W, BOX_H = 350, 220
FONT = ("Helvetica", 25, "bold")
BG_COLOR = "#fdfdf5"
FG_COLOR = "#111111"
ACCENT_COLOR = "#7c3aed"
ACCENT_SOFT = "#c4b5fd"
BORDER = 8
RISE_TRAVEL = 210
STAGE_COLOR = "#010102"
MOON_COLORS = ("#fbf6ec", "#f4e6c4", "#f3eefb")
STAR_COLORS = ("#fffaf2", "#f8e7c2", "#f6d5e4", "#e7def8")

def phrase_duration(index):
    if index + 1 < len(LYRICS):
        gap = LYRICS[index + 1][0] - LYRICS[index][0]
    else:
        gap = 6.6
    return max(1.25, min(gap, 8.0))

def estimate_beat(lyrics):
    gaps = [lyrics[i + 1][0] - lyrics[i][0] for i in range(len(lyrics) - 1)]
    chorus = [gap for gap in gaps if 6.2 <= gap <= 7.4]
    if len(chorus) >= 4:
        return sum(chorus) / len(chorus) / 8
    usable = [gap for gap in gaps if 3.0 <= gap <= 9.0]
    if not usable:
        return 60 / 72
    usable.sort()
    return usable[len(usable) // 2] / 8

def mix_hex(start, end, amount):
    amount = max(0.0, min(1.0, amount))
    a = tuple(int(start[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(end[i:i + 2], 16) for i in (1, 3, 5))
    mixed = tuple(int(a[i] + (b[i] - a[i]) * amount) for i in range(3))
    return "#{:02x}{:02x}{:02x}".format(*mixed)

def make_clickthrough(window):
    window.update_idletasks()
    hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
    get_long = ctypes.windll.user32.GetWindowLongPtrW
    set_long = ctypes.windll.user32.SetWindowLongPtrW
    get_long.restype = ctypes.c_ssize_t
    get_long.argtypes = [ctypes.c_void_p, ctypes.c_int]
    set_long.restype = ctypes.c_ssize_t
    set_long.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
    style = get_long(hwnd, -20)
    set_long(hwnd, -20, style | 0x00080000 | 0x00000020)

def star_points(x, y, outer, rotation):
    points = []
    for i in range(8):
        angle = rotation + i * math.pi / 4
        radius = outer if i % 2 == 0 else outer * 0.36
        points.extend((x + math.cos(angle) * radius, y + math.sin(angle) * radius))
    return points

class Stage:
    def __init__(self, root, width, height):
        self.width = width
        self.height = height
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-transparentcolor", STAGE_COLOR)
        self.win.geometry(f"{width}x{height}+0+0")
        self.win.configure(bg=STAGE_COLOR)
        self.canvas = tk.Canvas(
            self.win,
            width=width,
            height=height,
            bg=STAGE_COLOR,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack()
        make_clickthrough(self.win)
        self.moons = [
            {"x": width * 0.16, "y": height * 0.18, "r": 84, "phase": 0.5, "drift": 0.12, "amp": 16, "color": MOON_COLORS[0]},
            {"x": width * 0.80, "y": height * 0.34, "r": 48, "phase": 2.1, "drift": 0.09, "amp": 12, "color": MOON_COLORS[1]},
            {"x": width * 0.58, "y": height * 0.74, "r": 30, "phase": 3.8, "drift": 0.14, "amp": 10, "color": MOON_COLORS[2]},
        ]
        self.stars = [
            {
                "x": random.uniform(12, width - 12),
                "y": random.uniform(12, height - 12),
                "r": random.choice((2.2, 2.6, 3.2, 4.4, 6.5, 8.5)),
                "speed": random.uniform(4, 12),
                "phase": random.uniform(0, math.tau),
                "color": random.choice(STAR_COLORS),
            }
            for _ in range(42)
        ]
        self.shooting = []

    def burst(self, x, y):
        angle = random.uniform(-2.55, -0.75)
        speed = random.uniform(180, 280)
        self.shooting.append({
            "x": x,
            "y": y,
            "vx": math.cos(angle) * speed,
            "vy": math.sin(angle) * speed,
            "age": 0.0,
            "life": 1.25,
            "r": random.uniform(6, 9),
            "color": random.choice(STAR_COLORS),
        })
        if len(self.shooting) > 6:
            self.shooting = self.shooting[-6:]

    def draw_star(self, x, y, outer, rotation, color):
        if outer < 1.2:
            return
        self.canvas.create_polygon(
            star_points(x, y, outer, rotation),
            fill=color,
            outline="",
            tags="fx",
        )

    def draw_moon(self, x, y, radius, opening, color):
        self.canvas.create_oval(
            x - radius, y - radius, x + radius, y + radius,
            fill=color, outline="", tags="fx",
        )
        cut = radius * 0.84
        ox = math.cos(opening) * radius * 0.46
        oy = math.sin(opening) * radius * 0.22
        self.canvas.create_oval(
            x + ox - cut, y + oy - cut, x + ox + cut, y + oy + cut,
            fill=STAGE_COLOR, outline="", tags="fx",
        )

    def draw(self, elapsed, beat, dt):
        self.canvas.delete("fx")
        for moon in self.moons:
            phase = elapsed * moon["drift"] + moon["phase"]
            x = moon["x"] + math.sin(phase) * moon["amp"]
            y = moon["y"] + math.cos(phase * 0.65) * moon["amp"] * 0.4
            self.draw_moon(x, y, moon["r"], moon["phase"] + elapsed * 0.08, moon["color"])
        for star in self.stars:
            twinkle = 0.7 + 0.3 * math.sin(elapsed / max(beat, 0.2) + star["phase"])
            star["y"] -= star["speed"] * dt
            star["x"] += math.sin(elapsed * 0.22 + star["phase"]) * 6 * dt
            if star["y"] < -14:
                star["y"] = self.height + 10
                star["x"] = random.uniform(12, self.width - 12)
            self.draw_star(
                star["x"], star["y"], star["r"] * twinkle,
                star["phase"] + elapsed * 0.12, star["color"],
            )
        alive = []
        for shot in self.shooting:
            shot["age"] += dt
            if shot["age"] >= shot["life"]:
                continue
            shot["x"] += shot["vx"] * dt
            shot["y"] += shot["vy"] * dt
            fade = 1 - shot["age"] / shot["life"]
            for i in range(5):
                trail = i / 5
                self.draw_star(
                    shot["x"] - shot["vx"] * 0.045 * i,
                    shot["y"] - shot["vy"] * 0.045 * i,
                    shot["r"] * fade * (1 - trail * 0.7),
                    shot["age"] * 2,
                    shot["color"],
                )
            alive.append(shot)
        self.shooting = alive

    def close(self):
        try:
            self.win.destroy()
        except tk.TclError:
            pass

class LyricCard:
    def __init__(self, parent, text, x, y, born, duration):
        self.win = tk.Toplevel(parent)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=ACCENT_COLOR)
        self.win.geometry(f"{BOX_W}x{BOX_H}+{int(x)}+{int(y)}")
        self.win.resizable(False, False)
        self.full_text = text
        self.born = born
        self.span = duration
        self.deadline = born + duration
        self.fade_at = self.deadline - min(0.7, duration * 0.28)
        self.base_x = x
        self.base_y = float(y)
        self.reveal_time = 0.0 if len(text) <= 18 or duration < 2.6 else min(1.35, duration * 0.38)
        self.shown = -1
        self.alpha = -1.0
        self.placed = None
        self.border_at = -1.0
        inner = tk.Frame(self.win, bg=BG_COLOR)
        inner.pack(expand=True, fill="both", padx=BORDER, pady=BORDER)
        self.label = tk.Label(
            inner,
            text="",
            font=FONT,
            bg=BG_COLOR,
            fg=FG_COLOR,
            wraplength=BOX_W - 25 - BORDER * 2,
            justify="center"
        )
        self.label.pack(expand=True, fill="both", padx=15, pady=15)
        self.win.attributes("-alpha", 0.0)

    def handoff(self, elapsed):
        self.fade_at = min(self.fade_at, elapsed)
        self.deadline = min(self.deadline, elapsed + 0.38)

    def reveal(self, age):
        if self.reveal_time <= 0:
            count = len(self.full_text)
        else:
            count = int(len(self.full_text) * min(1.0, age / self.reveal_time))
            if age > 0.04:
                count = max(1, count)
        if count == self.shown:
            return True
        self.shown = count
        try:
            self.label.config(text=self.full_text[:count])
        except tk.TclError:
            return False
        return True

    def step(self, elapsed, beat):
        if elapsed >= self.deadline:
            return False
        age = max(0.0, elapsed - self.born)
        if not self.reveal(age):
            return False
        progress = max(0.0, min(age / self.span, 1.0))
        eased = 1 - (1 - progress) ** 2
        x = self.base_x
        y = self.base_y - RISE_TRAVEL * eased
        if elapsed < self.born + 0.28:
            alpha = (elapsed - self.born) / 0.28
        elif elapsed > self.fade_at:
            fade_len = max(0.2, self.deadline - self.fade_at)
            alpha = max(0.0, (self.deadline - elapsed) / fade_len)
        else:
            alpha = 1.0
        alpha = max(0.0, min(1.0, alpha))
        if abs(alpha - self.alpha) >= 0.04:
            self.alpha = alpha
            self.win.attributes("-alpha", alpha)
        if elapsed - self.border_at >= 0.16:
            self.border_at = elapsed
            pulse = 0.5 + 0.5 * math.sin(elapsed / beat * math.tau)
            self.win.configure(bg=mix_hex(ACCENT_COLOR, ACCENT_SOFT, 0.35 + 0.65 * pulse))
        placed = (int(x), int(y))
        if placed != self.placed:
            self.placed = placed
            self.win.geometry(f"{BOX_W}x{BOX_H}+{placed[0]}+{placed[1]}")
        return True

    def close(self):
        try:
            self.win.destroy()
        except tk.TclError:
            pass

class LyricFloatApp:
    def __init__(self, root):
        self.root = root
        self.screen_w = root.winfo_screenwidth()
        self.screen_h = root.winfo_screenheight()
        self.next_lyric_idx = 0
        self.boxes = []
        self.last_frame_time = None
        self.beat = estimate_beat(LYRICS)
        self.stage = None
        self.start()

    def spawn_x(self):
        return max(24, (self.screen_w - BOX_W) // 2)

    def spawn_y(self):
        center_y = (self.screen_h - BOX_H) // 2
        return center_y + RISE_TRAVEL // 2

    def start(self):
        self.root.iconify()
        self.stage = Stage(self.root, self.screen_w, self.screen_h)
        self.start_time = time.time()
        self.last_frame_time = self.start_time
        pygame.mixer.init()
        pygame.mixer.music.load(str(AUDIO_FILE))
        pygame.mixer.music.play()
        self.tick()

    def tick(self):
        now = time.time()
        elapsed = now - self.start_time
        dt = min(0.05, now - self.last_frame_time)
        self.last_frame_time = now
        due = []
        while (self.next_lyric_idx < len(LYRICS) and
               LYRICS[self.next_lyric_idx][0] <= elapsed):
            due.append(self.next_lyric_idx)
            self.next_lyric_idx += 1
        if len(due) > 2:
            due = due[-2:]
        for index in due:
            for box in self.boxes:
                box.handoff(elapsed)
            _t, text = LYRICS[index]
            x = self.spawn_x()
            y = self.spawn_y()
            duration = phrase_duration(index)
            box = LyricCard(self.root, text, x, y, elapsed, duration)
            box.win.lift()
            self.boxes.append(box)
            self.stage.burst(x + BOX_W / 2, y + BOX_H / 2)
        self.stage.draw(elapsed, self.beat, dt)
        still_visible = []
        for box in self.boxes:
            if box.step(elapsed, self.beat):
                still_visible.append(box)
            else:
                box.close()
        self.boxes = still_visible
        music_on = pygame.mixer.music.get_busy()
        if music_on or self.next_lyric_idx < len(LYRICS) or self.boxes:
            self.root.after(16, self.tick)
        else:
            self.stage.close()
            self.root.destroy()

def show_error(message):
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("Sway", message)
    root.destroy()


if __name__ == "__main__":
    lrc_path = find_lrc()
    if not AUDIO_FILE.is_file():
        show_error(
            "Letakkan sway.mp3 di folder yang sama dengan lyric_cards.py.\n"
            "Pakai file yang kamu miliki secara legal."
        )
    elif not lrc_path.is_file():
        show_error(
            "Letakkan file lirik .lrc di folder yang sama.\n"
            "Nama yang dicari: Lyrics Colorcode - Sway (feat. Sekar Agny).lrc"
        )
    else:
        LYRICS = load_lyrics(lrc_path)
        if not LYRICS:
            show_error("File .lrc terbaca, tapi tidak ada baris lirik berwaktu.")
        else:
            root = tk.Tk()
            app = LyricFloatApp(root)
            root.mainloop()
