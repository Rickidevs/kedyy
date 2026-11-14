"""KEDYY — a cat that pops up at random times during the day and quizzes you on your own cards.

Usage:
  kedyy                 open settings (starts the background service if it isn't running)
  kedyy --background    run in the background only (used at login)
  kedyy --now           ask a question right now
  kedyy --once          show one question and quit (for testing)
"""
import os

# Wayland doesn't let apps place their own windows; XWayland does, so the popup can sit in a corner.
os.environ.setdefault("GDK_BACKEND", "x11")

import json
import random
import signal
import sys

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gdk, Gio, GLib, Gtk, WebKit2  # noqa: E402

from . import i18n, store  # noqa: E402
from .deck import Deck  # noqa: E402
from .idle import IdleMonitor  # noqa: E402

APP_ID = "io.github.kedyy.Kedyy"
HERE = os.path.dirname(os.path.abspath(__file__))
UI = os.path.join(HERE, "ui")
ICON = os.path.join(HERE, "kedyy.svg")
FIRST_MIN, FIRST_MAX = 3, 10           # first question after login (minutes)
WIDTH = 400
MARGIN = 14


def log(*a):
    print("[kedyy]", *a, flush=True)


def make_webview(handler, on_message, strings):
    ucm = WebKit2.UserContentManager()
    ucm.connect("script-message-received::" + handler, on_message)
    ucm.register_script_message_handler(handler)
    inject_strings(ucm, strings)
    wv = WebKit2.WebView.new_with_user_content_manager(ucm)
    s = wv.get_settings()
    s.set_enable_developer_extras(bool(os.environ.get("KEDYY_DEBUG")))
    s.set_allow_file_access_from_file_urls(True)
    s.set_media_playback_requires_user_gesture(False)
    if not os.environ.get("KEDYY_DEBUG"):
        wv.connect("context-menu", lambda *a: True)
    return wv


def inject_strings(ucm, strings):
    ucm.remove_all_scripts()
    ucm.add_script(WebKit2.UserScript.new(
        "window.I18N = %s;" % json.dumps(strings, ensure_ascii=False),
        WebKit2.UserContentInjectedFrames.TOP_FRAME, WebKit2.UserScriptInjectionTime.START, None, None))


def read_msg(result):
    try:
        return json.loads(result.get_js_value().to_string())
    except Exception as e:  # noqa: BLE001
        log("bad message", e)
        return {}


def run_js(wv, code):
    wv.evaluate_javascript(code, -1, None, None, None, None, None)


def ui_uri(name):
    return "file://" + os.path.join(UI, name)


# ---------------------------------------------------------------- question popup
class Popup:
    def __init__(self, app, question, strings, corner, on_answer, on_closed):
        self.q = question
        self.corner = corner
        self.on_answer = on_answer
        self.on_closed = on_closed
        self.shown = False
        self.done = False
        self.height = 520

        w = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        if app:
            w.set_application(app)
        w.set_title("KEDYY")
        w.set_decorated(False)
        w.set_resizable(True)
        w.set_keep_above(True)
        w.set_skip_taskbar_hint(True)
        w.set_skip_pager_hint(True)
        w.stick()
        w.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        w.set_focus_on_map(False)   # don't steal the keyboard while you're typing; click to focus
        w.set_app_paintable(True)
        screen = w.get_screen()
        visual = screen.get_rgba_visual()
        if visual is not None and screen.is_composited():
            w.set_visual(visual)
        w.set_default_size(WIDTH, self.height)
        self.win = w

        wv = make_webview("kedi", self._on_message, strings)
        wv.set_background_color(Gdk.RGBA(0, 0, 0, 0))
        wv.connect("load-changed", self._on_load)
        self.wv = wv
        w.add(wv)
        wv.load_uri(ui_uri("index.html"))

    def _place(self):
        display = Gdk.Display.get_default()
        mon = display.get_primary_monitor() or display.get_monitor(0)
        wa = mon.get_workarea()
        left = self.corner.endswith("left")
        top = self.corner.startswith("top")
        x = wa.x + MARGIN if left else wa.x + wa.width - WIDTH - MARGIN
        y = wa.y + MARGIN if top else wa.y + wa.height - self.height - MARGIN
        self.win.resize(WIDTH, self.height)
        self.win.move(x, y)

    def _on_load(self, wv, event):
        if event == WebKit2.LoadEvent.FINISHED:
            run_js(self.wv, "window.showQuestion(%s);" % json.dumps(self.q, ensure_ascii=False))
            if not self.shown:
                self.shown = True
                self._place()
                self.win.show_all()
                self._place()
                GLib.timeout_add(250, lambda: (run_js(self.wv, "window.enter();"), False)[1])

    def _on_message(self, ucm, result):
        msg = read_msg(result)
        t = msg.get("type")
        if t == "size":
            h = int(msg.get("h", 0))
            if h > 50 and h != self.height:
                self.height = h
                self._place()
        elif t == "answer":
            self.on_answer(msg["id"], bool(msg["correct"]))
        elif t == "closed":
            self.destroy(msg.get("reason", ""))

    def destroy(self, reason=""):
        if self.done:
            return
        self.done = True
        self.win.destroy()
        self.on_closed(reason)


