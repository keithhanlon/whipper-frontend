"""About window: app name, version, links, license, and the versions of the
pieces it runs on (useful to paste into a bug report)."""
import os
import platform

from PySide6 import __version__ as PYSIDE_VERSION
from PySide6.QtCore import QProcess, Qt, qVersion
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from whippergui import __version__

APP_NAME = "Whipper Frontend"
REPO_URL = "https://github.com/keithhanlon/whipper-frontend"
ISSUES_URL = REPO_URL + "/issues"
RELEASES_URL = REPO_URL + "/releases"
WHIPPER_URL = "https://github.com/whipper-team/whipper"
LOGCHECKER_URL = "https://github.com/OPSnet/Logchecker"
COPYRIGHT = "© 2026 Keith Hanlon"

_ICON_PATH = os.path.join(os.path.dirname(__file__), "icon.svg")


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setMinimumWidth(460)

        self._whipper_version = "checking…"

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ---- Header: icon + name + version ------------------------------
        header = QHBoxLayout()
        header.setSpacing(14)

        icon_label = QLabel()
        pixmap = QPixmap(_ICON_PATH)
        if not pixmap.isNull():
            icon_label.setPixmap(
                pixmap.scaled(
                    72, 72,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        header.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)

        title_box = QVBoxLayout()
        name_label = QLabel(f"<h2 style='margin:0'>{APP_NAME}</h2>")
        version_label = QLabel(f"Version {__version__}")
        tagline = QLabel(
            "A graphical interface for whipper,\n"
            "the accurate CD ripper for Linux."
        )
        title_box.addWidget(name_label)
        title_box.addWidget(version_label)
        title_box.addSpacing(4)
        title_box.addWidget(tagline)
        title_box.addStretch(1)
        header.addLayout(title_box, 1)
        layout.addLayout(header)

        # ---- Links -------------------------------------------------------
        links = QLabel(
            f'<a href="{REPO_URL}">Project page on GitHub</a> &nbsp;·&nbsp; '
            f'<a href="{RELEASES_URL}">Releases</a> &nbsp;·&nbsp; '
            f'<a href="{ISSUES_URL}">Report a bug</a>'
        )
        links.setOpenExternalLinks(True)
        links.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        layout.addWidget(links)

        # ---- License / credits -------------------------------------------
        credits = QLabel(
            f"{COPYRIGHT}<br>"
            "Released under the "
            '<a href="https://www.gnu.org/licenses/gpl-3.0.html">GNU GPL v3</a>. '
            "This program comes with no warranty.<br><br>"
            "Does the actual ripping with "
            f'<a href="{WHIPPER_URL}">whipper</a> '
            "and checks logs with "
            f'<a href="{LOGCHECKER_URL}">OPSnet’s Logchecker</a>. '
            "Both are the work of their respective authors; this app is an "
            "independent frontend and is not affiliated with either project."
        )
        credits.setWordWrap(True)
        credits.setOpenExternalLinks(True)
        credits.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        layout.addWidget(credits)

        # ---- Environment (also what "Copy details" copies) ---------------
        self._env_label = QLabel()
        self._env_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self._env_label)
        self._refresh_env_label()

        # ---- Buttons -----------------------------------------------------
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        copy_btn = QPushButton("Copy details")
        copy_btn.setToolTip("Copy version info to the clipboard, handy for bug reports.")
        copy_btn.clicked.connect(self._copy_details)
        buttons.addButton(copy_btn, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._lookup_whipper_version()

    # ---- Environment details ---------------------------------------------

    def _details_text(self) -> str:
        return (
            f"{APP_NAME} {__version__}\n"
            f"whipper: {self._whipper_version}\n"
            f"Qt {qVersion()} / PySide6 {PYSIDE_VERSION}\n"
            f"Python {platform.python_version()}\n"
            f"{platform.system()} {platform.release()}"
        )

    def _refresh_env_label(self):
        self._env_label.setText(self._details_text().replace("\n", "<br>"))

    def _copy_details(self):
        QGuiApplication.clipboard().setText(self._details_text())

    def _lookup_whipper_version(self):
        """Ask `whipper --version` asynchronously, so a slow start never
        freezes the window."""
        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._proc.finished.connect(self._on_version_finished)
        self._proc.errorOccurred.connect(self._on_version_error)
        self._proc.start("whipper", ["--version"])

    def _on_version_finished(self, *_):
        out = bytes(self._proc.readAllStandardOutput()).decode(errors="replace").strip()
        # Typically "whipper 0.10.0"; keep just the version token if present.
        last_line = out.splitlines()[-1] if out else ""
        parts = last_line.split()
        self._whipper_version = parts[-1] if parts else "unknown"
        self._refresh_env_label()

    def _on_version_error(self, *_):
        self._whipper_version = "not found"
        self._refresh_env_label()
