"""The launcher window: sign in, make a character, press Play.

Tkinter keeps Fanxi dependency-free: macOS, Linux and Windows all have it, and the whole launcher
is one Python process. Long work (HTTP, building host64) runs on threads and reports back through
a queue, so the window never freezes.
"""
from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import APP_NAME, __version__
from .api import ApiError, FanxiApi, NetworkError
from .config import LauncherConfig
from .game import GameError, GameManager, find_game_dir, find_host64, is_game_dir

BG = "#07111f"
PANEL = "#0c1b2c"
PANEL_2 = "#12263d"
PANEL_3 = "#17324e"
BORDER = "#1d3a56"
TEXT = "#eaf6ff"
MUTED = "#8da7be"
ACCENT = "#59d8f2"
ACCENT_DARK = "#1d8ba8"
GOLD = "#ffd166"
DANGER = "#ff7b72"
GREEN = "#5be49b"

RACES = [
    ("Hume male", 1), ("Hume female", 2), ("Elvaan male", 3), ("Elvaan female", 4),
    ("Tarutaru male", 5), ("Tarutaru female", 6), ("Mithra", 7), ("Galka", 8),
]
NATIONS = [("San d'Oria", 0), ("Bastok", 1), ("Windurst", 2)]
JOBS = [
    ("Warrior", 1), ("Monk", 2), ("White Mage", 3), ("Black Mage", 4), ("Red Mage", 5),
    ("Thief", 6), ("Paladin", 7), ("Dark Knight", 8), ("Beastmaster", 9), ("Bard", 10),
    ("Ranger", 11), ("Samurai", 12), ("Ninja", 13), ("Dragoon", 14), ("Summoner", 15),
    ("Blue Mage", 16), ("Corsair", 17), ("Puppetmaster", 18), ("Dancer", 19), ("Scholar", 20),
    ("Geomancer", 21), ("Rune Fencer", 22),
]
SIZES = [("Small", 0), ("Medium", 1), ("Large", 2)]
ZONES = {
    50: "Aht Urhgan Whitegate", 100: "West Ronfaure", 230: "Southern San d'Oria",
    231: "Northern San d'Oria", 232: "Port San d'Oria", 236: "Port Bastok",
    246: "Port Jeuno", 248: "Ru'Lude Gardens",
}


def race_name(value: int) -> str:
    return next((name for name, v in RACES if v == value), "Adventurer")


def nation_name(value: int) -> str:
    return next((name for name, v in NATIONS if v == value), "—")


def job_name(value: int) -> str:
    return next((name for name, v in JOBS if v == value), "Adventurer")


def size_name(value: int) -> str:
    return next((name for name, v in SIZES if v == value), "Medium")


def pretty_date(value: str | None) -> str:
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return dt.strftime("%b %-d, %Y") if os.name != "nt" else dt.strftime("%b %d, %Y")


def _font_family(root) -> str:
    import tkinter.font as tkfont
    families = set(tkfont.families(root))
    for name in ("SF Pro Display", "SF Pro Text", "Helvetica Neue", "Segoe UI", "Inter", "DejaVu Sans"):
        if name in families:
            return name
    return "TkDefaultFont"


def _mono_family(root) -> str:
    import tkinter.font as tkfont
    families = set(tkfont.families(root))
    for name in ("SF Mono", "Menlo", "Consolas", "DejaVu Sans Mono", "Courier New"):
        if name in families:
            return name
    return "TkFixedFont"


class ActionButton(tk.Frame):
    def __init__(self, parent, text, command, *, kind="primary", font=None, padx=20, pady=11):
        if kind == "primary":
            bg, fg, hover = ACCENT, "#05202c", "#8be9fb"
        elif kind == "ghost":
            bg, fg, hover = PANEL_2, TEXT, PANEL_3
        else:
            bg, fg, hover = PANEL_2, MUTED, PANEL_3
        super().__init__(parent, bg=bg, cursor="hand2", highlightthickness=0)
        self.command = command
        self.bg, self.hover = bg, hover
        self.label = tk.Label(self, text=text, bg=bg, fg=fg, font=font, padx=padx, pady=pady, cursor="hand2")
        self.label.pack()
        for widget in (self, self.label):
            widget.bind("<Button-1>", self._click)
            widget.bind("<Enter>", self._enter)
            widget.bind("<Leave>", self._leave)

    def _click(self, _event):
        if self.command:
            self.command()

    def _enter(self, _event):
        self.configure(bg=self.hover)
        self.label.configure(bg=self.hover)

    def _leave(self, _event):
        self.configure(bg=self.bg)
        self.label.configure(bg=self.bg)

    def set_text(self, text: str) -> None:
        self.label.configure(text=text)


class LinkButton(tk.Label):
    def __init__(self, parent, text, command, *, bg=PANEL, fg=ACCENT):
        super().__init__(parent, text=text, bg=bg, fg=fg, cursor="hand2", font=("TkDefaultFont", 10, "underline"))
        self.command = command
        self.bind("<Button-1>", lambda _e: self.command())


