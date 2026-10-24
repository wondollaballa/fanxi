"""The launcher window: sign in, make a character, press Play.

Tkinter keeps Fanxi dependency-free: macOS, Linux and Windows all have it, and the whole launcher
is one Python process. Long work (HTTP, building host64) runs on threads and reports back through
a queue, so the window never freezes.
"""
from __future__ import annotations

import json
import os
import queue
import re
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from . import APP_NAME, __version__
from .api import ApiError, FanxiApi, NetworkError
from .config import LauncherConfig, data_dir
from .control import InstanceManager
from .game import GameError, GameManager, find_game_dir, find_host64, is_game_dir
from .gear import (
    GearError, JOB_ORDER, SLOT_KEYS, SLOT_LABELS, clean_items, default_file,
    defaults_dir, downloads_dir, flatten_sets, flatten_sets_detailed, item_choices,
    job_from_state,
    normalize_set_path, path_conflict, save_version, strip_version_suffix,
    versioned_name, write_profile_snapshot,
)

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
# Item families whose GearSwap entry is a Rank 30 build; the Gear window marks them
# "R30" (Odyssey's four sets and the five Limbus top tiers).
RANK30_PREFIXES = (
    "Nyame ", "Sakpata's ", "Gleti's ", "Agwu's ",
    "Duty ", "Revelation ", "Sworn ", "Indom. ", "Indomitable ",
    "Clemen. ", "Clemency ",
)
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


