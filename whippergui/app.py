"""Application bootstrap for Whipper Frontend."""
import os
import shutil
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from whippergui.main_window import MainWindow

_ICON_PATH = os.path.join(os.path.dirname(__file__), "icon.svg")


def _check_whipper_installed() -> bool:
    return shutil.which("whipper") is not None


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Whipper Frontend")
    app.setOrganizationName("citizenkeith")

    # Explicit icon, rather than relying solely on the .desktop file /
    # icon-theme lookup — that helps the app *launcher* find an icon, but
    # a running window's taskbar icon comes from the window itself
    # (_NET_WM_ICON), which Qt only sets if asked to.
    if os.path.exists(_ICON_PATH):
        app.setWindowIcon(QIcon(_ICON_PATH))

    if not _check_whipper_installed():
        QMessageBox.critical(
            None,
            "Whipper not found",
            "The 'whipper' command was not found on your PATH.\n\n"
            "Install it first, e.g.:\n"
            "  sudo apt install whipper\n"
            "or see https://github.com/whipper-team/whipper",
        )
        return 1

    window = MainWindow()
    window.show()
    return app.exec()
