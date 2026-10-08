"""Plays a short system alert sound, without adding a Qt Multimedia
dependency or blocking the GUI thread waiting for playback to finish.

Preference order:
  1. `canberra-gtk-play` — respects the user's actual configured desktop
     sound theme (correct on GNOME/KDE alike), if installed.
  2. `paplay` against a standard freedesktop sound-theme file, if present
     (the sound-theme-freedesktop package is common on most desktop
     installs, but not guaranteed).
  3. Qt's own simple system beep, which always works but is a plain
     beep rather than a themed sound.
"""
import os
import shutil
import subprocess

from PySide6.QtWidgets import QApplication

_FREEDESKTOP_SOUND_PATHS = [
    "/usr/share/sounds/freedesktop/stereo/complete.oga",
    "/usr/share/sounds/freedesktop/stereo/message.oga",
]


def play_alert_sound():
    if shutil.which("canberra-gtk-play"):
        if _run_detached(["canberra-gtk-play", "-i", "complete"]):
            return

    if shutil.which("paplay"):
        for path in _FREEDESKTOP_SOUND_PATHS:
            if os.path.exists(path):
                if _run_detached(["paplay", path]):
                    return

    QApplication.beep()


def _run_detached(cmd: list[str]) -> bool:
    """Fires off playback without waiting for it, so a slow/hanging player
    can never block the GUI. Returns whether the process actually launched.
    """
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (OSError, subprocess.SubprocessError):
        return False