# ---------------------------------------------------------------- settings window
class SettingsWindow:
    def __init__(self, svc):
        self.svc = svc
        w = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        w.set_application(svc.app)
        w.set_title("KEDYY")
        w.set_default_size(580, 800)
        w.set_position(Gtk.WindowPosition.CENTER)
        if os.path.exists(ICON):
            w.set_icon_from_file(ICON)
        w.connect("destroy", self._on_destroy)
        self.win = w
        self.wv = make_webview("settings", self._on_message, svc.strings)
        w.add(self.wv)
        self.wv.load_uri(ui_uri("settings.html"))
        w.show_all()

    def present(self):
        self.win.present()

    def reload(self):
        inject_strings(self.wv.get_user_content_manager(), self.svc.strings)
        self.wv.reload()

    def _on_destroy(self, *_):
        self.svc.settings_win = None

    def push_state(self, toast=None, error=None):
        st = self.svc.state()
        if toast:
            st["toast"] = toast
        if error:
            st["error"] = error
        run_js(self.wv, "window.setState(%s);" % json.dumps(st, ensure_ascii=False))

    def _on_message(self, ucm, result):
        msg = read_msg(result)
        t = msg.get("type")
        s = self.svc.strings
        if t == "ready":
            self.push_state()
        elif t == "save":
            if self.svc.apply_settings(msg.get("settings", {})):
                self.reload()               # language changed
            else:
                self.push_state(toast=s["saved"])
        elif t == "ask":
            self.svc.show()
        elif t == "import":
            self._import()
        elif t == "toggle_deck":
            off = set(store.load_settings()["disabled_decks"])
            (off.discard if msg.get("on") else off.add)(msg["name"])
            self.svc.apply_settings({"disabled_decks": sorted(off)})
            self.push_state()
        elif t == "delete_deck":
            store.delete_deck(msg["name"])
            self.svc.reload_cards()
            self.push_state(toast=s["deleted"].replace("{name}", msg["name"]))
        elif t == "reset_progress":
            self.svc.deck.reset()
            self.push_state(toast=s["progress_reset"])

    def _import(self):
        s = self.svc.strings
        dlg = Gtk.FileChooserNative.new(s["dlg_title"], self.win, Gtk.FileChooserAction.OPEN, s["dlg_add"], s["dlg_cancel"])
        dlg.set_select_multiple(True)
        flt = Gtk.FileFilter()
        flt.set_name(s["dlg_filter"])
        for ext in store.SUPPORTED:
            flt.add_pattern("*" + ext)
            flt.add_pattern("*" + ext.upper())
        dlg.add_filter(flt)
        if dlg.run() != Gtk.ResponseType.ACCEPT:
            return
        added, errors = [], []
        for path in dlg.get_filenames():
            try:
                name, n = store.import_file(path)
                added.append(f"{name} ({n})")
            except ValueError as e:
                key = "err_unsupported" if str(e) == "unsupported" else "err_empty"
                errors.append(f"{os.path.basename(path)}: " + s[key].replace("{list}", ", ".join(store.SUPPORTED)))
            except OSError as e:
                errors.append(f"{os.path.basename(path)}: {e}")
        if added:
            self.svc.reload_cards()
        self.push_state(toast=s["added"].replace("{list}", ", ".join(added)) if added else None,
                        error="\n".join(errors) or None)