class Dropdown(tk.Frame):
    """A dark, focus-safe menu button.

    tk.OptionMenu on macOS flips to the native white background when it takes focus, which made
    the white text invisible.  This is a plain Tk button plus a Tk menu: the colors stay ours and
    the button never takes keyboard focus.
    """

    def __init__(self, parent, variable: tk.StringVar, values, command=None, *,
                 width: int = 18, font=None):
        super().__init__(parent, bg=PANEL_2, highlightthickness=1, highlightbackground=BORDER,
                         highlightcolor=BORDER)
        self.variable = variable
        self.command = command
        self.values: list[str] = []
        self.display = tk.StringVar()
        # A Label, not a Button: macOS draws tk.Button with the native light control color and
        # ignores -background.  The label keeps our dark palette and never takes focus.
        self.button = tk.Label(
            self, textvariable=self.display, anchor="w", width=width,
            bg=PANEL_2, fg=TEXT, font=font or ("TkDefaultFont", 10),
            padx=8, pady=5, cursor="hand2",
        )
        self.button.pack(fill="x")
        self.button.bind("<Button-1>", lambda _event: self._open())
        self.button.bind("<Enter>", lambda _event: self.button.configure(bg=PANEL_3))
        self.button.bind("<Leave>", lambda _event: self.button.configure(bg=PANEL_2))
        self.menu = tk.Menu(
            self, tearoff=0, bg=PANEL_2, fg=TEXT, activebackground=ACCENT,
            activeforeground="#05202c", activeborderwidth=0, borderwidth=0,
            font=font or ("TkDefaultFont", 10),
        )
        self.variable.trace_add("write", lambda *_args: self._sync())
        self.set_values(values)

    def set_values(self, values) -> None:
        self.values = [str(value) for value in values]
        self.menu.delete(0, "end")
        for value in self.values:
            self.menu.add_command(label=value, command=lambda v=value: self._choose(v))
        if self.values and self.variable.get() not in self.values:
            self.variable.set(self.values[0])
        self._sync()

    def _sync(self) -> None:
        self.display.set("%s   ▾" % (self.variable.get() or ""))

    def _choose(self, value: str) -> None:
        self.variable.set(value)
        if self.command:
            self.command(value)

    def _open(self) -> None:
        if not self.values:
            return
        try:
            self.menu.tk_popup(self.button.winfo_rootx(),
                               self.button.winfo_rooty() + self.button.winfo_height())
        finally:
            self.menu.grab_release()


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
        self.insecure = os.environ.get("FANXI_API_INSECURE", "") in ("1", "true", "yes")
        self.api = FanxiApi(self.config.api_url, insecure=self.insecure)
        self.game = GameManager(self.config)
        self.account: dict | None = None
        self.characters: list[dict] = []
        self.server_status: dict | None = None
        self.news: list[dict] = []
        self.page = "home"
        self.build_log = None
        self.instances = InstanceManager(self.game)
        self._jobs: queue.Queue = queue.Queue()
        self._busy = False
        self._building = False
        self._creating_character = False
        self._control_rows: dict[int, tuple] = {}
        self._control_target = None
        self._gear_window = None
        self._control_poll_started = False
        self._control_results: queue.Queue = queue.Queue()
        self._nav_buttons: dict[str, dict] = {}
        self._hovered_nav: str | None = None

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
        for name, label in (("home", "Home"), ("character", "Character"),
                            ("accounts", "Accounts"), ("control", "Control"),
                            ("gear", "Gear / GearSwap"), ("news", "News"), ("settings", "Settings")):
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
            widget.bind("<Enter>", lambda _e, n=name: self._set_nav_hover(n, True))
            widget.bind("<Leave>", lambda e, n=name: self._set_nav_hover(n, False, e))
        return data

    def _set_nav_hover(self, name: str, entering: bool, event=None):
        if not entering and event is not None:
            # Moving from the row into its label is not leaving the row.
            if str(getattr(event, "detail", "")) == "NotifyInferior":
                return
        if entering:
            self._hovered_nav = name
        elif self._hovered_nav == name:
            self._hovered_nav = None
        self._paint_nav()

    def _paint_nav(self):
        for name, data in self._nav_buttons.items():
            active = name == self.page
            hovered = name == self._hovered_nav and not active
            bg = PANEL_2 if (active or hovered) else PANEL
            fg = TEXT if (active or hovered) else MUTED
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
        self.config.remember_account(self.account, self.config.token,
                                     self.config.token_expires_at, self.characters)
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
        extra = len(self.config.saved_accounts()) - 1
        label = "@" + self.account["username"]
        if extra > 0:
            label += "  +%d" % extra
        self.account_label.configure(text=label, fg=TEXT)
        self.signout_link.pack(anchor="w", pady=(6, 0))
        self._pick_character()
        self._creating_character = False
        self.show_view("home")
        self.set_status("Signed in as %s" % self.account["username"])

    def _pick_character(self):
        if not self.characters:
            self.config.character_id = None
            self.config.save()
            return
        chosen = None
        if self.config.character_id is not None:
            chosen = next((c for c in self.characters if c["id"] == self.config.character_id), None)
        if chosen is None:
            entry = self.config.account_entry()
            wanted = entry.get("character_id") if entry else None
            chosen = next((c for c in self.characters if c["id"] == wanted), None)
        if chosen is None:
            chosen = self.characters[0]
        self.config.character_id = chosen["id"]
        entry = self.config.account_entry()
        if entry is not None:
            entry["characters"] = list(self.characters)
            entry["character_id"] = chosen["id"]
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
        if name in ("home", "character", "accounts", "control", "gear") and not self.account:
            name = "auth"
        self._hovered_nav = None
        self.page = name
        title = {"home": "Home", "character": "Characters", "accounts": "Accounts",
                 "control": "Control room", "gear": "Gear & GearSwap", "news": "News",
                 "settings": "Settings", "auth": "Sign in"}.get(name, "Home")
        self.page_title.configure(text=title)
        self._paint_nav()
        for child in self.content.winfo_children():
            child.destroy()
        self.build_log = None
        builder = {
            "home": self._view_home, "character": self._view_character,
            "accounts": self._view_accounts, "control": self._view_control,
            "gear": self._view_gear, "news": self._view_news, "settings": self._view_settings,
            "auth": self._view_auth,
        }.get(name, self._view_home)
        builder()

    def show_auth(self):
        self.account = None
        self.characters = []
        self._creating_character = False
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

    def _view_auth(self, register: bool = False, add: bool = False):
        self._auth_add = add
        for child in self.content.winfo_children():
            child.destroy()
        self.build_log = None
        wrap = tk.Frame(self.content, bg=BG)
        wrap.place(relx=0.5, rely=0.46, anchor="center")
        card = tk.Frame(wrap, bg=PANEL, padx=36, pady=30, highlightthickness=1, highlightbackground=BORDER)
        card.pack()
        heading = ("Add another account" if add else
                   ("Create your Fanxi account" if register else "Sign in to Fanxi"))
        tk.Label(card, text=heading, bg=PANEL,
                 fg=TEXT, font=(self.font, 20, "bold")).pack(anchor="w")
        tk.Label(card, text=("Each account can run one character at a time. Add as many accounts as "
                             "you want to multibox." if add else
                             "The launcher signs you in, keeps your characters and starts the game."),
                 bg=PANEL, fg=MUTED, font=(self.font, 10), wraplength=380, justify="left").pack(
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
                self.api = FanxiApi(self.config.api_url, insecure=self.insecure)
                # Tokens belong to one server; do not carry them to another.
                self.config.accounts = []
                self.config.clear_session()
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
            LinkButton(card, "I already have an account",
                       lambda: self._view_auth(False, add)).pack(pady=(8, 0))
        else:
            LinkButton(card, "Create a new account",
                       lambda: self._view_auth(True, add)).pack(pady=(8, 0))
        if add and self.account:
            LinkButton(card, "Cancel", lambda: self.show_view("accounts")).pack(pady=(4, 0))
        tk.Label(card, text="Your password goes only to the server you choose; it is never saved here.",
                 bg=PANEL, fg=MUTED, font=(self.font, 8), wraplength=360).pack(anchor="w", pady=(14, 0))
        password.bind("<Return>", submit)
        (confirm or password).bind("<Return>", submit)
        username.focus_set()

    def _after_auth(self, data):
        token = data.get("token", "")
        expires = data.get("expires_at", "")
        self.account = data.get("account")
        self.characters = data.get("characters") or []
        if self.account:
            self.config.remember_account(self.account, token, expires, self.characters)
        self.config.save()
        self._signed_in()
        if getattr(self, "_auth_add", False):
            self.set_status("Added @%s" % self.account["username"])
        self._fetch_public()

    def sign_out(self, local: bool = False):
        token = self.config.token
        username = self.config.username
        if token and not local:
            self.run_bg(lambda: self.api.logout(token), lambda _r: None, lambda _e: None, label="Signing out…")
        self.config.forget_account(username)
        self.config.save()
        if self.config.token:
            self.set_status("Switched account")
            self.run_bg(lambda: self.api.me(self.config.token), self._restore_session,
                        self._restore_failed, label="Signing in…")
        else:
            self.account = None
            self.characters = []
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
            buttons = tk.Frame(char_card, bg=PANEL)
            buttons.pack(anchor="w")
            ActionButton(buttons, "Play", self.play, font=(self.font, 13, "bold"), padx=38,
                         pady=13).pack(side="left")
            ActionButton(buttons, "Control room", lambda: self.show_view("control"), kind="ghost",
                         font=(self.font, 11, "bold"), padx=18, pady=13).pack(side="left", padx=(10, 0))
            tk.Label(char_card, text="%d character%s on this account · %d saved account%s" % (
                len(self.characters), "" if len(self.characters) == 1 else "s",
                len(self.config.saved_accounts()), "" if len(self.config.saved_accounts()) == 1 else "s"),
                bg=PANEL, fg=MUTED, font=(self.font, 9)).pack(anchor="w", pady=(10, 0))
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
        scroll = ScrollFrame(self.content, bg=BG)
        scroll.pack(fill="both", expand=True)
        page = scroll.inner

        header = tk.Frame(page, bg=BG)
        header.pack(fill="x", pady=(2, 14))
        tk.Label(header, text="Characters on @%s" % self.account["username"], bg=BG, fg=TEXT,
                 font=(self.font, 22, "bold")).pack(side="left")
        ActionButton(header, "+ New mule", self._start_new_character, kind="ghost", padx=14,
                     pady=6).pack(side="right")
        tk.Label(page, text="Every character is a mule: make as many as you want. "
                            "One character per account can be online at a time; add another account "
                            "on the Accounts page to multibox.",
                 bg=BG, fg=MUTED, font=(self.font, 10), wraplength=760, justify="left").pack(
            anchor="w", pady=(0, 14))

        if self.characters:
            for character in self.characters:
                self._character_card(page, character)
        else:
            tk.Label(page, text="No characters yet. Make your first adventurer below.", bg=BG,
                     fg=MUTED, font=(self.font, 11)).pack(anchor="w", pady=(0, 14))

        if self._creating_character or not self.characters:
            self._character_form(page)

    def _start_new_character(self):
        self._creating_character = True
        self.show_view("character")

    def _character_card(self, parent, character):
        active = character.get("id") == self.config.character_id
        card = tk.Frame(parent, bg=PANEL, padx=22, pady=16, highlightthickness=1,
                        highlightbackground=ACCENT if active else BORDER)
        card.pack(fill="x", pady=(0, 10))
        left = tk.Frame(card, bg=PANEL)
        left.pack(side="left", fill="x", expand=True)
        title = tk.Frame(left, bg=PANEL)
        title.pack(anchor="w")
        tk.Label(title, text=character["name"], bg=PANEL, fg=TEXT,
                 font=(self.font, 20, "bold")).pack(side="left")
        if active:
            tk.Label(title, text="  ACTIVE", bg=PANEL, fg=ACCENT,
                     font=(self.font, 9, "bold")).pack(side="left", pady=(5, 0))
        detail = "%s  ·  %s  ·  %s level %d" % (
            race_name(character["race"]), nation_name(character["nation"]),
            job_name(character["main_job"]), character["main_level"])
        tk.Label(left, text=detail, bg=PANEL, fg=ACCENT, font=(self.font, 11)).pack(anchor="w",
                                                                                    pady=(3, 2))
        zone = ZONES.get(character.get("zone"), "zone %s" % character.get("zone", "?"))
        tk.Label(left, text="Last seen in %s" % zone, bg=PANEL, fg=MUTED,
                 font=(self.font, 10)).pack(anchor="w")

        actions = tk.Frame(card, bg=PANEL)
        actions.pack(side="right")
        ActionButton(actions, "Select", lambda c=character: self._select_character(c), kind="ghost",
                     padx=14, pady=6).pack(side="left", padx=(0, 6))
        ActionButton(actions, "Play", lambda c=character: self._play_character(c), kind="primary",
                     padx=18, pady=6).pack(side="left")

    def _select_character(self, character):
        self.config.character_id = character["id"]
        entry = self.config.account_entry()
        if entry is not None:
            entry["character_id"] = character["id"]
            entry["characters"] = list(self.characters)
        self.config.save()
        self.show_view("character")
        self.set_status("%s selected" % character["name"])

    def _play_character(self, character):
        self.config.character_id = character["id"]
        self.config.save()
        self.play()

    def _character_form(self, parent):
        card = tk.Frame(parent, bg=PANEL, padx=30, pady=26, highlightthickness=1,
                        highlightbackground=BORDER)
        card.pack(fill="x", pady=(8, 0))
        tk.Label(card, text="Create another character", bg=PANEL, fg=TEXT,
                 font=(self.font, 20, "bold")).pack(anchor="w")
        tk.Label(card, text="The look can be changed later by an admin; the name and job are yours.",
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
        self._choice_row(form, 1, "Race", race_var, [item for item, _ in RACES])
        self._choice_row(form, 2, "Nation", nation_var, [item for item, _ in NATIONS])
        self._choice_row(form, 3, "Main job", job_var, [item for item, _ in JOBS])
        self._choice_row(form, 4, "Size", size_var, [item for item, _ in SIZES])
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
        option = Dropdown(parent, variable, values, width=20, font=(self.font, 11))
        option.grid(row=row, column=1, sticky="w", pady=6)

    def _after_character(self, character):
        self.characters = [c for c in self.characters if c.get("id") != character.get("id")]
        self.characters.append(character)
        self.config.character_id = character["id"]
        entry = self.config.account_entry()
        if entry is not None:
            entry["character_id"] = character["id"]
            entry["characters"] = list(self.characters)
        self.config.save()
        self._creating_character = False
        self.show_view("character")
        self.set_status("%s is ready. %d character%s on this account." % (
            character["name"], len(self.characters), "" if len(self.characters) == 1 else "s"))

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

    # --- accounts ------------------------------------------------------------------------------
    def _view_accounts(self):
        scroll = ScrollFrame(self.content, bg=BG)
        scroll.pack(fill="both", expand=True)
        page = scroll.inner
        header = tk.Frame(page, bg=BG)
        header.pack(fill="x", pady=(2, 14))
        tk.Label(header, text="Saved accounts", bg=BG, fg=TEXT,
                 font=(self.font, 22, "bold")).pack(side="left")
        ActionButton(header, "+ Add account", self._add_account, kind="ghost", padx=14,
                     pady=6).pack(side="right")
        tk.Label(page, text="Each account can have one character online at a time. Add another "
                            "account here, then launch both from the Control room.",
                 bg=BG, fg=MUTED, font=(self.font, 10), wraplength=760, justify="left").pack(
            anchor="w", pady=(0, 14))
        accounts = self.config.saved_accounts()
        if not accounts:
            tk.Label(page, text="No saved accounts yet.", bg=BG, fg=MUTED,
                     font=(self.font, 11)).pack(anchor="w", pady=12)
            return
        for entry in accounts:
            self._account_card(page, entry)

    def _account_card(self, parent, entry):
        active = str(entry.get("username", "")).lower() == (self.config.username or "").lower()
        card = tk.Frame(parent, bg=PANEL, padx=22, pady=16, highlightthickness=1,
                        highlightbackground=ACCENT if active else BORDER)
        card.pack(fill="x", pady=(0, 10))
        left = tk.Frame(card, bg=PANEL)
        left.pack(side="left", fill="x", expand=True)
        title = tk.Frame(left, bg=PANEL)
        title.pack(anchor="w")
        tk.Label(title, text="@" + str(entry.get("username", "")), bg=PANEL, fg=TEXT,
                 font=(self.font, 18, "bold")).pack(side="left")
        if active:
            tk.Label(title, text="  ACTIVE", bg=PANEL, fg=ACCENT,
                     font=(self.font, 9, "bold")).pack(side="left", pady=(4, 0))
        token = entry.get("token") or ""
        if token:
            expires = entry.get("token_expires_at") or "saved"
            state = "session saved · expires %s" % expires[:10]
            color = MUTED
        else:
            state = "not signed in"
            color = GOLD
        tk.Label(left, text=state, bg=PANEL, fg=color, font=(self.font, 9)).pack(anchor="w",
                                                                                 pady=(3, 2))
        characters = entry.get("characters") or []
        if characters:
            names = ", ".join(c.get("name", "?") for c in characters[:8])
            if len(characters) > 8:
                names += " +%d" % (len(characters) - 8)
            tk.Label(left, text="Characters: %s" % names, bg=PANEL, fg=MUTED,
                     font=(self.font, 10)).pack(anchor="w")
        else:
            tk.Label(left, text="No characters yet", bg=PANEL, fg=MUTED,
                     font=(self.font, 10)).pack(anchor="w")
        actions = tk.Frame(card, bg=PANEL)
        actions.pack(side="right")
        if not active:
            ActionButton(actions, "Use", lambda u=entry["username"]: self._use_account(u),
                         kind="ghost", padx=12, pady=5).pack(side="left", padx=(0, 6))
        ActionButton(actions, "Sign in again", lambda u=entry["username"]: self._relogin_account(u),
                     kind="ghost", padx=12, pady=5).pack(side="left", padx=(0, 6))
        ActionButton(actions, "Remove", lambda u=entry["username"]: self._remove_account(u),
                     kind="secondary", padx=12, pady=5).pack(side="left")

    def _add_account(self):
        self.page = "auth"
        self.page_title.configure(text="Add account")
        self._paint_nav()
        self._view_auth(False, add=True)

    def _use_account(self, username: str):
        if not self.config.activate_account(username):
            return
        self.config.save()
        self.account = None
        self.characters = []
        self.run_bg(lambda: self.api.me(self.config.token), self._restore_session,
                    self._restore_failed, label="Signing in…")

    def _relogin_account(self, username: str):
        self.config.activate_account(username)
        self.config.save()
        self.page = "auth"
        self.page_title.configure(text="Sign in")
        self._paint_nav()
        self._view_auth(False, add=True)

    def _remove_account(self, username: str):
        entry = self.config.account_entry(username)
        if entry is None:
            return
        if not messagebox.askyesno("Fanxi", "Remove @%s from this launcher?\n\nThe server account "
                                             "and its characters stay." % username, parent=self):
            return
        token = entry.get("token") or ""
        active = str(username).lower() == (self.config.username or "").lower()
        if token:
            self.run_bg(lambda: self._api_for(token).logout(token), lambda _r: None,
                        lambda _e: None, label="Signing out…")
        self.config.forget_account(username)
        self.config.save()
        if active:
            if self.config.token:
                self.account = None
                self.characters = []
                self.run_bg(lambda: self.api.me(self.config.token), self._restore_session,
                            self._restore_failed, label="Signing in…")
            else:
                self.account = None
                self.characters = []
                self.show_auth()
        elif self.page == "accounts":
            self.show_view("accounts")

    # --- control room --------------------------------------------------------------------------
    def _view_control(self):
        self._ensure_control_poll()
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Fanxi.Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                        rowheight=25, borderwidth=0)
        style.configure("Fanxi.Treeview.Heading", background=PANEL_2, foreground=MUTED,
                        font=(self.font, 9, "bold"), relief="flat")
        style.map("Fanxi.Treeview", background=[("selected", PANEL_3)],
                  foreground=[("selected", TEXT)])

        page = tk.Frame(self.content, bg=BG)
        page.pack(fill="both", expand=True)
        header = tk.Frame(page, bg=BG)
        header.pack(fill="x", pady=(2, 12))
        ActionButton(header, "Stop all", self._stop_all, kind="secondary", padx=14,
                     pady=6).pack(side="right")
        ActionButton(header, "Launch all", self._launch_all, kind="primary", padx=14,
                     pady=6).pack(side="right", padx=(0, 8))
        tk.Label(page, text="One client per account. Launch them here, then send commands or watch "
                            "EXP/hr and DPS without leaving the launcher.",
                 bg=BG, fg=MUTED, font=(self.font, 10), wraplength=800, justify="left").pack(
            anchor="w", pady=(0, 12))

        party = tk.Frame(page, bg=PANEL, padx=18, pady=14, highlightthickness=1,
                         highlightbackground=BORDER)
        party.pack(fill="x")
        party_title = tk.Frame(party, bg=PANEL)
        party_title.pack(fill="x")
        tk.Label(party_title, text="PARTY", bg=PANEL, fg=MUTED,
                 font=(self.font, 9, "bold")).pack(side="left")
        LinkButton(party_title, "Manage accounts", lambda: self.show_view("accounts"),
                   bg=PANEL).pack(side="right")
        self._control_status_labels: dict[str, tk.Label] = {}
        self._control_party_vars: dict[str, tk.StringVar] = {}
        accounts = self.config.saved_accounts()
        if not accounts:
            tk.Label(party, text="No accounts yet. Add one from Accounts.", bg=PANEL, fg=MUTED,
                     font=(self.font, 10)).pack(anchor="w", pady=(10, 2))
        for entry in accounts:
            self._control_party_row(party, entry)

        live = tk.Frame(page, bg=PANEL, padx=18, pady=14, highlightthickness=1,
                        highlightbackground=BORDER)
        live.pack(fill="x", pady=(12, 0))
        live_title = tk.Frame(live, bg=PANEL)
        live_title.pack(fill="x")
        tk.Label(live_title, text="LIVE PARTY", bg=PANEL, fg=MUTED,
                 font=(self.font, 9, "bold")).pack(side="left")
        LinkButton(live_title, "Refresh", lambda: self._refresh_control(force=True),
                   bg=PANEL).pack(side="right")
        LinkButton(live_title, "Gear & GearSwap", lambda: self.show_view("gear"),
                   bg=PANEL).pack(side="right", padx=(0, 16))
        columns = ("account", "character", "zone", "hp", "mp", "exp", "dps", "status")
        self._control_tree = ttk.Treeview(live, columns=columns, show="headings", height=5,
                                          style="Fanxi.Treeview")
        headings = {"account": ("Account", 95), "character": ("Character", 110),
                    "zone": ("Zone", 120), "hp": ("HP", 55), "mp": ("MP", 55),
                    "exp": ("EXP/hr", 65), "dps": ("DPS", 55), "status": ("Status", 90)}
        for column in columns:
            label, width = headings[column]
            self._control_tree.heading(column, text=label)
            self._control_tree.column(column, width=width, anchor="w", stretch=column in ("zone",))
        self._control_tree.pack(fill="x", pady=(8, 0))
        self._control_tree.bind("<Double-1>", self._gear_from_tree)
        self._control_empty = tk.Label(live, text="No clients running. Launch a character above.",
                                       bg=PANEL, fg=MUTED, font=(self.font, 10))
        self._control_empty.pack(anchor="w", pady=(6, 0))

        command = tk.Frame(page, bg=PANEL, padx=18, pady=14, highlightthickness=1,
                           highlightbackground=BORDER)
        command.pack(fill="x", pady=(12, 0))
        tk.Label(command, text="COMMAND CONSOLE", bg=PANEL, fg=MUTED,
                 font=(self.font, 9, "bold")).pack(anchor="w")
        row = tk.Frame(command, bg=PANEL)
        row.pack(fill="x", pady=(8, 0))
        target_var = tk.StringVar()
        self._control_target_var = target_var
        targets = self._control_targets()
        self._control_target_map = targets
        names = list(targets.keys()) or ["(no client)"]
        target_var.set(names[0])
        target = Dropdown(row, target_var, names, width=26, font=(self.font, 10))
        target.pack(side="left")
        self._command_entry = tk.Entry(row, bg=PANEL_2, fg=TEXT, insertbackground=ACCENT,
                                       relief="flat", highlightthickness=1,
                                       highlightbackground=BORDER, highlightcolor=ACCENT,
                                       font=(self.mono, 11))
        self._command_entry.pack(side="left", fill="x", expand=True, padx=(8, 8), ipady=5)
        self._command_entry.insert(0, "!zone 100")
        self._command_entry.bind("<Return>", lambda _e: self._send_command())
        ActionButton(row, "Send", self._send_command, padx=16, pady=5).pack(side="left")
        ActionButton(row, "Gear / GearSwap", lambda: self._open_gear(self._selected_control_port()),
                     kind="ghost", padx=12, pady=5).pack(side="left", padx=(8, 0))
        quick = tk.Frame(command, bg=PANEL)
        quick.pack(fill="x", pady=(8, 0))
        for label, line in (("Zone 100", "!zone 100"), ("Port Jeuno", "!zone 246"),
                            ("Heal", "!heal"), ("Merits 5", "!merits 5"),
                            ("Where", "!where"), ("Help", "!help")):
            LinkButton(quick, label, lambda value=line: self._send_command(value), bg=PANEL,
                       fg=ACCENT).pack(side="left", padx=(0, 16))
        tk.Label(command, text="GearSwap is in the Gear window: double-click a LIVE PARTY row, "
                               "or pick a client above and press Gear / GearSwap.",
                 bg=PANEL, fg=MUTED, font=(self.font, 9)).pack(anchor="w", pady=(8, 0))
        self._refresh_control()

    def _control_party_row(self, parent, entry):
        username = str(entry.get("username", ""))
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x", pady=(9, 0))
        left = tk.Frame(row, bg=PANEL, width=300)
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text="@" + username, bg=PANEL, fg=TEXT,
                 font=(self.font, 11, "bold")).pack(anchor="w")
        status = tk.Label(left, text="offline", bg=PANEL, fg=MUTED, font=(self.font, 9))
        status.pack(anchor="w")
        self._control_status_labels[username] = status
        characters = entry.get("characters") or []
        if characters:
            names = [str(c.get("name") or "?") for c in characters]
            selected = next((c for c in characters if c.get("id") == entry.get("character_id")),
                            characters[0])
            var = tk.StringVar(value=str(selected.get("name") or names[0]))
            self._control_party_vars[username] = var
            menu = Dropdown(row, var, names,
                            command=lambda value, u=username: self._select_party_character(u, value),
                            width=18, font=(self.font, 10))
            menu.pack(side="left", padx=(0, 10))
        else:
            tk.Label(row, text="no character", bg=PANEL, fg=GOLD,
                     font=(self.font, 10)).pack(side="left", padx=(0, 10))
            self._control_party_vars[username] = tk.StringVar(value="")
        running = self.instances.running_for(username)
        if running is not None:
            ActionButton(row, "Stop", lambda u=username: self._stop_account(u), kind="secondary",
                         padx=12, pady=4).pack(side="right")
        else:
            ActionButton(row, "Launch", lambda u=username: self._launch_account(u), kind="ghost",
                         padx=12, pady=4).pack(side="right")

    def _control_targets(self) -> dict:
        targets = {}
        for instance in self.instances.active():
            targets["%s — %s (:%d)" % (instance.account, instance.name, instance.port)] = instance.port
        return targets

    def _select_party_character(self, username: str, name: str) -> None:
        entry = self.config.account_entry(username)
        if entry is None:
            return
        character = next((c for c in entry.get("characters") or [] if c.get("name") == name), None)
        if character is not None:
            entry["character_id"] = character.get("id")
            if str(username).lower() == (self.config.username or "").lower():
                self.config.character_id = character.get("id")
            self.config.save()

    def _selected_control_port(self) -> int | None:
        if not getattr(self, "_control_target_var", None):
            return None
        return getattr(self, "_control_target_map", {}).get(self._control_target_var.get())

    def _gear_from_tree(self, _event=None):
        selection = self._control_tree.selection() if hasattr(self, "_control_tree") else ()
        if selection:
            try:
                self._open_gear(int(selection[0]))
            except (TypeError, ValueError):
                pass

    def _send_command(self, line: str | None = None) -> None:
        port = self._selected_control_port()
        instance = self.instances.by_port(port) if port else None
        if instance is None:
            messagebox.showinfo("Fanxi", "Launch a client first, then pick it in the console.",
                                parent=self)
            return
        if line is None:
            line = self._command_entry.get().strip()
        if not line:
            return
        self.set_status("Sending %s to %s…" % (line, instance.name))
        self.run_bg(lambda: instance.control().command(line),
                    lambda _r: self.set_status("Sent %s to %s" % (line, instance.name)),
                    lambda exc: self._command_failed(instance, exc), label="Sending command…")

    def _command_failed(self, instance, exc):
        self.set_status("Command failed: %s" % self._message(exc))
        if instance.last_state is None:
            messagebox.showinfo("Fanxi", "%s is still signing in (%s)." % (instance.name, exc),
                                parent=self)

    def _stop_all(self) -> None:
        running = self.instances.active()
        if not running:
            return
        if not messagebox.askyesno("Fanxi", "Stop %d client%s?" % (len(running),
                                                                   "" if len(running) == 1 else "s"),
                                   parent=self):
            return
        self.set_status("Stopping the party…")

        def work():
            for instance in running:
                self.instances.stop(instance)
            return len(running)

        self.run_bg(work, lambda n: self._stopped_all(n), lambda exc: self._report(exc),
                    label="Stopping the party…")

    def _stopped_all(self, count):
        self.set_status("Stopped %d client%s." % (count, "" if count == 1 else "s"))
        self.show_view("control")

    def _open_gear(self, port: int | None):
        instance = self.instances.by_port(port) if port else None
        if instance is None:
            messagebox.showinfo("Fanxi", "Pick a running client first.", parent=self)
            return
        GearWindow(self, instance)

    # --- gear ----------------------------------------------------------------------------------
    def _view_gear(self):
        scroll = ScrollFrame(self.content, bg=BG)
        scroll.pack(fill="both", expand=True)
        page = scroll.inner
        tk.Label(page, text="Open a running client's gear window to see the item in every slot, "
                            "change a slot, load the live job's default GearSwap library, import "
                            "or edit sets, and save timestamped versions.",
                 bg=BG, fg=MUTED, font=(self.font, 10), wraplength=800, justify="left").pack(
            anchor="w", pady=(0, 14))

        instances = self.instances.active()
        if not instances:
            card = tk.Frame(page, bg=PANEL, padx=24, pady=22, highlightthickness=1,
                            highlightbackground=BORDER)
            card.pack(fill="x")
            tk.Label(card, text="No clients are running", bg=PANEL, fg=TEXT,
                     font=(self.font, 18, "bold")).pack(anchor="w")
            tk.Label(card, text="Start a client from the Control room first. Gear and GearSwap "
                                "read the live client, so they need its control port.",
                     bg=PANEL, fg=MUTED, font=(self.font, 10), wraplength=700, justify="left").pack(
                anchor="w", pady=(4, 14))
            ActionButton(card, "Open Control room", lambda: self.show_view("control"),
                         kind="primary", padx=18, pady=8).pack(anchor="w")
        else:
            for instance in instances:
                card = tk.Frame(page, bg=PANEL, padx=22, pady=16, highlightthickness=1,
                                highlightbackground=BORDER)
                card.pack(fill="x", pady=(0, 10))
                left = tk.Frame(card, bg=PANEL)
                left.pack(side="left", fill="x", expand=True)
                tk.Label(left, text=instance.name, bg=PANEL, fg=TEXT,
                         font=(self.font, 18, "bold")).pack(anchor="w")
                state = instance.last_state or {}
                zone = (state.get("zone") or {}).get("name") or "signing in"
                tk.Label(left, text="@%s · control :%d · %s" % (
                    instance.account, instance.port, zone), bg=PANEL, fg=MUTED,
                    font=(self.font, 10)).pack(anchor="w", pady=(2, 0))
                ActionButton(card, "Open Gear & GearSwap",
                             lambda port=instance.port: self._open_gear(port),
                             kind="primary", padx=18, pady=8).pack(side="right")

        folder = data_dir() / "gearswap"
        try:
            profiles = sorted(folder.glob("*.json"))
        except OSError:
            profiles = []
        if profiles:
            card = tk.Frame(page, bg=PANEL, padx=22, pady=16, highlightthickness=1,
                            highlightbackground=BORDER)
            card.pack(fill="x", pady=(12, 0))
            tk.Label(card, text="SAVED GEAR VERSIONS", bg=PANEL, fg=MUTED,
                     font=(self.font, 9, "bold")).pack(anchor="w")
            for profile in profiles[-12:]:
                tk.Label(card, text=profile.name, bg=PANEL, fg=TEXT,
                         font=(self.mono, 9), anchor="w").pack(anchor="w", pady=(3, 0))
            tk.Label(card, text="Versions are written by “Save version” in a Gear window.",
                     bg=PANEL, fg=MUTED, font=(self.font, 9)).pack(anchor="w", pady=(8, 0))

    # --- control polling -----------------------------------------------------------------------
    def _ensure_control_poll(self):
        if self._control_poll_started:
            return
        self._control_poll_started = True
        threading.Thread(target=self._control_loop, name="fanxi-control-poll", daemon=True).start()
        self.after(400, self._drain_control)

    def _control_loop(self):
        while True:
            instances = self.instances.active()
            threads = []
            for instance in instances:
                thread = threading.Thread(target=self._poll_instance, args=(instance,), daemon=True)
                thread.start()
                threads.append(thread)
            for thread in threads:
                thread.join(timeout=5)
            time.sleep(2.0)

    def _poll_instance(self, instance):
        try:
            metrics = instance.control().metrics()
            self._control_results.put((instance.port, metrics, ""))
        except Exception as exc:  # a game still signing in has no control port yet
            self._control_results.put((instance.port, None, str(exc)))

    def _drain_control(self):
        try:
            while True:
                port, metrics, error = self._control_results.get_nowait()
                instance = self.instances.by_port(port)
                if instance is None:
                    continue
                instance.last_seen = time.time()
                instance.last_error = error
                if metrics:
                    instance.last_metrics = metrics
                    instance.last_state = metrics.get("state")
        except queue.Empty:
            pass
        if self.page == "control":
            self._refresh_control()
        self.after(350, self._drain_control)

    def _refresh_control(self, force: bool = False):
        for username, label in getattr(self, "_control_status_labels", {}).items():
            instance = self.instances.running_for(username)
            if instance is None:
                label.configure(text="offline", fg=MUTED)
            elif instance.last_state and instance.last_state.get("player"):
                label.configure(text="online · control :%d" % instance.port, fg=GREEN)
            else:
                label.configure(text="signing in · control :%d" % instance.port, fg=GOLD)
        tree = getattr(self, "_control_tree", None)
        try:
            if tree is None or not tree.winfo_exists():
                return
        except tk.TclError:
            return
        instances = self.instances.active()
        keep = set()
        for instance in instances:
            keep.add(str(instance.port))
            metrics = instance.last_metrics or {}
            state = metrics.get("state") or instance.last_state or {}
            player = state.get("player") or {}
            zone = state.get("zone") or {}
            kpi = metrics.get("kpi") or {}
            hp = "%s/%s" % (player.get("hp", "—"), player.get("hpmax", player.get("hp", "—")))
            mp = "%s/%s" % (player.get("mp", "—"), player.get("mpmax", player.get("mp", "—")))
            values = (
                "@" + instance.account,
                instance.name,
                zone.get("name") or ("zone %s" % zone.get("id") if zone.get("id") else "—"),
                hp, mp,
                ("%.0f" % kpi["exp_per_hour"]) if kpi.get("exp_per_hour") is not None else "—",
                ("%.1f" % kpi["dps"]) if kpi.get("dps") is not None else "—",
                "online" if player else ("starting" if instance.uptime < 30 else "waiting"),
            )
            if tree.exists(str(instance.port)):
                tree.item(str(instance.port), values=values)
            else:
                tree.insert("", "end", iid=str(instance.port), values=values)
        for item in tree.get_children():
            if item not in keep:
                tree.delete(item)
        if hasattr(self, "_control_empty"):
            if instances:
                self._control_empty.pack_forget()
            else:
                self._control_empty.pack(anchor="w", pady=(6, 0))

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
            self.config.accounts = []
            self.config.clear_session()
            self.config.save()
            self.api = FanxiApi(new_api, insecure=self.insecure)
            self.show_auth()
            self.set_status("Server changed; sign in again")
        else:
            self.set_status("Settings saved")

    def _build_game(self, game_var, confirm=True):
        if self._building:
            return
        folder = game_var.get().strip()
        if not is_game_dir(folder):
            self._detect_game(game_var)
            folder = game_var.get().strip()
            if not is_game_dir(folder):
                return
        if confirm and not messagebox.askyesno(
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
        self._launch_one(self.account, character, self.config.token)

    def _api_for(self, token: str) -> FanxiApi:
        if token and token == self.config.token:
            return self.api
        return FanxiApi(self.config.api_url, insecure=self.insecure)

    def _ensure_game_ready(self) -> str | None:
        game_dir = self.config.game_dir or str(find_game_dir(self.config.game_dir) or "")
        if not is_game_dir(game_dir):
            folder = filedialog.askdirectory(title="Choose your FINAL FANTASY XI folder", parent=self)
            if not folder or not is_game_dir(folder):
                messagebox.showwarning("Fanxi", "Fanxi needs your FINAL FANTASY XI folder first.",
                                       parent=self)
                return None
            game_dir = folder
            self.config.game_dir = folder
            self.config.save()
        if find_host64(self.config) is None:
            if messagebox.askyesno("Fanxi", "host64 is not built yet. Build it now?", parent=self):
                self.show_view("settings")
                self._build_game(tk.StringVar(value=game_dir), confirm=False)
            return None
        return game_dir

    def _launch_one(self, account: dict | None, character: dict, token: str) -> None:
        if not account or not character:
            self.show_view("character")
            return
        if not token:
            self.show_auth()
            return
        running = self.instances.running_for(account.get("username", ""))
        if running is not None:
            messagebox.showinfo("Fanxi", "%s is already online as %s (control port %d)." % (
                account.get("username"), running.name, running.port), parent=self)
            return
        game_dir = self._ensure_game_ready()
        if not game_dir:
            return
        api = self._api_for(token)
        username = account.get("username", "")
        self.set_status("Starting %s…" % character.get("name", "the game"))

        def work():
            data = api.launch(token, character["id"])
            return self.instances.launch(account, character, data["client"], data["login_token"],
                                         game_dir)

        self.run_bg(work, self._launched, lambda exc: self._launch_failed(exc, username),
                    label="Starting the game…")

    def _launched(self, instance):
        self.set_status("%s is running (pid %d, control port %d)." % (
            instance.name, instance.pid, instance.port))
        self._ensure_control_poll()
        if self.page == "control":
            self.show_view("control")

    def _launch_failed(self, exc, username: str = ""):
        if isinstance(exc, ApiError) and exc.unauthorized:
            entry = self.config.account_entry(username)
            if entry is not None:
                entry["token"] = ""
                entry["token_expires_at"] = ""
                if str(username).lower() == (self.config.username or "").lower():
                    self.config.token = ""
                    self.config.token_expires_at = ""
                self.config.save()
            messagebox.showinfo("Fanxi", "The session for %s expired. Sign in again from Accounts."
                                % (username or "this account"), parent=self)
            self.show_view("accounts")
            self.set_status("Session expired")
            return
        if isinstance(exc, ApiError) and exc.code == "no_character":
            self.show_view("character")
        messagebox.showerror("Fanxi", self._message(exc), parent=self)
        self.set_status("Could not start the game")

    # --- control room --------------------------------------------------------------------------
    def _launch_account(self, username: str) -> None:
        entry = self.config.account_entry(username)
        if entry is None:
            return
        characters = entry.get("characters") or []
        character_id = entry.get("character_id")
        character = next((c for c in characters if c.get("id") == character_id), None)
        if character is None and characters:
            character = characters[0]
        if character is None:
            messagebox.showinfo("Fanxi", "@%s has no character yet. Open Characters and make one."
                                % username, parent=self)
            return
        self._launch_one({"username": entry["username"], "id": entry.get("id")},
                         character, entry.get("token", ""))

    def _launch_all(self) -> None:
        entries = [e for e in self.config.saved_accounts() if e.get("token")]
        if not entries:
            messagebox.showinfo("Fanxi", "Sign in to an account first.", parent=self)
            return
        game_dir = self._ensure_game_ready()
        if not game_dir:
            return
        self.set_status("Launching %d account%s…" % (len(entries), "" if len(entries) == 1 else "s"))

        def work():
            launched, failed = [], []
            for entry in entries:
                username = entry.get("username", "")
                if self.instances.running_for(username) is not None:
                    continue
                characters = entry.get("characters") or []
                character = next((c for c in characters
                                  if c.get("id") == entry.get("character_id")), None)
                if character is None and characters:
                    character = characters[0]
                if character is None:
                    failed.append((username, "no character"))
                    continue
                try:
                    data = self._api_for(entry.get("token", "")).launch(
                        entry.get("token", ""), character["id"])
                    launched.append(self.instances.launch(
                        {"username": username, "id": entry.get("id")}, character,
                        data["client"], data["login_token"], game_dir))
                except Exception as exc:  # report the account that failed, keep going
                    failed.append((username, str(exc)))
                time.sleep(0.8)
            return launched, failed

        self.run_bg(work, self._launched_all, self._launch_failed, label="Launching the party…")

    def _launched_all(self, result):
        launched, failed = result
        self._ensure_control_poll()
        message = "Started %d client%s." % (len(launched), "" if len(launched) == 1 else "s")
        if failed:
            message += "\n\n" + "\n".join("%s: %s" % item for item in failed)
        messagebox.showinfo("Fanxi", message, parent=self)
        self.show_view("control")

    def _stop_account(self, username: str) -> None:
        instance = self.instances.running_for(username)
        if instance is None:
            self.show_view("control")
            return
        self.set_status("Stopping %s…" % instance.name)
        self.run_bg(lambda: self.instances.stop(instance), lambda _r: self._stopped(username),
                    lambda exc: messagebox.showerror("Fanxi", self._message(exc), parent=self),
                    label="Stopping the game…")

    def _stopped(self, username: str):
        self.set_status("%s stopped." % username)
        if self.page == "control":
            self.show_view("control")
        else:
            self.show_view("home")

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


class GearWindow(tk.Toplevel):
    """The active gear and GearSwap sets of one running client."""

    SLOTS = [
        (0, "Main", "main"), (1, "Sub", "sub"), (2, "Range", "range"), (3, "Ammo", "ammo"),
        (4, "Head", "head"), (5, "Body", "body"), (6, "Hands", "hands"), (7, "Legs", "legs"),
        (8, "Feet", "feet"), (9, "Neck", "neck"), (10, "Waist", "waist"),
        (11, "Left ear", "left_ear"), (12, "Right ear", "right_ear"),
        (13, "Left ring", "left_ring"), (14, "Right ring", "right_ring"), (15, "Back", "back"),
    ]

    def __init__(self, app, instance):
        super().__init__(app)
        self.app = app
        self.instance = instance
        self.title("Gear — %s" % instance.name)
        self.configure(bg=BG)
        self.geometry("1120x740")
        self.minsize(980, 650)
        self.transient(app)
        self.sets: dict[str, dict[str, str]] = {}
        self.set_details: dict[str, dict[str, dict]] = {}
        self._list_paths: list[str] = []
        self._item_slots: list[str] = []
        self._gear_labels: dict[str, tk.Label] = {}
        self.job = None
        self.character_name = instance.name
        self.loaded_job = ""
        self.source = ""
        self.save_dir: Path | None = None
        self._save_hint: Path | None = None
        self._chosen_base: str | None = None
        self.last_saved: Path | None = None
        self.dirty = False
        self._auto_loaded = False
        self._save_prompted = False
        self._load_id = 0
        self._save_after: str | None = None
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(150, self.refresh)

    # --- layout --------------------------------------------------------------------------------
    def _build(self):
        header = tk.Frame(self, bg=BG, padx=24, pady=18)
        header.pack(fill="x")
        tk.Label(header, text=self.instance.name, bg=BG, fg=TEXT,
                 font=(self.app.font, 20, "bold")).pack(side="left")
        self.job_label = tk.Label(header, text="detecting job…", bg=BG, fg=GOLD,
                                  font=(self.app.font, 9, "bold"))
        self.job_label.pack(side="left", padx=(14, 0), pady=(7, 0))
        tk.Label(header, text="  @%s · control :%d" % (self.instance.account, self.instance.port),
                 bg=BG, fg=MUTED, font=(self.app.font, 9)).pack(side="left", pady=(6, 0))
        ActionButton(header, "Refresh", self.refresh, kind="ghost", padx=12, pady=5).pack(
            side="right")

        body = tk.Frame(self, bg=BG, padx=24)
        body.pack(fill="both", expand=True)
        left = tk.Frame(body, bg=PANEL, padx=18, pady=16, highlightthickness=1,
                        highlightbackground=BORDER)
        left.pack(side="left", fill="both")
        tk.Label(left, text="ACTIVE GEAR", bg=PANEL, fg=MUTED,
                 font=(self.app.font, 9, "bold")).pack(anchor="w")
        gear_grid = tk.Frame(left, bg=PANEL)
        gear_grid.pack(fill="both", expand=True, pady=(8, 0))
        for index, (slot, label, key) in enumerate(self.SLOTS):
            row = tk.Frame(gear_grid, bg=PANEL)
            row.grid(row=index // 2, column=index % 2, sticky="ew", padx=(0, 12), pady=5)
            gear_grid.grid_columnconfigure(index % 2, weight=1)
            tk.Label(row, text=label.upper(), bg=PANEL, fg=MUTED,
                     font=(self.app.font, 8)).pack(anchor="w")
            value = tk.Label(row, text="—", bg=PANEL, fg=TEXT, font=(self.app.font, 10),
                             anchor="w", wraplength=170, justify="left")
            value.pack(anchor="w")
            LinkButton(row, "change", lambda k=key: self._change_slot(k), bg=PANEL,
                       fg=ACCENT).pack(anchor="w")
            self._gear_labels[key] = value

        right = tk.Frame(body, bg=PANEL, padx=18, pady=16, highlightthickness=1,
                         highlightbackground=BORDER)
        right.pack(side="left", fill="both", expand=True, padx=(14, 0))
        tk.Label(right, text="GEARSWAP SETS", bg=PANEL, fg=MUTED,
                 font=(self.app.font, 9, "bold")).pack(anchor="w")
        self.source_label = tk.Label(right, text="No library loaded yet", bg=PANEL, fg=MUTED,
                                     font=(self.app.font, 9), anchor="w", justify="left",
                                     wraplength=430)
        self.source_label.pack(anchor="w", pady=(4, 8))

        defaults = tk.Frame(right, bg=PANEL)
        defaults.pack(fill="x", pady=(0, 4))
        tk.Label(defaults, text="DEFAULTS", bg=PANEL, fg=MUTED,
                 font=(self.app.font, 8, "bold")).pack(side="left")
        self.defaults_var = tk.StringVar(value=JOB_ORDER[0])
        self.defaults_dd = Dropdown(defaults, self.defaults_var, JOB_ORDER, width=8)
        self.defaults_dd.pack(side="left", padx=(6, 6))
        ActionButton(defaults, "Load", lambda: self._load_defaults(self.defaults_var.get()),
                     kind="ghost", padx=9, pady=3).pack(side="left")
        ActionButton(defaults, "Import your own…", self._import, kind="ghost", padx=9,
                     pady=3).pack(side="right")

        tools = tk.Frame(right, bg=PANEL)
        tools.pack(fill="x", pady=(2, 6))
        ActionButton(tools, "New set…", self._new_set, kind="primary", padx=9,
                     pady=3).pack(side="left")
        ActionButton(tools, "Duplicate", self._duplicate_set, kind="ghost", padx=8,
                     pady=3).pack(side="left", padx=(6, 0))
        ActionButton(tools, "Edit set…", self._edit_set, kind="ghost", padx=8,
                     pady=3).pack(side="left", padx=(6, 0))
        ActionButton(tools, "Delete", self._delete_set, kind="ghost", padx=8,
                     pady=3).pack(side="left", padx=(6, 0))

        set_wrap = tk.Frame(right, bg=PANEL)
        set_wrap.pack(fill="both", expand=True, pady=(10, 4))
        self.set_list = tk.Listbox(set_wrap, bg="#06101c", fg="#b9d4e8",
                                   selectbackground=PANEL_3, selectforeground=TEXT,
                                   relief="flat", highlightthickness=0,
                                   exportselection=False,
                                   font=(self.app.mono, 9), height=11)
        set_scroll = ttk.Scrollbar(set_wrap, orient="vertical", command=self.set_list.yview)
        self.set_list.configure(yscrollcommand=set_scroll.set)
        self.set_list.pack(side="left", fill="both", expand=True)
        set_scroll.pack(side="right", fill="y")
        self.set_list.bind("<<ListboxSelect>>", self._show_set)

        item_wrap = tk.Frame(right, bg=PANEL)
        item_wrap.pack(fill="x", pady=(4, 6))
        self.items_list = tk.Listbox(item_wrap, bg="#06101c", fg="#b9d4e8",
                                     selectbackground=PANEL_3, selectforeground=TEXT,
                                     relief="flat", highlightthickness=0,
                                     exportselection=False,
                                     font=(self.app.mono, 9), height=10)
        item_scroll = ttk.Scrollbar(item_wrap, orient="vertical",
                                    command=self.items_list.yview)
        self.items_list.configure(yscrollcommand=item_scroll.set)
        self.items_list.pack(side="left", fill="both", expand=True)
        item_scroll.pack(side="right", fill="y")
        self.items_list.bind("<Double-1>", self._edit_item)
        self.items_list.bind("<<ListboxSelect>>", self._show_item_augments)

        self.augment_label = tk.Label(
            right, text="", bg=PANEL, fg=MUTED, font=(self.app.mono, 8),
            wraplength=470, justify="left", anchor="w")
        self.augment_label.pack(fill="x", pady=(0, 4))

        buttons = tk.Frame(right, bg=PANEL)
        buttons.pack(fill="x", pady=(4, 0))
        ActionButton(buttons, "Wear set", self._apply_set, kind="primary", padx=10,
                     pady=5).pack(side="left")
        ActionButton(buttons, "Save version…", lambda: self._save_version(ask=True),
                     kind="ghost", padx=10, pady=5).pack(side="left", padx=(8, 0))
        self.status = tk.Label(right, text="", bg=PANEL, fg=MUTED, font=(self.app.font, 9),
                               wraplength=430, justify="left", anchor="w")
        self.status.pack(anchor="w", pady=(8, 0))

    # --- active gear ---------------------------------------------------------------------------
    def _alive(self) -> bool:
        try:
            return bool(self.winfo_exists())
        except tk.TclError:
            return False

    def refresh(self):
        self.app.run_bg(self._read_client, self._show_client, self._gear_error,
                        label="Reading gear…")

    def _read_client(self):
        control = self.instance.control()
        payload = {"gear": control.gear(), "state": None, "state_error": ""}
        try:
            payload["state"] = control.state()
        except Exception as exc:  # the job is a bonus; active gear still matters
            payload["state_error"] = str(exc)
        return payload

    def _show_client(self, payload):
        if not self._alive():
            return
        self._show_gear((payload or {}).get("gear"))
        info = job_from_state((payload or {}).get("state"))
        saved_job = False
        if info is None:
            info = job_from_character(getattr(self.instance, "character", None))
            saved_job = info is not None
        if info is not None:
            self.job = info
            self.character_name = info.character or self.instance.name
            self.job_label.configure(
                text=info.label + (" · saved job" if saved_job else ""),
                fg=GOLD if saved_job else ACCENT)
            self._update_title()
            if not self._auto_loaded:
                self._auto_loaded = True
                self.defaults_var.set(info.abbr)
                if not self.sets:
                    self._load_defaults(info.abbr, auto=True)
        elif not self.sets:
            message = (payload or {}).get("state_error") or "job not detected yet"
            self.job_label.configure(text="job not detected", fg=GOLD)
            self.status.configure(text=str(message)[:220], fg=GOLD)
        if (payload or {}).get("state_error") and self.job is None:
            self.status.configure(text=str(payload["state_error"])[:220], fg=GOLD)

    def _show_gear(self, data):
        slots = (data or {}).get("slots") or {}
        for slot, _label, key in self.SLOTS:
            item = slots.get(key) or slots.get(str(slot)) or {}
            name = item.get("name") or "—"
            item_id = item.get("id")
            self._gear_labels[key].configure(
                text=name if not item_id else "%s  (%s)" % (name, item_id))

    def _gear_error(self, exc):
        if not self._alive():
            return
        self.status.configure(text=str(exc), fg=GOLD)
        self.job_label.configure(text="job not detected", fg=GOLD)

    def _change_slot(self, slot: str):
        name = simpledialog.askstring("Gear", "Item name for %s:" % slot, parent=self)
        if not name:
            return
        self.app.run_bg(lambda: self.instance.control().equip(slot, name),
                        lambda _r: self.refresh(),
                        lambda exc: self.status.configure(text=str(exc), fg=DANGER),
                        label="Changing gear…")

    # --- GearSwap ------------------------------------------------------------------------------
    def _load_defaults(self, abbr: str | None = None, *, auto: bool = False):
        code = str(abbr or self.defaults_var.get() or "").strip().upper()
        path = default_file(code)
        if path is None:
            folder = defaults_dir()
            where = " in %s" % folder if folder else ""
            self.status.configure(text="No %s default library found%s. Use Import your own…"
                                  % (code or "job", where), fg=GOLD)
            return
        if not auto and self.dirty and not messagebox.askyesno(
                "Replace current sets?",
                "Load the %s defaults and discard the unsaved edits?" % code, parent=self):
            return
        self.defaults_var.set(code)
        self.loaded_job = code
        self._load_file(path, source="%s defaults" % code)

    def _import(self):
        if self.dirty and not messagebox.askyesno(
                "Replace current sets?", "Import another file and discard the unsaved edits?",
                parent=self):
            return
        path = filedialog.askopenfilename(
            title="Choose a GearSwap Lua file", parent=self,
            filetypes=[("GearSwap Lua", "*.lua"), ("All files", "*.*")])
        if not path:
            return
        self.loaded_job = self.job.abbr if self.job else ""
        self._load_file(Path(path), source="imported · %s" % Path(path).name,
                        save_hint=Path(path).parent)

    def _load_file(self, path: Path, *, source: str, save_hint: Path | None = None):
        self._load_id += 1
        load_id = self._load_id
        self.status.configure(text="Reading %s…" % path.name, fg=MUTED)
        self.app.run_bg(lambda: self.instance.control().gearswap(str(path)),
                        lambda result: self._loaded_sets(result, source, path, save_hint, load_id),
                        lambda exc: self._load_error(exc, load_id),
                        label="Reading GearSwap sets…")

    def _load_error(self, exc, load_id: int):
        if load_id != self._load_id or not self._alive():
            return
        self.status.configure(text=str(exc), fg=DANGER)

    def _loaded_sets(self, result, source: str, path: Path, save_hint: Path | None,
                     load_id: int):
        if load_id != self._load_id or not self._alive():
            return
        self.set_details = flatten_sets_detailed((result or {}).get("sets") or {})
        self.sets = {
            path: {slot: detail["name"] for slot, detail in items.items()}
            for path, items in self.set_details.items()
        }
        self.source = source
        self.source_label.configure(text="SOURCE · " + source)
        self.save_dir = None
        self._save_hint = save_hint
        self._chosen_base = None
        self.last_saved = None
        self.dirty = False
        self._save_prompted = False
        if self._save_after is not None:
            try:
                self.after_cancel(self._save_after)
            except tk.TclError:
                pass
            self._save_after = None
        self._refresh_set_list(select_first=True)
        self._update_title()
        loaded_path = (result or {}).get("path") or str(path)
        if self.sets:
            self.status.configure(
                text="Loaded %d sets from %s. The first change asks where versions go; "
                     "later edits auto-save there." % (
                         len(self.sets), Path(loaded_path).name), fg=GREEN)
        else:
            self.status.configure(text="No sets found in %s." % Path(loaded_path).name, fg=GOLD)

    def _refresh_set_list(self, selected: str | None = None, select_first: bool = False):
        self._list_paths = sorted(self.sets, key=str.lower)
        self.set_list.delete(0, "end")
        for path in self._list_paths:
            self.set_list.insert("end", path)
        self._item_slots = []
        self.items_list.delete(0, "end")
        target = selected if selected in self.sets else None
        if target is None and select_first and self._list_paths:
            target = self._list_paths[0]
        if target is not None:
            index = self._list_paths.index(target)
            self.set_list.selection_clear(0, "end")
            self.set_list.selection_set(index)
            self.set_list.see(index)
        self._show_set()

    def _selected_set(self) -> str | None:
        selection = self.set_list.curselection()
        if not selection:
            return None
        index = int(selection[0])
        return self._list_paths[index] if index < len(self._list_paths) else None

    def _show_set(self, _event=None):
        path = self._selected_set()
        self.items_list.delete(0, "end")
        self._item_slots = []
        self.augment_label.configure(text="Select an item to see its augment build.")
        if not path:
            return
        items = self.sets.get(path, {})
        details = self.set_details.get(path, {})
        for slot in SLOT_KEYS:
            if items.get(slot):
                augments = (details.get(slot) or {}).get("augments") or []
                if not augments:
                    marker = ""
                elif items[slot].startswith(RANK30_PREFIXES):
                    marker = "  R30"
                else:
                    marker = "  *"
                self.items_list.insert(
                    "end", "%s: %s%s" % (SLOT_LABELS[slot], items[slot], marker))
                self._item_slots.append(slot)
        for slot, item in items.items():
            if slot not in SLOT_KEYS and item:
                self.items_list.insert("end", "%s: %s" % (slot, item))
                self._item_slots.append(slot)
        if self.items_list.size():
            chosen = 0
            for index, slot in enumerate(self._item_slots):
                if (details.get(slot) or {}).get("augments"):
                    chosen = index
                    break
            self.items_list.selection_clear(0, "end")
            self.items_list.selection_set(chosen)
            self._show_item_augments()

    def _show_item_augments(self, _event=None):
        path = self._selected_set()
        selection = self.items_list.curselection()
        if not path or not selection:
            return
        index = int(selection[0])
        if index >= len(self._item_slots):
            return
        slot = self._item_slots[index]
        detail = (self.set_details.get(path, {}).get(slot) or {})
        augments = detail.get("augments") or []
        if augments:
            prefix = ("R30 Augments: "
                      if (detail.get("name") or "").startswith(RANK30_PREFIXES)
                      else "Augments: ")
            self.augment_label.configure(
                text=prefix + "  |  ".join(augments), fg=TEXT)
        else:
            self.augment_label.configure(
                text="No augments recorded for this item.", fg=MUTED)

    def _edit_item(self, _event=None):
        path = self._selected_set()
        selection = self.items_list.curselection()
        if not path or not selection:
            return
        index = int(selection[0])
        if index >= len(self._item_slots):
            return
        slot = self._item_slots[index]
        old = self.sets.get(path, {}).get(slot, "")
        new = simpledialog.askstring(
            "GearSwap", "Item for %s (%s):" % (SLOT_LABELS.get(slot, slot), path),
            initialvalue=old, parent=self)
        if new is None:
            return
        items = dict(self.sets.get(path, {}))
        if new.strip():
            items[slot] = new.strip()
        else:
            items.pop(slot, None)
        try:
            items = clean_items(items)
            if not items:
                raise GearError("A set needs at least one item; use Delete set instead.")
        except GearError as exc:
            self.status.configure(text=str(exc), fg=DANGER)
            return
        self.sets[path] = items
        details = self.set_details.setdefault(path, {})
        if slot in items:
            if (details.get(slot) or {}).get("name") != items[slot]:
                details[slot] = {"name": items[slot], "augments": []}
        else:
            details.pop(slot, None)
        self._show_set()
        self._mark_dirty("Edited %s (%s)" % (path, SLOT_LABELS.get(slot, slot)))

    def _apply_set(self):
        path = self._selected_set()
        if not path:
            self.status.configure(text="Select a set first.", fg=GOLD)
            return
        items = [{"slot": slot, "item": self.sets[path][slot]}
                 for slot in SLOT_KEYS if self.sets[path].get(slot)]
        items += [{"slot": slot, "item": item} for slot, item in self.sets[path].items()
                  if slot not in SLOT_KEYS and item]
        self.status.configure(text="Wearing %s…" % path, fg=MUTED)
        self.app.run_bg(lambda: self.instance.control().call("equip_set", {"items": items},
                                                             timeout=30),
                        lambda _r: (self.status.configure(text="Wore %s" % path, fg=GREEN),
                                    self.refresh()),
                        lambda exc: self.status.configure(text=str(exc), fg=DANGER),
                        label="Wearing gear…")

    # --- editing sets --------------------------------------------------------------------------
    def item_choices(self, slot: str) -> list[str]:
        return item_choices(self.sets, slot)

    def path_conflict(self, path: str, original_path: str | None = None) -> str | None:
        existing = [other for other in self.sets if other != original_path] \
            if original_path else self.sets
        return path_conflict(path, existing)

    def apply_editor(self, path: str, items: dict[str, str], *,
                     original_path: str | None = None, mode: str = "new"):
        try:
            path = normalize_set_path(path)
            if path in self.sets and not (mode == "edit" and path == original_path):
                raise GearError("%s already exists; choose another path." % path)
            conflict = self.path_conflict(
                path, original_path if mode == "edit" else None)
            if conflict:
                raise GearError("%s collides with %s." % (path, conflict))
            items = clean_items(items)
            if not items:
                raise GearError("A set needs at least one item.")
            old_details = self.set_details.get(
                original_path if original_path else path, {})
            new_details = {}
            for slot, name in items.items():
                old = old_details.get(slot) or {}
                if old.get("name") == name:
                    new_details[slot] = old
                else:
                    new_details[slot] = {"name": name, "augments": []}
            if mode == "edit" and original_path and original_path != path:
                self.sets.pop(original_path, None)
                self.set_details.pop(original_path, None)
            self.sets[path] = items
            self.set_details[path] = new_details
        except GearError as exc:
            messagebox.showerror("GearSwap set", str(exc), parent=self)
            return False
        self._refresh_set_list(selected=path)
        action = {"edit": "Updated", "duplicate": "Duplicated"}.get(mode, "Added")
        self._mark_dirty("%s %s" % (action, path))
        return True

    def _new_set(self):
        SetEditorWindow(self, path="sets.idle.new", items={}, mode="new")

    def _duplicate_set(self):
        path = self._selected_set()
        if not path:
            self.status.configure(text="Select a set to duplicate.", fg=GOLD)
            return
        SetEditorWindow(self, path=path + " copy", items=dict(self.sets[path]),
                        original_path=path, mode="duplicate")

    def _edit_set(self):
        path = self._selected_set()
        if not path:
            self.status.configure(text="Select a set to edit.", fg=GOLD)
            return
        SetEditorWindow(self, path=path, items=dict(self.sets[path]),
                        original_path=path, mode="edit")

    def _delete_set(self):
        path = self._selected_set()
        if not path:
            self.status.configure(text="Select a set to delete.", fg=GOLD)
            return
        if not messagebox.askyesno("Delete set", "Remove %s from this library?" % path,
                                   parent=self):
            return
        self.sets.pop(path, None)
        self.set_details.pop(path, None)
        self._refresh_set_list(select_first=True)
        self._mark_dirty("Deleted %s" % path)

    # --- versioned saves -----------------------------------------------------------------------
    def _job_code(self) -> str:
        # The loaded library wins: loading NIN defaults while playing WAR should
        # save a NIN version, not a WAR one.
        if self.loaded_job:
            return self.loaded_job
        if self.job is not None:
            return self.job.abbr
        return "GEAR"

    def _version_base(self) -> str:
        if self._chosen_base:
            return self._chosen_base
        character = self.character_name
        if not character or character == "?":
            character = "Fanxi"
        return "%s-%s" % (character, self._job_code())

    def _update_title(self):
        mark = " · unsaved" if self.dirty else ""
        self.title("Gear — %s (%s)%s" % (self.character_name or self.instance.name,
                                        self._job_code(), mark))

    def _mark_dirty(self, message: str):
        self.dirty = True
        self._update_title()
        if self.save_dir is None:
            if not self._save_prompted:
                self._save_prompted = True
                self.status.configure(
                    text="%s · choose where this and later versions should go…" % message,
                    fg=GOLD)
                self.after(30, lambda: self._save_version(ask=True))
            else:
                self.status.configure(
                    text="%s · unsaved. Save version… chooses a folder." % message, fg=GOLD)
            return
        self.status.configure(text="%s · queued new version…" % message, fg=GOLD)
        if self._save_after is not None:
            try:
                self.after_cancel(self._save_after)
            except tk.TclError:
                pass
        self._save_after = self.after(1200, self._auto_save)

    def _auto_save(self):
        self._save_after = None
        if not self._alive():
            return
        if self.dirty and self.save_dir is not None:
            self._save_version(ask=False, quiet=True)

    def _save_version(self, *, ask: bool = True, quiet: bool = False) -> bool:
        if not self._alive():
            return False
        if not self.sets:
            if not quiet:
                self.status.configure(text="There are no sets to save.", fg=GOLD)
            return False
        folder = self.save_dir
        base = self._version_base()
        if ask or folder is None:
            initial_dir = folder or self._save_hint or downloads_dir()
            chosen = filedialog.asksaveasfilename(
                parent=self, title="Save GearSwap version",
                initialdir=str(initial_dir), initialfile=versioned_name(base),
                defaultextension=".lua",
                filetypes=[("GearSwap Lua", "*.lua"), ("All files", "*.*")])
            if not chosen:
                if not quiet:
                    self.status.configure(text="Save cancelled; changes are still in memory.",
                                          fg=MUTED)
                return False
            target = Path(chosen)
            folder = target.parent
            base = strip_version_suffix(target.stem) or base
            self._chosen_base = base
            self.save_dir = folder
            self._save_hint = folder
        when = datetime.now()
        try:
            path = save_version(folder, self.sets, base=base,
                                character=self.character_name, job=self._job_code(),
                                source=self.source, when=when)
        except (OSError, GearError) as exc:
            self.status.configure(text="Could not save: %s" % exc, fg=DANGER)
            if not quiet:
                messagebox.showerror("Save GearSwap version", str(exc), parent=self)
            return False
        profile = None
        try:
            profile = write_profile_snapshot(
                data_dir() / "gearswap", self.sets, character=self.character_name,
                job=self._job_code(), source=self.source, version_path=path, when=when)
        except OSError:
            profile = None
        self.dirty = False
        self.last_saved = path
        self._update_title()
        extra = " · profile copy in %s" % profile.parent if profile else ""
        self.status.configure(text="Saved %s%s" % (path, extra), fg=GREEN)
        return True

    def _on_close(self):
        if self._save_after is not None:
            try:
                self.after_cancel(self._save_after)
            except tk.TclError:
                pass
            self._save_after = None
        if self.dirty and self.sets and not self._save_version(ask=self.save_dir is None):
            return  # cancelled or failed: keep the window open with its edits
        self.destroy()


class SetEditorWindow(tk.Toplevel):
    """The full 16-slot form for a new, duplicated or edited set."""

    def __init__(self, owner: GearWindow, *, path: str, items: dict[str, str],
                 original_path: str | None = None, mode: str = "new"):
        super().__init__(owner)
        self.owner = owner
        self.app = owner.app
        self.original_path = original_path
        self.mode = mode
        title = {"new": "New GearSwap set", "edit": "Edit %s" % path,
                 "duplicate": "Duplicate %s" % (original_path or path)}.get(mode, "GearSwap set")
        self.title(title)
        self.configure(bg=BG)
        self.geometry("940x720")
        self.minsize(780, 640)
        self.transient(owner)
        self._entries: dict[str, tk.Entry] = {}
        self._build(path, items)
        self.after(50, self._grab)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _event: self.destroy())
        self.after(50, self._focus_path)

    def _build(self, path: str, items: dict[str, str]):
        head = tk.Frame(self, bg=BG, padx=24, pady=16)
        head.pack(fill="x")
        tk.Label(head, text="SET EDITOR", bg=BG, fg=MUTED,
                 font=(self.app.font, 9, "bold")).pack(anchor="w")
        tk.Label(head, text="Fill any of the sixteen slots. Empty slots are omitted; double-click "
                            "an item in the Gear window to edit one slot quickly.",
                 bg=BG, fg=TEXT, font=(self.app.font, 11), anchor="w", justify="left",
                 wraplength=860).pack(anchor="w", pady=(4, 0))

        path_box = tk.Frame(self, bg=BG, padx=24)
        path_box.pack(fill="x")
        tk.Label(path_box, text="SET PATH", bg=BG, fg=MUTED,
                 font=(self.app.font, 8, "bold")).pack(anchor="w")
        self.path_entry = tk.Entry(
            path_box, bg=PANEL_2, fg=TEXT, insertbackground=ACCENT, relief="flat",
            highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT,
            font=(self.app.mono, 11))
        self.path_entry.pack(fill="x", ipady=7, pady=(4, 0))
        self.path_entry.insert(0, path)

        grid = tk.Frame(self, bg=BG, padx=24, pady=14)
        grid.pack(fill="both", expand=True)
        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)
        for index, slot in enumerate(SLOT_KEYS):
            row, column = divmod(index, 2)
            cell = tk.Frame(grid, bg=BG)
            cell.grid(row=row, column=column, sticky="ew",
                      padx=(0, 16) if column == 0 else (0, 0), pady=4)
            tk.Label(cell, text=SLOT_LABELS[slot].upper(), bg=BG, fg=MUTED,
                     font=(self.app.font, 8, "bold")).pack(anchor="w")
            line = tk.Frame(cell, bg=PANEL_2, highlightthickness=1,
                            highlightbackground=BORDER)
            line.pack(fill="x")
            entry = tk.Entry(line, bg=PANEL_2, fg=TEXT, insertbackground=ACCENT,
                             relief="flat", highlightthickness=0, font=(self.app.mono, 10))
            entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(8, 0))
            picker = tk.Label(line, text="▾", bg=PANEL_2, fg=ACCENT, cursor="hand2",
                              font=(self.app.font, 11), padx=8)
            picker.pack(side="right", fill="y")
            picker.bind("<Button-1>", lambda event, key=slot: self._pick(key, event))
            if items.get(slot):
                entry.insert(0, items[slot])
            self._entries[slot] = entry

        footer = tk.Frame(self, bg=BG, padx=24, pady=16)
        footer.pack(fill="x")
        tk.Label(footer, text="The path is a table path: sets.idle.pdt, sets.WS.Savage Blade, …",
                 bg=BG, fg=MUTED, font=(self.app.font, 9)).pack(side="left")
        ActionButton(footer, "Save set", self._save, kind="primary", padx=16,
                     pady=7).pack(side="right")
        ActionButton(footer, "Cancel", self.destroy, kind="ghost", padx=12,
                     pady=7).pack(side="right", padx=(0, 8))

    def _grab(self):
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _focus_path(self):
        try:
            self.path_entry.focus_set()
            self.path_entry.selection_range(0, "end")
        except tk.TclError:
            pass

    def _pick(self, slot: str, event):
        choices = self.owner.item_choices(slot)
        menu = tk.Menu(self, tearoff=0, bg=PANEL_2, fg=TEXT, activebackground=ACCENT,
                       activeforeground="#05202c", activeborderwidth=0, borderwidth=0,
                       font=(self.app.font, 10))
        if choices:
            menu.add_command(label="(clear)", command=lambda: self._set_item(slot, ""))
            menu.add_separator()
            for name in choices:
                menu.add_command(label=name, command=lambda n=name: self._set_item(slot, n))
        else:
            menu.add_command(label="No items for this slot in the loaded library",
                             state="disabled")
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _set_item(self, slot: str, name: str):
        entry = self._entries[slot]
        entry.delete(0, "end")
        if name:
            entry.insert(0, name)
        entry.focus_set()

    def _save(self):
        try:
            path = normalize_set_path(self.path_entry.get())
            items = {}
            for slot, entry in self._entries.items():
                value = entry.get().strip()
                if value:
                    items[slot] = value
            items = clean_items(items)
            if not items:
                raise GearError("A set needs at least one item.")
            if path in self.owner.sets and not (
                    self.mode == "edit" and path == self.original_path):
                raise GearError("%s already exists; choose another path." % path)
            original = self.original_path if self.mode == "edit" else None
            conflict = self.owner.path_conflict(path, original)
            if conflict:
                raise GearError("%s collides with %s." % (path, conflict))
            if self.mode == "duplicate" and path == self.original_path:
                raise GearError("Choose a new path for the duplicate.")
        except GearError as exc:
            messagebox.showerror("GearSwap set", str(exc), parent=self)
            return
        if self.owner.apply_editor(path, items, original_path=self.original_path,
                                   mode=self.mode):
            self.destroy()

def run(config: LauncherConfig | None = None) -> int:
    app = LauncherApp(config)
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
    return 0
