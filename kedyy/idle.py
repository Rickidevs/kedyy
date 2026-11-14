"""How long has the user been away? Tries several desktop APIs, returns milliseconds (0 if unknown)."""
import shutil
import subprocess

from gi.repository import Gio, GLib


class IdleMonitor:
    def __init__(self):
        self._method = None
        self._proxy = None
        candidates = [
            # GNOME (and GNOME-based desktops like Zorin, Ubuntu): milliseconds
            ("mutter", "org.gnome.Mutter.IdleMonitor", "/org/gnome/Mutter/IdleMonitor/Core",
             "org.gnome.Mutter.IdleMonitor", "GetIdletime"),
            # KDE Plasma and others implementing the freedesktop screensaver API: milliseconds
            ("screensaver", "org.freedesktop.ScreenSaver", "/org/freedesktop/ScreenSaver",
             "org.freedesktop.ScreenSaver", "GetSessionIdleTime"),
        ]
        for name, bus, path, iface, method in candidates:
            try:
                proxy = Gio.DBusProxy.new_for_bus_sync(Gio.BusType.SESSION, Gio.DBusProxyFlags.NONE,
                                                       None, bus, path, iface, None)
                proxy.call_sync(method, None, Gio.DBusCallFlags.NONE, 1000, None)
                self._proxy, self._call, self._method = proxy, method, name
                return
            except GLib.Error:
                continue
        if shutil.which("xprintidle"):      # X11 fallback
            self._method = "xprintidle"

    @property
    def method(self):
        return self._method or "none"

    def idle_ms(self):
        try:
            if self._proxy:
                return int(self._proxy.call_sync(self._call, None, Gio.DBusCallFlags.NONE, 1000, None).unpack()[0])
            if self._method == "xprintidle":
                return int(subprocess.run(["xprintidle"], capture_output=True, text=True, timeout=2).stdout.strip() or 0)
        except (GLib.Error, ValueError, OSError, subprocess.SubprocessError):
            pass
        return 0