class ScrollFrame(tk.Frame):
    """A canvas-backed frame that scrolls with the wheel over its contents."""

    def __init__(self, parent, bg=BG):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll.pack(side="right", fill="y")
        self.inner.bind("<Configure>", self._configure)
        self.canvas.bind("<Enter>", self._bind_wheel)
        self.canvas.bind("<Leave>", self._unbind_wheel)

    def _configure(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.canvas.itemconfigure(self.window, width=self.canvas.winfo_width())

    def _bind_wheel(self, _event):
        self.canvas.bind_all("<MouseWheel>", self._wheel)
        self.canvas.bind_all("<Button-4>", self._wheel)
        self.canvas.bind_all("<Button-5>", self._wheel)

    def _unbind_wheel(self, _event):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _wheel(self, event):
        if getattr(event, "num", None) == 4:
            delta = -1
        elif getattr(event, "num", None) == 5:
            delta = 1
        else:
            delta = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(delta, "units")


class LauncherApp(tk.Tk):
    def __init__(self, config: LauncherConfig | None = None):
        super().__init__()
        self.config = config or LauncherConfig.load()
        insecure = os.environ.get("FANXI_API_INSECURE", "") in ("1", "true", "yes")
        self.api = FanxiApi(self.config.api_url, insecure=insecure)
        self.game = GameManager(self.config)
        self.account: dict | None = None
        self.characters: list[dict] = []
        self.server_status: dict | None = None
        self.news: list[dict] = []
        self.page = "home"
        self.build_log = None
        self._jobs: queue.Queue = queue.Queue()
        self._busy = False
        self._building = False
        self._nav_buttons: dict[str, dict] = {}

        self.title(APP_NAME)
        self.configure(bg=BG)
        self.geometry("1040x700")
        self.minsize(900, 620)
        self.font = _font_family(self)
        self.mono = _mono_family(self)
        self._set_icon()
        self._build_shell()
        self._poll_jobs()
        self.after(60, self._startup)

    # --- shell ---------------------------------------------------------------------------------
    def _set_icon(self):
        assets = Path(self.game.root) / "assets"
        for name, subsample in (("icon.png", 16), ("icon.gif", 1)):
            try:
                image = tk.PhotoImage(file=str(assets / name))
                self._icon_full = image
                self._icon = image.subsample(subsample, subsample)
                self.iconphoto(True, self._icon)
                return
            except Exception:
                continue
        self._icon = None

    def _build_shell(self):
        sidebar = tk.Frame(self, bg=PANEL, width=232)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        self.sidebar = sidebar

        brand = tk.Frame(sidebar, bg=PANEL, padx=24, pady=26)
        brand.pack(fill="x")
        if self._icon is not None:
            tk.Label(brand, image=self._icon, bg=PANEL).pack(anchor="w")
        tk.Label(brand, text="FANXI", bg=PANEL, fg=TEXT, font=(self.font, 25, "bold")).pack(anchor="w", pady=(14, 0))
        tk.Label(brand, text="L A U N C H E R", bg=PANEL, fg=MUTED, font=(self.font, 8)).pack(anchor="w", pady=(2, 0))

        nav = tk.Frame(sidebar, bg=PANEL, padx=12)
        nav.pack(fill="x", pady=(10, 0))
        for name, label in (("home", "Home"), ("character", "Character"), ("news", "News"),
                            ("settings", "Settings")):
            self._nav_buttons[name] = self._nav_button(nav, name, label)

        self.sidebar_bottom = tk.Frame(sidebar, bg=PANEL, padx=22, pady=20)
        self.sidebar_bottom.pack(side="bottom", fill="x")
        self.account_label = tk.Label(self.sidebar_bottom, text="Not signed in", bg=PANEL, fg=MUTED,
                                      font=(self.font, 10), anchor="w")
        self.account_label.pack(fill="x")
        self.signout_link = LinkButton(self.sidebar_bottom, "Sign out", self.sign_out, bg=PANEL, fg=MUTED)
        self.signout_link.pack(anchor="w", pady=(6, 0))

        main = tk.Frame(self, bg=BG)
        main.pack(side="left", fill="both", expand=True)
        self.main = main

        top = tk.Frame(main, bg=BG, padx=30, pady=20)
        top.pack(fill="x")
        self.page_title = tk.Label(top, text="Home", bg=BG, fg=TEXT, font=(self.font, 22, "bold"))
        self.page_title.pack(side="left")
        self.server_pill = tk.Frame(top, bg=PANEL_2, padx=12, pady=6)
        self.server_pill.pack(side="right")
        self.dot = tk.Canvas(self.server_pill, width=10, height=10, bg=PANEL_2, highlightthickness=0)
        self.dot.pack(side="left", padx=(0, 7))
        self.dot_id = self.dot.create_oval(2, 2, 9, 9, fill=MUTED, outline="")
        self.server_label = tk.Label(self.server_pill, text="Checking server…", bg=PANEL_2, fg=MUTED,
                                     font=(self.font, 10))
        self.server_label.pack(side="left")

        self.content = tk.Frame(main, bg=BG, padx=30)
        self.content.pack(fill="both", expand=True)

        status = tk.Frame(main, bg=PANEL, padx=30, pady=7)
        status.pack(fill="x", side="bottom")
        self.status_var = tk.StringVar(value="Ready")
        tk.Label(status, textvariable=self.status_var, bg=PANEL, fg=MUTED, font=(self.font, 9),
                 anchor="w").pack(side="left")
        tk.Label(status, text="Fanxi " + __version__, bg=PANEL, fg=MUTED,
                 font=(self.font, 9)).pack(side="right")
        self.progress = ttk.Progressbar(status, mode="indeterminate", length=90)
        self.progress.pack(side="right", padx=(0, 14))

    def _nav_button(self, parent, name, label):
        frame = tk.Frame(parent, bg=PANEL, cursor="hand2")
        frame.pack(fill="x", pady=2)
        bar = tk.Frame(frame, bg=PANEL, width=3)
        bar.pack(side="left", fill="y")
        text = tk.Label(frame, text=label, bg=PANEL, fg=MUTED, font=(self.font, 11), anchor="w",
                        padx=16, pady=11, cursor="hand2")
        text.pack(side="left", fill="x", expand=True)
        data = {"frame": frame, "bar": bar, "label": text}
        for widget in (frame, text):
            widget.bind("<Button-1>", lambda _e, n=name: self.show_view(n))
            widget.bind("<Enter>", lambda _e, d=data: self._hover_nav(d, True))
            widget.bind("<Leave>", lambda _e, d=data: self._hover_nav(d, False))
        return data

    def _hover_nav(self, data, entering):
        active = data["frame"].cget("bg") == PANEL_2
        if active:
            return
        color = PANEL_2 if entering else PANEL
        data["frame"].configure(bg=color)
        data["label"].configure(bg=color)

    def _paint_nav(self):
        for name, data in self._nav_buttons.items():
            active = name == self.page
            bg = PANEL_2 if active else PANEL
            fg = TEXT if active else MUTED
            data["frame"].configure(bg=bg)
            data["label"].configure(bg=bg, fg=fg)
            data["bar"].configure(bg=ACCENT if active else bg)

    # --- lifecycle -----------------------------------------------------------------------------
    def _startup(self):
        self.show_view("home")
        self._fetch_public()
        if self.config.token and self.config.auto_login:
            self.run_bg(lambda: self.api.me(self.config.token), self._restore_session, self._restore_failed,
                        label="Signing in…")
        else:
            self.show_auth()

    def _restore_session(self, data):
        self.account = data["account"]
        self.characters = data.get("characters", [])
        self.config.username = self.account["username"]
        self.config.save()
        self._signed_in()

    def _restore_failed(self, exc):
        if isinstance(exc, ApiError) and exc.unauthorized:
            self.config.clear_session()
            self.config.save()
        self.show_auth()
        if not isinstance(exc, ApiError):
            self.set_status(str(exc))

    def _fetch_public(self):
        def work():
            status = self.api.status()
            news = self.api.news(6)
            return status, news
        self.run_bg(work, self._public_loaded, lambda exc: self._server_down(exc), label="Contacting server…")

    def _public_loaded(self, data):
        self.server_status, self.news = data
        self._paint_server()
        if self.page == "news":
            self.show_view("news")
        elif self.page == "home" and self.account:
            self.show_view("home")

    def _server_down(self, exc):
        self.server_status = None
        self._paint_server()
        self.server_label.configure(text="Server unreachable", fg=DANGER)
        self.dot.itemconfigure(self.dot_id, fill=DANGER)
        if self.page == "auth":
            pass
        self.set_status(str(exc))

    def _paint_server(self):
        if not self.server_status:
            return
        world = self.server_status.get("world", {})
        self.server_label.configure(
            text="%s  ·  %d online" % (world.get("name", "Fanxi"), self.server_status.get("online", 0)),
            fg=GREEN,
        )
        self.dot.itemconfigure(self.dot_id, fill=GREEN)

    def _signed_in(self):
        self.account_label.configure(text="@" + self.account["username"], fg=TEXT)
        self.signout_link.pack(anchor="w", pady=(6, 0))
        self._pick_character()
        self.show_view("home")
        self.set_status("Signed in as %s" % self.account["username"])

    def _pick_character(self):
        if not self.characters:
            return
        chosen = None
        if self.config.character_id is not None:
            chosen = next((c for c in self.characters if c["id"] == self.config.character_id), None)
        if chosen is None:
            chosen = self.characters[0]
        self.config.character_id = chosen["id"]
        self.config.save()

    @property
    def character(self) -> dict | None:
        if not self.characters:
            return None
        for character in self.characters:
            if character["id"] == self.config.character_id:
                return character
        return self.characters[0]

    # --- navigation ----------------------------------------------------------------------------
    def show_view(self, name: str):
        if name in ("home", "character") and not self.account:
            name = "auth"
        self.page = name
        title = {"home": "Home", "character": "Character", "news": "News", "settings": "Settings",
                 "auth": "Sign in"}.get(name, "Home")
        self.page_title.configure(text=title)
        self._paint_nav()
        for child in self.content.winfo_children():
            child.destroy()
        self.build_log = None
        builder = {
            "home": self._view_home, "character": self._view_character, "news": self._view_news,
            "settings": self._view_settings, "auth": self._view_auth,
        }.get(name, self._view_home)
        builder()

    def show_auth(self):
        self.account = None
        self.characters = []
        self.account_label.configure(text="Not signed in", fg=MUTED)
        self.signout_link.pack_forget()
        self.show_view("auth")

    # --- auth ----------------------------------------------------------------------------------
    def _field(self, parent, label, *, show=None, width=30, initial=""):
        tk.Label(parent, text=label, bg=PANEL, fg=MUTED, font=(self.font, 9), anchor="w").pack(
            fill="x", pady=(10, 4))
        entry = tk.Entry(parent, bg=PANEL_2, fg=TEXT, insertbackground=ACCENT, relief="flat",
                         highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT,
                         font=(self.font, 12), width=width, show=show)
        entry.pack(fill="x", ipady=7)
        if initial:
            entry.insert(0, initial)
        return entry

    def _view_auth(self, register: bool = False):
        for child in self.content.winfo_children():
            child.destroy()
        self.build_log = None
        wrap = tk.Frame(self.content, bg=BG)
        wrap.place(relx=0.5, rely=0.46, anchor="center")
        card = tk.Frame(wrap, bg=PANEL, padx=36, pady=30, highlightthickness=1, highlightbackground=BORDER)
        card.pack()
        tk.Label(card, text="Create your Fanxi account" if register else "Sign in to Fanxi", bg=PANEL,
                 fg=TEXT, font=(self.font, 20, "bold")).pack(anchor="w")
        tk.Label(card, text="The launcher signs you in, keeps your character and starts the game.",
                 bg=PANEL, fg=MUTED, font=(self.font, 10), wraplength=360, justify="left").pack(
            anchor="w", pady=(4, 8))

        server = self._field(card, "Server", initial=self.config.api_url)
        username = self._field(card, "Username")
        password = self._field(card, "Password", show="•")
        confirm = self._field(card, "Confirm password", show="•") if register else None
        error = tk.Label(card, text="", bg=PANEL, fg=DANGER, font=(self.font, 9), wraplength=360,
                         justify="left")
        error.pack(anchor="w", pady=(10, 0))

        def submit(_event=None):
            url = server.get().strip() or self.config.api_url
            if url.rstrip("/") != self.config.api_url.rstrip("/"):
                self.config.api_url = url.rstrip("/")
                self.api = FanxiApi(self.config.api_url)
                self.config.save()
            user = username.get().strip()
            pw = password.get()
            if register and pw != confirm.get():
                error.configure(text="The passwords do not match.")
                return
            if not user or not pw:
                error.configure(text="Enter a username and a password.")
                return
            error.configure(text="")
            if register:
                self.run_bg(lambda: self.api.register(user, pw), self._after_auth,
                            lambda exc: error.configure(text=self._message(exc)), label="Creating account…")
            else:
                self.run_bg(lambda: self.api.login(user, pw), self._after_auth,
                            lambda exc: error.configure(text=self._message(exc)), label="Signing in…")

        ActionButton(card, "Create account" if register else "Sign in", submit).pack(fill="x", pady=(16, 4))
        if register:
            LinkButton(card, "I already have an account", lambda: self._view_auth(False)).pack(pady=(8, 0))
        else:
            LinkButton(card, "Create a new account", lambda: self._view_auth(True)).pack(pady=(8, 0))
        tk.Label(card, text="Your password goes only to the server you choose; it is never saved here.",
                 bg=PANEL, fg=MUTED, font=(self.font, 8), wraplength=360).pack(anchor="w", pady=(14, 0))
        password.bind("<Return>", submit)
        (confirm or password).bind("<Return>", submit)
        username.focus_set()

    def _after_auth(self, data):
        self.config.token = data.get("token", "")
        self.config.token_expires_at = data.get("expires_at", "")
        self.account = data.get("account")
        self.characters = data.get("characters", [])
        if self.account:
            self.config.username = self.account["username"]
        self.config.save()
        self._signed_in()
        self._fetch_public()

    def sign_out(self, local: bool = False):
        token = self.config.token
        if token and not local:
            self.run_bg(lambda: self.api.logout(token), lambda _r: None, lambda _e: None, label="Signing out…")
        self.config.clear_session()
        self.config.save()
        self.show_auth()
        self.set_status("Signed out")

    @staticmethod
    def _message(exc: Exception) -> str:
        if isinstance(exc, (ApiError, NetworkError, GameError)):
            return str(exc)
        return "%s: %s" % (type(exc).__name__, exc)

    # --- home ----------------------------------------------------------------------------------
    def _view_home(self):
        if not self.account:
            self._view_auth()
            return
        character = self.character
        header = tk.Frame(self.content, bg=BG)
        header.pack(fill="x", pady=(2, 18))
        name = self.account.get("username", "adventurer")
        tk.Label(header, text="Welcome back, %s." % name, bg=BG, fg=TEXT,
                 font=(self.font, 22, "bold")).pack(anchor="w")
        tk.Label(header, text="Your world is ready when you are.", bg=BG, fg=MUTED,
                 font=(self.font, 11)).pack(anchor="w", pady=(4, 0))

        columns = tk.Frame(self.content, bg=BG)
        columns.pack(fill="both", expand=True)
        columns.grid_columnconfigure(0, weight=3)
        columns.grid_columnconfigure(1, weight=2)
        columns.grid_rowconfigure(0, weight=1)

        char_card = tk.Frame(columns, bg=PANEL, padx=26, pady=22, highlightthickness=1, highlightbackground=BORDER)
        char_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        tk.Label(char_card, text="YOUR CHARACTER", bg=PANEL, fg=MUTED, font=(self.font, 9, "bold")).pack(anchor="w")
        if character:
            tk.Label(char_card, text=character["name"], bg=PANEL, fg=TEXT,
                     font=(self.font, 30, "bold")).pack(anchor="w", pady=(8, 4))
            detail = "%s  ·  %s  ·  %s" % (race_name(character["race"]), nation_name(character["nation"]),
                                           job_name(character["main_job"]))
            tk.Label(char_card, text=detail, bg=PANEL, fg=ACCENT, font=(self.font, 11)).pack(anchor="w")
            zone = ZONES.get(character.get("zone"), "zone %s" % character.get("zone", "?"))
            tk.Label(char_card, text="Last seen in %s" % zone, bg=PANEL, fg=MUTED,
                     font=(self.font, 10)).pack(anchor="w", pady=(4, 18))
            ActionButton(char_card, "Play", self.play, font=(self.font, 13, "bold"), padx=38, pady=13).pack(
                anchor="w")
        else:
            tk.Label(char_card, text="No character yet", bg=PANEL, fg=TEXT,
                     font=(self.font, 22, "bold")).pack(anchor="w", pady=(10, 4))
            tk.Label(char_card, text="Make a name for yourself before you enter Vana'diel.", bg=PANEL, fg=MUTED,
                     font=(self.font, 10)).pack(anchor="w", pady=(0, 18))
            ActionButton(char_card, "Create a character", lambda: self.show_view("character"),
                         font=(self.font, 12, "bold")).pack(anchor="w")

        server_card = tk.Frame(columns, bg=PANEL, padx=22, pady=22, highlightthickness=1,
                               highlightbackground=BORDER)
        server_card.grid(row=0, column=1, sticky="nsew")
        tk.Label(server_card, text="SERVER", bg=PANEL, fg=MUTED, font=(self.font, 9, "bold")).pack(anchor="w")
        status = self.server_status or {}
        world = status.get("world", {})
        tk.Label(server_card, text=world.get("name", "Fanxi"), bg=PANEL, fg=TEXT,
                 font=(self.font, 19, "bold")).pack(anchor="w", pady=(8, 10))
        self._stat_row(server_card, "Players online", str(status.get("online", "—")))
        self._stat_row(server_card, "Accounts", str(status.get("accounts", "—")))
        self._stat_row(server_card, "Version", str(status.get("version", "—")))
        self._stat_row(server_card, "Server", "online" if status else "offline")

        news_box = tk.Frame(self.content, bg=BG)
        news_box.pack(fill="x", pady=(20, 4))
        tk.Label(news_box, text="LATEST NEWS", bg=BG, fg=MUTED, font=(self.font, 9, "bold")).pack(anchor="w")
        if not self.news:
            tk.Label(news_box, text="No news yet.", bg=BG, fg=MUTED, font=(self.font, 10)).pack(
                anchor="w", pady=(6, 0))
        for post in self.news[:3]:
            row = tk.Frame(news_box, bg=BG, cursor="hand2")
            row.pack(fill="x", pady=(8, 0))
            title = tk.Label(row, text=post["title"], bg=BG, fg=TEXT, font=(self.font, 11, "bold"),
                             anchor="w")
            title.pack(side="left")
            tk.Label(row, text=pretty_date(post.get("published_at")), bg=BG, fg=MUTED,
                     font=(self.font, 9)).pack(side="right")
            for widget in (row, title):
                widget.bind("<Button-1>", lambda _e: self.show_view("news"))

    def _stat_row(self, parent, label, value):
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label, bg=PANEL, fg=MUTED, font=(self.font, 10)).pack(side="left")
        tk.Label(row, text=value, bg=PANEL, fg=TEXT, font=(self.font, 10, "bold")).pack(side="right")

    # --- character -----------------------------------------------------------------------------
    def _view_character(self):
        if not self.account:
            self._view_auth()
            return
        character = self.character
        if character:
            card = tk.Frame(self.content, bg=PANEL, padx=30, pady=26, highlightthickness=1,
                            highlightbackground=BORDER)
            card.pack(fill="x")
            tk.Label(card, text=character["name"], bg=PANEL, fg=TEXT,
                     font=(self.font, 30, "bold")).pack(anchor="w")
            tk.Label(card, text="%s  ·  %s  ·  %s level %d" % (
                race_name(character["race"]), nation_name(character["nation"]),
                job_name(character["main_job"]), character["main_level"]),
                bg=PANEL, fg=ACCENT, font=(self.font, 11)).pack(anchor="w", pady=(4, 16))
            grid = tk.Frame(card, bg=PANEL)
            grid.pack(fill="x")
            for index, (label, value) in enumerate((
                    ("Race", race_name(character["race"])),
                    ("Nation", nation_name(character["nation"])),
                    ("Main job", job_name(character["main_job"])),
                    ("Home zone", ZONES.get(character.get("zone"), "zone %s" % character.get("zone"))),
                    ("HP", str(character["hp"])), ("MP", str(character["mp"])),
                    ("Face", str(character["face"])), ("Size", size_name(character["size"])))):
                cell = tk.Frame(grid, bg=PANEL)
                cell.grid(row=index // 4, column=index % 4, sticky="w", padx=(0, 40), pady=6)
                tk.Label(cell, text=label.upper(), bg=PANEL, fg=MUTED, font=(self.font, 8)).pack(anchor="w")
                tk.Label(cell, text=value, bg=PANEL, fg=TEXT, font=(self.font, 12)).pack(anchor="w")
            ActionButton(card, "Play", self.play, font=(self.font, 13, "bold"), padx=38, pady=13).pack(
                anchor="w", pady=(22, 0))
            return

        card = tk.Frame(self.content, bg=PANEL, padx=30, pady=26, highlightthickness=1,
                        highlightbackground=BORDER)
        card.pack(fill="x")
        tk.Label(card, text="Create your character", bg=PANEL, fg=TEXT,
                 font=(self.font, 24, "bold")).pack(anchor="w")
        tk.Label(card, text="One adventurer per account on this server. You can change the look only by asking an admin.",
                 bg=PANEL, fg=MUTED, font=(self.font, 10), wraplength=660, justify="left").pack(
            anchor="w", pady=(4, 18))
        form = tk.Frame(card, bg=PANEL)
        form.pack(fill="x")
        form.grid_columnconfigure(1, weight=1)
        name_var = tk.StringVar()
        tk.Label(form, text="Name", bg=PANEL, fg=MUTED, font=(self.font, 9)).grid(
            row=0, column=0, sticky="w", pady=6, padx=(0, 18))
        name = tk.Entry(form, textvariable=name_var, bg=PANEL_2, fg=TEXT, insertbackground=ACCENT,
                        relief="flat", highlightthickness=1, highlightbackground=BORDER,
                        highlightcolor=ACCENT, font=(self.font, 12))
        name.grid(row=0, column=1, columnspan=3, sticky="ew", ipady=7, pady=6)

        race_var = tk.StringVar(value=RACES[0][0])
        nation_var = tk.StringVar(value=NATIONS[0][0])
        job_var = tk.StringVar(value=JOBS[0][0])
        size_var = tk.StringVar(value=SIZES[1][0])
        face_var = tk.StringVar(value="1")
        self._choice_row(form, 1, "Race", race_var, [name for name, _ in RACES])
        self._choice_row(form, 2, "Nation", nation_var, [name for name, _ in NATIONS])
        self._choice_row(form, 3, "Main job", job_var, [name for name, _ in JOBS])
        self._choice_row(form, 4, "Size", size_var, [name for name, _ in SIZES])
        tk.Label(form, text="Face", bg=PANEL, fg=MUTED, font=(self.font, 9)).grid(
            row=5, column=0, sticky="w", pady=6, padx=(0, 18))
        face = tk.Spinbox(form, from_=1, to=8, textvariable=face_var, width=5, bg=PANEL_2, fg=TEXT,
                          buttonbackground=PANEL_2, relief="flat", highlightthickness=1,
                          highlightbackground=BORDER, font=(self.font, 11))
        face.grid(row=5, column=1, sticky="w", pady=6)

        error = tk.Label(card, text="", bg=PANEL, fg=DANGER, font=(self.font, 9))
        error.pack(anchor="w", pady=(12, 0))

        def create():
            try:
                data = {
                    "name": name_var.get().strip(),
                    "race": next(v for n, v in RACES if n == race_var.get()),
                    "nation": next(v for n, v in NATIONS if n == nation_var.get()),
                    "main_job": next(v for n, v in JOBS if n == job_var.get()),
                    "size": next(v for n, v in SIZES if n == size_var.get()),
                    "face": int(face_var.get() or 1),
                }
            except (StopIteration, ValueError):
                error.configure(text="Pick a race, nation, job and face.")
                return
            if not data["name"]:
                error.configure(text="Your character needs a name.")
                return
            error.configure(text="")
            self.run_bg(lambda: self.api.create_character(self.config.token, data), self._after_character,
                        lambda exc: error.configure(text=self._message(exc)), label="Creating character…")

        ActionButton(card, "Create character", create, font=(self.font, 12, "bold")).pack(
            anchor="w", pady=(18, 0))
        name.bind("<Return>", lambda _e: create())
        name.focus_set()

    def _choice_row(self, parent, row, label, variable, values):
        tk.Label(parent, text=label, bg=PANEL, fg=MUTED, font=(self.font, 9)).grid(
            row=row, column=0, sticky="w", pady=6, padx=(0, 18))
        option = tk.OptionMenu(parent, variable, *values)
        option.configure(bg=PANEL_2, fg=TEXT, activebackground=PANEL_3, activeforeground=TEXT,
                         relief="flat", highlightthickness=1, highlightbackground=BORDER,
                         font=(self.font, 11), anchor="w", padx=8, pady=5)
        option["menu"].configure(bg=PANEL_2, fg=TEXT, activebackground=ACCENT, activeforeground="#05202c",
                                 font=(self.font, 11))
        option.grid(row=row, column=1, sticky="w", pady=6)

    def _after_character(self, character):
        self.characters = [character]
        self.config.character_id = character["id"]
        self.config.save()
        self.show_view("home")
        self.set_status("%s is ready." % character["name"])

    # --- news ----------------------------------------------------------------------------------
    def _view_news(self):
        header = tk.Frame(self.content, bg=BG)
        header.pack(fill="x", pady=(2, 12))
        tk.Label(header, text="News from the world", bg=BG, fg=TEXT,
                 font=(self.font, 22, "bold")).pack(anchor="w")
        if not self.news:
            tk.Label(self.content, text="No news yet.", bg=BG, fg=MUTED,
                     font=(self.font, 11)).pack(anchor="w", pady=20)
            return
        scroll = ScrollFrame(self.content, bg=BG)
        scroll.pack(fill="both", expand=True)
        for post in self.news:
            card = tk.Frame(scroll.inner, bg=PANEL, padx=24, pady=20, highlightthickness=1,
                            highlightbackground=BORDER)
            card.pack(fill="x", pady=(0, 12))
            tk.Label(card, text=post["title"], bg=PANEL, fg=TEXT, font=(self.font, 16, "bold"),
                     anchor="w").pack(fill="x")
            tk.Label(card, text=pretty_date(post.get("published_at")), bg=PANEL, fg=MUTED,
                     font=(self.font, 9)).pack(anchor="w", pady=(2, 10))
            tk.Label(card, text=post.get("body", ""), bg=PANEL, fg="#c7dcee", font=(self.font, 11),
                     wraplength=760, justify="left", anchor="w").pack(fill="x")

    # --- settings ------------------------------------------------------------------------------
    def _view_settings(self):
        tk.Label(self.content, text="Settings", bg=BG, fg=TEXT, font=(self.font, 22, "bold")).pack(anchor="w")
        tk.Label(self.content, text="The launcher talks to one Fanxi server and builds the client from your own game files.",
                 bg=BG, fg=MUTED, font=(self.font, 10)).pack(anchor="w", pady=(4, 18))

        card = tk.Frame(self.content, bg=PANEL, padx=26, pady=22, highlightthickness=1,
                        highlightbackground=BORDER)
        card.pack(fill="x")
        api_var = tk.StringVar(value=self.config.api_url)
        game_var = tk.StringVar(value=self.config.game_dir or str(find_game_dir(self.config.game_dir) or ""))
        self._settings_entry(card, "Server URL", api_var)
        row = tk.Frame(card, bg=PANEL)
        row.pack(fill="x", pady=(12, 0))
        tk.Label(row, text="Game folder", bg=PANEL, fg=MUTED, font=(self.font, 9)).pack(anchor="w")
        entry_row = tk.Frame(row, bg=PANEL)
        entry_row.pack(fill="x", pady=(4, 0))
        game_entry = tk.Entry(entry_row, textvariable=game_var, bg=PANEL_2, fg=TEXT, insertbackground=ACCENT,
                              relief="flat", highlightthickness=1, highlightbackground=BORDER,
                              highlightcolor=ACCENT, font=(self.font, 11))
        game_entry.pack(side="left", fill="x", expand=True, ipady=6)
        ActionButton(entry_row, "Browse", lambda: self._browse_game(game_var), kind="ghost", padx=12,
                     pady=5).pack(side="left", padx=(8, 0))
        found = find_host64(self.config)
        tk.Label(card, text="host64: %s" % (found or "not built yet"), bg=PANEL, fg=MUTED if found else GOLD,
                 font=(self.font, 9)).pack(anchor="w", pady=(12, 0))

        buttons = tk.Frame(card, bg=PANEL)
        buttons.pack(fill="x", pady=(16, 0))
        ActionButton(buttons, "Save", lambda: self._save_settings(api_var, game_var), kind="ghost",
                     padx=18, pady=8).pack(side="left")
        ActionButton(buttons, "Detect game", lambda: self._detect_game(game_var), kind="ghost",
                     padx=18, pady=8).pack(side="left", padx=(8, 0))
        ActionButton(buttons, "Build game", lambda: self._build_game(game_var), kind="primary",
                     padx=18, pady=8).pack(side="left", padx=(8, 0))
        ActionButton(buttons, "Open data folder", self.game.open_data_dir, kind="ghost",
                     padx=18, pady=8).pack(side="right")

        log_card = tk.Frame(self.content, bg=PANEL, padx=20, pady=14, highlightthickness=1,
                            highlightbackground=BORDER)
        log_card.pack(fill="both", expand=True, pady=(16, 0))
        tk.Label(log_card, text="BUILD LOG", bg=PANEL, fg=MUTED, font=(self.font, 9, "bold")).pack(anchor="w")
        self.build_log = tk.Text(log_card, height=9, bg="#06101c", fg="#b9d4e8", insertbackground=ACCENT,
                                 relief="flat", highlightthickness=0, font=(self.mono, 9), wrap="word")
        self.build_log.pack(fill="both", expand=True, pady=(8, 0))
        self.build_log.insert("end", self.game.build_log_tail(20) or "Build output appears here.\n")
        self.build_log.configure(state="disabled")

    def _settings_entry(self, parent, label, variable):
        tk.Label(parent, text=label, bg=PANEL, fg=MUTED, font=(self.font, 9)).pack(anchor="w")
        entry = tk.Entry(parent, textvariable=variable, bg=PANEL_2, fg=TEXT, insertbackground=ACCENT,
                         relief="flat", highlightthickness=1, highlightbackground=BORDER,
                         highlightcolor=ACCENT, font=(self.font, 11))
        entry.pack(fill="x", ipady=6, pady=(4, 0))
        return entry

    def _browse_game(self, variable):
        folder = filedialog.askdirectory(title="Choose your FINAL FANTASY XI folder", parent=self)
        if folder:
            variable.set(folder)

    def _detect_game(self, variable):
        folder = find_game_dir(variable.get())
        if folder:
            variable.set(str(folder))
            self.set_status("Found %s" % folder)
        else:
            messagebox.showwarning("Fanxi", "No FINAL FANTASY XI folder found. Choose it with Browse.", parent=self)

    def _save_settings(self, api_var, game_var):
        new_api = api_var.get().strip().rstrip("/")
        old_api = self.config.api_url.rstrip("/")
        game = game_var.get().strip()
        if game and not is_game_dir(game):
            if not messagebox.askyesno("Fanxi", "That folder does not contain FFXiMain.dll, FFXi.dll and ROM. Save anyway?",
                                       parent=self):
                return
        self.config.api_url = new_api or old_api
        self.config.game_dir = str(Path(game).expanduser()) if game else ""
        self.config.save()
        if new_api and new_api != old_api:
            self.config.clear_session()
            self.config.save()
            self.api = FanxiApi(new_api)
            self.show_auth()
            self.set_status("Server changed; sign in again")
        else:
            self.set_status("Settings saved")

    def _build_game(self, game_var):
        if self._building:
            return
        folder = game_var.get().strip()
        if not is_game_dir(folder):
            self._detect_game(game_var)
            folder = game_var.get().strip()
            if not is_game_dir(folder):
                return
        if not messagebox.askyesno(
                "Build Fanxi",
                "Build host64 from your own game files?\n\nThis translates the game's code and compiles it; "
                "the first build takes several minutes.", parent=self):
            return
        self.config.game_dir = str(Path(folder).expanduser())
        self.config.save()
        self._building = True
        self.show_view("settings")
        self.set_status("Building host64…")
        self.run_bg(lambda: self.game.build(folder, progress=self._build_progress), self._build_done,
                    self._build_failed, label="Building host64…")

    def _build_progress(self, text):
        self._jobs.put(("log", None, text))

    def _build_done(self, host64):
        self._building = False
        self.set_status("Built %s" % host64)
        messagebox.showinfo("Fanxi", "The client is built.\n\n%s" % host64, parent=self)
        self.show_view("settings")

    def _build_failed(self, exc):
        self._building = False
        self.set_status("Build failed")
        messagebox.showerror("Build failed", self._message(exc), parent=self)

    # --- play ----------------------------------------------------------------------------------
    def play(self):
        character = self.character
        if not character:
            self.show_view("character")
            return
        game_dir = self.config.game_dir or str(find_game_dir(self.config.game_dir) or "")
        if not is_game_dir(game_dir):
            folder = filedialog.askdirectory(title="Choose your FINAL FANTASY XI folder", parent=self)
            if not folder or not is_game_dir(folder):
                messagebox.showwarning("Fanxi", "Fanxi needs your FINAL FANTASY XI folder first.", parent=self)
                return
            game_dir = folder
            self.config.game_dir = folder
            self.config.save()
        if find_host64(self.config) is None:
            if messagebox.askyesno("Fanxi", "host64 is not built yet. Build it now?", parent=self):
                self.show_view("settings")
                self._build_game(tk.StringVar(value=game_dir))
            return
        self.set_status("Starting Fanxi…")
        self.run_bg(lambda: self.api.launch(self.config.token, character["id"]), self._start_game,
                    self._start_failed, label="Starting the game…")

    def _start_game(self, data):
        game_dir = self.config.game_dir or str(find_game_dir(self.config.game_dir) or "")
        try:
            process = self.game.launch(game_dir, data["client"], data["login_token"])
        except GameError as exc:
            messagebox.showerror("Fanxi", str(exc), parent=self)
            self.set_status("Could not start the game")
            return
        self.set_status("Fanxi is running (pid %d). Have fun." % process.pid)

    def _start_failed(self, exc):
        if isinstance(exc, ApiError) and exc.unauthorized:
            self.config.clear_session()
            self.config.save()
            self.show_auth()
            messagebox.showinfo("Fanxi", "Your session expired. Sign in again.", parent=self)
            return
        if isinstance(exc, ApiError) and exc.code == "no_character":
            self.show_view("character")
        messagebox.showerror("Fanxi", self._message(exc), parent=self)
        self.set_status("Could not start the game")

    # --- background work -----------------------------------------------------------------------
    def run_bg(self, work, on_ok=None, on_err=None, label="Working…"):
        self.set_busy(label)

        def runner():
            try:
                value = work()
            except Exception as exc:  # the UI shows what went wrong
                self._jobs.put(("err", (on_ok, on_err), exc))
                return
            self._jobs.put(("ok", (on_ok, on_err), value))

        threading.Thread(target=runner, daemon=True).start()

    def set_busy(self, label):
        if label:
            self._busy = True
            self.status_var.set(label)
            try:
                self.progress.start(12)
            except tk.TclError:
                pass
        else:
            self._busy = False
            try:
                self.progress.stop()
            except tk.TclError:
                pass

    def set_status(self, text):
        if not self._busy:
            self.status_var.set(text)

    def _poll_jobs(self):
        try:
            while True:
                kind, callbacks, payload = self._jobs.get_nowait()
                if kind == "log":
                    self._append_log(str(payload))
                    continue
                self.set_busy(None)
                on_ok, on_err = callbacks if callbacks else (None, None)
                if kind == "ok":
                    if on_ok:
                        try:
                            on_ok(payload)
                        except Exception as exc:  # a UI callback must not kill the poll loop
                            self._report(exc)
                else:
                    if on_err:
                        try:
                            on_err(payload)
                        except Exception:
                            self._report(payload)
                    else:
                        self._report(payload)
        except queue.Empty:
            pass
        self.after(80, self._poll_jobs)

    def _report(self, exc):
        self.set_status(self._message(exc))
        messagebox.showerror("Fanxi", self._message(exc), parent=self)

    def _append_log(self, text):
        if self.build_log is not None and self.build_log.winfo_exists():
            try:
                self.build_log.configure(state="normal")
                self.build_log.insert("end", text + "\n")
                self.build_log.see("end")
                self.build_log.configure(state="disabled")
            except tk.TclError:
                pass
        if text.strip():
            self.status_var.set(text.strip()[:120])

    def on_close(self):
        try:
            self.config.last_page = self.page
            self.config.save()
        finally:
            self.destroy()


def run(config: LauncherConfig | None = None) -> int:
    app = LauncherApp(config)
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
    return 0
