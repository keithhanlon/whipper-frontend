"""Tabbed Settings window: General / File Naming / Cover Art / Log Verification."""
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from whippergui.log_verify import find_logchecker
from whippergui.settings import Settings
from whippergui.templates_dialog import TemplatesDialog
from whippergui.whipper_config import get_path_filter_vfat, set_path_filter_vfat

# (label, value passed to whipper's -C flag; "" = don't fetch)
_COVER_ART_OPTIONS = [
    ("Don't fetch cover art", ""),
    ("Save as cover.jpg in the album folder", "file"),
    ("Embed in each FLAC file", "embed"),
    ("Both — save cover.jpg AND embed", "complete"),
]


class SettingsDialog(QDialog):
    """All app settings, applied instantly as each control changes (same
    behavior as the flat menu this replaces) — there's no separate
    OK/Cancel state to reconcile, just a Close button.
    """

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(480, 380)
        self.settings = settings

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._build_general_tab(), "General")
        tabs.addTab(self._build_file_naming_tab(), "File Naming")
        tabs.addTab(self._build_cover_art_tab(), "Cover Art")
        tabs.addTab(self._build_log_verification_tab(), "Log Verification")
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.accept)
        layout.addWidget(buttons)

    # ---- General ---------------------------------------------------

    def _build_general_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        allow_unknown = QCheckBox("Rip even if metadata not found")
        allow_unknown.setChecked(self.settings.allow_unknown)
        allow_unknown.setToolTip(
            "Without this, whipper refuses to rip entirely when it can't find "
            "the disc on MusicBrainz, and just prints a submission URL instead."
        )
        allow_unknown.toggled.connect(
            lambda checked: setattr(self.settings, "allow_unknown", checked)
        )
        layout.addWidget(allow_unknown)

        keep_going = QCheckBox("Keep ripping remaining tracks if one fails")
        keep_going.setChecked(self.settings.keep_going)
        keep_going.setToolTip(
            "Without this, whipper aborts the whole disc if a single track "
            "can't be ripped after all retries — useful for scratched or "
            "damaged CDs where you'd rather get the tracks that DO work."
        )
        keep_going.toggled.connect(
            lambda checked: setattr(self.settings, "keep_going", checked)
        )
        layout.addWidget(keep_going)

        eject = QCheckBox("Eject disc when rip finishes")
        eject.setChecked(self.settings.eject_when_done)
        eject.toggled.connect(
            lambda checked: setattr(self.settings, "eject_when_done", checked)
        )
        layout.addWidget(eject)

        layout.addStretch(1)
        return widget

    # ---- File Naming -----------------------------------------------

    def _build_file_naming_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.vfat_check = QCheckBox("Sanitize filenames for other filesystems (VFAT/exFAT)")
        self.vfat_check.setChecked(get_path_filter_vfat())
        self.vfat_check.setToolTip(
            'Replaces characters illegal on VFAT/exFAT/Windows filesystems '
            '(" * / : < > ? \\ |) with underscores in ripped filenames — '
            "useful when your output folder is on a network share or drive "
            "formatted for Windows/macOS. Only affects rips done AFTER this "
            "is enabled; existing files are not renamed."
        )
        self.vfat_check.toggled.connect(self._on_vfat_toggled)
        layout.addWidget(self.vfat_check)

        templates_btn = QPushButton("Edit Track/Disc Naming Templates…")
        templates_btn.clicked.connect(self._open_templates_dialog)
        layout.addWidget(templates_btn)

        layout.addStretch(1)
        return widget

    def _open_templates_dialog(self):
        dialog = TemplatesDialog(
            self.settings.track_template, self.settings.disc_template, parent=self
        )
        if dialog.exec() and dialog.track_template is not None:
            self.settings.track_template = dialog.track_template
            self.settings.disc_template = dialog.disc_template

    def _on_vfat_toggled(self, checked: bool):
        try:
            set_path_filter_vfat(checked)
        except OSError as e:
            QMessageBox.critical(
                self,
                "Couldn't update whipper.conf",
                f"Failed to write the setting to whipper's config file:\n{e}",
            )
            self.vfat_check.blockSignals(True)
            self.vfat_check.setChecked(not checked)
            self.vfat_check.blockSignals(False)

    # ---- Cover Art ---------------------------------------------------

    def _build_cover_art_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        current = self.settings.cover_art
        for label, value in _COVER_ART_OPTIONS:
            radio = QRadioButton(label)
            radio.setChecked(value == current)
            radio.toggled.connect(
                lambda checked, v=value: setattr(self.settings, "cover_art", v)
                if checked
                else None
            )
            layout.addWidget(radio)

        layout.addStretch(1)
        return widget

    # ---- Log Verification -------------------------------------------

    def _build_log_verification_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        intro = QLabel(
            "Scores a finished rip's .log file using OPSnet's logchecker.\n\n"
            "Requires PHP (php-cli) and logchecker.phar, downloaded from:\n"
            "github.com/OPSnet/Logchecker/releases"
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        path_row = QHBoxLayout()
        self.logchecker_edit = QLineEdit(self.settings.logchecker_path)
        self.logchecker_edit.setPlaceholderText(
            "Leave blank to look for 'logchecker' on your PATH"
        )
        self.logchecker_edit.textChanged.connect(
            lambda text: setattr(self.settings, "logchecker_path", text)
        )
        path_row.addWidget(self.logchecker_edit)

        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_for_logchecker)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        self.logchecker_status = QLabel()
        layout.addWidget(self.logchecker_status)
        self._update_logchecker_status()
        self.logchecker_edit.textChanged.connect(self._update_logchecker_status)

        layout.addStretch(1)
        return widget

    def _browse_for_logchecker(self):
        path, _ = QFileDialog.getOpenFileName(self, "Locate logchecker or logchecker.phar")
        if path:
            self.logchecker_edit.setText(path)

    def _update_logchecker_status(self):
        found = find_logchecker(self.settings.logchecker_path)
        if found:
            self.logchecker_status.setText(f"Found: {found}")
            self.logchecker_status.setStyleSheet("color: green;")
        else:
            self.logchecker_status.setText("Not found")
            self.logchecker_status.setStyleSheet("color: darkorange;")