# ---------------------------------------------------------------- background service
class Service:
    def __init__(self, app=None, once=False):
        self.app = app
        self.once = once
        self.settings = store.load_settings()
        self.strings = i18n.load(self.settings["language"])
        cards, metas = store.load_cards(self.settings)
        self.deck = Deck(cards, metas, self.settings)
        self.popup = None
        self.timer = None
        self.next_at = None
        self.settings_win = None
        self.idle = IdleMonitor()
        log(f"{len(cards)} cards loaded · data: {store.DATA_DIR} · idle: {self.idle.method} · ui: {self.strings['_code']}")

    def state(self):
        st = self.deck.progress["stats"]
        return {
            "settings": self.settings,
            "decks": store.decks(),
            "languages": i18n.available(),
            "stats": {"correct": st["correct"], "wrong": st["wrong"],
                      "learned": self.deck.learned_count(), "total": len(self.deck.items)},
            "next_at": self.next_at,
            "formats": list(store.SUPPORTED),
        }

    def reload_cards(self):
        cards, metas = store.load_cards(self.settings)
        self.deck.set_cards(cards, metas)
        log(f"{len(cards)} cards loaded")

    def apply_settings(self, new):
        """Save settings. Returns True if the interface language changed."""
        old = self.settings
        self.settings = store.save_settings(new)
        self.deck.settings = self.settings
        if old.get("disabled_decks") != self.settings["disabled_decks"]:
            self.reload_cards()
        if any(old.get(k) != self.settings[k] for k in ("enabled", "min_gap", "max_gap")) \
                and not self.popup and not self.once:
            self.schedule_next()
        if old.get("language") != self.settings["language"]:
            self.strings = i18n.load(self.settings["language"])
            return True
        return False

    # ---- timing ----
    def _cancel(self):
        if self.timer:
            GLib.source_remove(self.timer)
        self.timer = None
        self.next_at = None

    def schedule(self, lo_min, hi_min):
        self._cancel()
        if not self.settings["enabled"]:
            log("questions paused")
            return
        secs = random.randint(int(lo_min * 60), max(int(lo_min * 60), int(hi_min * 60)))
        log(f"next question in {secs // 60} min {secs % 60} s")
        self.next_at = int(GLib.get_real_time() / 1e6) + secs
        self.timer = GLib.timeout_add_seconds(secs, self._tick)

    def schedule_next(self, short=False):
        lo, hi = self.settings["min_gap"], self.settings["max_gap"]
        if short:   # not answered: come back a bit sooner
            lo, hi = max(1, lo / 2), max(1, hi / 2)
        self.schedule(lo, hi)

    def _tick(self):
        self.timer = None
        limit = self.settings["idle_limit"] * 60 * 1000
        if limit and self.idle.idle_ms() > limit:
            # you're away: check again every minute until you're back
            self.timer = GLib.timeout_add_seconds(60, self._tick)
            self.next_at = int(GLib.get_real_time() / 1e6) + 60
            return False
        self.show()
        return False

    # ---- questions ----
    def show(self):
        if self.popup:
            self.popup.win.present()
            return
        q = self.deck.pick()
        if not q:
            log("no cards")
            return
        self._cancel()
        log("question:", q["shown"])
        self.popup = Popup(self.app, q, self.strings, self.settings["corner"], self._answered, self._closed)

    def _answered(self, item_id, correct):
        log("answer:", item_id, "right" if correct else "wrong")
        self.deck.record(item_id, correct)
        if self.settings_win:
            self.settings_win.push_state()

    def _closed(self, reason):
        log("closed:", reason)
        self.popup = None
        if self.once:
            Gtk.main_quit()
            return
        self.schedule_next(short=reason in ("later", "timeout"))
        if self.settings_win:
            self.settings_win.push_state()

    def open_settings(self):
        if self.settings_win:
            self.settings_win.present()
        else:
            self.settings_win = SettingsWindow(self)


class KedyyApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.svc = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        GLib.set_application_name("KEDYY")
        if os.path.exists(ICON):
            Gtk.Window.set_default_icon_from_file(ICON)
        self.svc = Service(self)
        self.hold()     # keep running without any window
        self.svc.schedule(FIRST_MIN, FIRST_MAX)
        for sig in (signal.SIGINT, signal.SIGTERM):
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: (self.quit(), False)[1])

    def do_command_line(self, cmd):
        args = cmd.get_arguments()[1:]
        if "--now" in args:
            self.svc.show()
        elif "--background" not in args:
            self.svc.open_settings()
        return 0


def main():
    os.makedirs(store.DATA_DIR, exist_ok=True)
    GLib.set_prgname("kedyy")
    if "--once" in sys.argv:
        svc = Service(once=True)
        svc.show()
        Gtk.main()
        return
    if "-h" in sys.argv or "--help" in sys.argv:
        print(__doc__)
        return
    sys.exit(KedyyApp().run(sys.argv))
