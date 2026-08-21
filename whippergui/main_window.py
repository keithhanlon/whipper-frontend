"""Main window: drive selection, track table, rip controls, progress + log."""
import glob
import os
import subprocess

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from whippergui.device_utils import DriveInfo, list_drives
from whippergui.log_verify import find_logchecker, verify_log
from whippergui.log_verify_dialog import LogVerifyDialog
from whippergui.offset_dialog import OffsetDialog
from whippergui.offset_utils import find_offset_for_drive
from whippergui.rip_worker import RipOptions, RipWorker
from whippergui.settings import Settings
from whippergui.settings_dialog import SettingsDialog

TRACK_COLUMNS = ["#", "Filename", "Status"]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Whipper Frontend")
        self.resize(920, 680)

        self.settings = Settings()
        self.worker: RipWorker | None = None
        self._drives: list[DriveInfo] = []
        self._current_rip_output_dir: str | None = None

        self._build_ui()
        self._build_menu()
        self._refresh_drives()

    # ---- UI construction -------------------------------------------------

    def _build_menu(self):
        settings_menu = self.menuBar().addMenu("&Settings")

        preferences_action = QAction("Preferences…", self)
        preferences_action.triggered.connect(self._open_settings_dialog)
        settings_menu.addAction(preferences_action)

        tools_menu = self.menuBar().addMenu("&Tools")

        verify_log_action = QAction("Verify Log…", self)
        verify_log_action.triggered.connect(self._start_log_verification)
        tools_menu.addAction(verify_log_action)

    def _start_log_verification(self):
        binary = find_logchecker(self.settings.logchecker_path)
        if not binary:
            QMessageBox.warning(
                self,
                "logchecker not found",
                "Couldn't find a logchecker to run.\n\n"
                "Set its location in Settings → Log Verification, or "
                "install it so 'logchecker' is on your PATH.",
            )
            return

        log_path, _ = QFileDialog.getOpenFileName(
            self, "Select a rip log to verify", self.settings.output_dir, "Log files (*.log)"
        )
        if not log_path:
            return

        result = verify_log(log_path, binary)
        dialog = LogVerifyDialog(result, log_path, parent=self)
        dialog.exec()

    def _open_settings_dialog(self):
        dialog = SettingsDialog(self.settings, parent=self)
        dialog.exec()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        layout.addLayout(self._build_top_bar())
        self.album_label = QLabel("")
        self.album_label.setStyleSheet("font-weight: bold;")
        self.album_label.setWordWrap(True)
        layout.addWidget(self.album_label)
        layout.addWidget(self._build_track_table())
        layout.addWidget(self._build_progress_area())
        layout.addWidget(self._build_log_pane())
        layout.addLayout(self._build_action_bar())

    def _build_top_bar(self) -> QHBoxLayout:
        row = QHBoxLayout()

        row.addWidget(QLabel("Drive:"))
        self.drive_combo = QComboBox()
        self.drive_combo.currentIndexChanged.connect(self._update_offset_label)
        row.addWidget(self.drive_combo, stretch=1)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_drives)
        row.addWidget(refresh_btn)

        self.offset_label = QLabel("Offset: —")
        self.offset_label.setStyleSheet("color: gray;")
        row.addWidget(self.offset_label)

        offset_btn = QPushButton("Offset…")
        offset_btn.clicked.connect(self._open_offset_dialog)
        row.addWidget(offset_btn)

        format_note = QLabel("Format: FLAC")
        format_note.setStyleSheet("color: gray;")
        row.addWidget(format_note)

        self.output_dir_label = QLabel(self.settings.output_dir)
        self.output_dir_label.setStyleSheet("color: gray;")
        row.addWidget(self.output_dir_label, stretch=2)

        choose_dir_btn = QPushButton("Choose Output Folder…")
        choose_dir_btn.clicked.connect(self._choose_output_dir)
        row.addWidget(choose_dir_btn)

        return row

    def _build_track_table(self) -> QTableWidget:
        self.track_table = QTableWidget(0, len(TRACK_COLUMNS))
        self.track_table.setHorizontalHeaderLabels(TRACK_COLUMNS)
        self.track_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.track_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.track_table.verticalHeader().setVisible(False)
        return self.track_table

    def _on_album_info(self, artist: str, title: str):
        self.album_label.setText(f"{artist} — {title}")

    def _on_track_filename(self, track_number: int, filename: str):
        # Row count grows as tracks are announced — whipper doesn't tell us
        # the total track count in a single line we've found a clean way to
        # parse ahead of time, so the table just grows to fit as we go.
        if self.track_table.rowCount() < track_number:
            self.track_table.setRowCount(track_number)
        row = track_number - 1

        self.track_table.setItem(row, 0, QTableWidgetItem(str(track_number)))
        self.track_table.setItem(row, 1, QTableWidgetItem(filename))
        self.track_table.setItem(row, 2, QTableWidgetItem("Ripping…"))

    def _on_track_verified(self, track_number: int):
        row = track_number - 1
        if 0 <= row < self.track_table.rowCount():
            self.track_table.setItem(row, 2, QTableWidgetItem("Verified ✓"))

    def _build_progress_area(self) -> QWidget:
        wrapper = QWidget()
        vbox = QVBoxLayout(wrapper)
        vbox.setContentsMargins(0, 0, 0, 0)

        vbox.addWidget(QLabel("Overall progress:"))
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        vbox.addWidget(self.progress_bar)

        vbox.addWidget(QLabel("Current track:"))
        self.track_progress_bar = QProgressBar()
        self.track_progress_bar.setRange(0, 100)
        vbox.addWidget(self.track_progress_bar)

        self.status_label = QLabel("Idle")
        vbox.addWidget(self.status_label)

        return wrapper

    def _build_log_pane(self) -> QPlainTextEdit:
        self.log_pane = QPlainTextEdit()
        self.log_pane.setReadOnly(True)
        self.log_pane.setMaximumBlockCount(2000)
        self.log_pane.setFixedHeight(160)
        return self.log_pane

    def _build_action_bar(self) -> QHBoxLayout:
        row = QHBoxLayout()

        self.rip_btn = QPushButton("Rip Disc")
        self.rip_btn.clicked.connect(self._start_rip)
        row.addWidget(self.rip_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_rip)
        row.addWidget(self.cancel_btn)

        self.eject_btn = QPushButton("Eject")
        self.eject_btn.clicked.connect(self._eject_disc)
        row.addWidget(self.eject_btn)

        row.addStretch(1)
        return row

    def _eject_disc(self):
        device = self.drive_combo.currentData()
        if not device:
            QMessageBox.warning(self, "No drive selected", "Select a drive first.")
            return

        try:
            result = subprocess.run(
                ["eject", device], capture_output=True, text=True, timeout=10
            )
        except FileNotFoundError:
            QMessageBox.critical(
                self,
                "eject not found",
                "The 'eject' command isn't installed. It's normally part of "
                "util-linux and should already be on a Debian system — try "
                "'sudo apt install util-linux' if it's genuinely missing.",
            )
            return
        except subprocess.SubprocessError as e:
            QMessageBox.critical(self, "Eject failed", str(e))
            return

        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            QMessageBox.warning(
                self, "Eject failed", detail or f"eject exited with code {result.returncode}"
            )

    # ---- Drive handling ----------------------------------------------

    def _refresh_drives(self):
        self.drive_combo.clear()
        self._drives = list_drives()
        if not self._drives:
            self.drive_combo.addItem("No drives found")
            self.rip_btn.setEnabled(False)
            self.eject_btn.setEnabled(False)
            self.offset_label.setText("Offset: —")
            return

        self.rip_btn.setEnabled(True)
        self.eject_btn.setEnabled(True)
        for d in self._drives:
            self.drive_combo.addItem(d.label, userData=d.device)

        # Restore last-used device if still present
        idx = self.drive_combo.findData(self.settings.last_device)
        if idx >= 0:
            self.drive_combo.setCurrentIndex(idx)

        self._update_offset_label()

    def _current_drive_info(self) -> DriveInfo | None:
        idx = self.drive_combo.currentIndex()
        if 0 <= idx < len(self._drives):
            return self._drives[idx]
        return None

    def _update_offset_label(self):
        drive = self._current_drive_info()
        if not drive:
            self.offset_label.setText("Offset: —")
            return

        configured = find_offset_for_drive(drive.vendor, drive.model, drive.release)
        if configured and configured.read_offset is not None:
            self.offset_label.setText(f"Offset: {configured.read_offset:+d}")
            self.offset_label.setStyleSheet("color: green;")
        else:
            self.offset_label.setText("Offset: not set")
            self.offset_label.setStyleSheet("color: darkorange;")

    def _open_offset_dialog(self):
        drive = self._current_drive_info()
        if not drive:
            QMessageBox.warning(self, "No drive selected", "Select a drive first.")
            return

        dialog = OffsetDialog(drive.device, drive.vendor, drive.model, drive.release, parent=self)
        dialog.exec()
        self._update_offset_label()

    def _choose_output_dir(self):
        chosen = QFileDialog.getExistingDirectory(
            self, "Choose output folder", self.settings.output_dir
        )
        if chosen:
            self.settings.output_dir = chosen
            self.output_dir_label.setText(chosen)

    # ---- Ripping -------------------------------------------------------

    def _start_rip(self):
        device = self.drive_combo.currentData()
        if not device:
            QMessageBox.warning(self, "No drive selected", "Select a drive first.")
            return

        drive = self._current_drive_info()
        configured = (
            find_offset_for_drive(drive.vendor, drive.model, drive.release)
            if drive
            else None
        )
        if not configured or configured.read_offset is None:
            proceed = QMessageBox.warning(
                self,
                "Drive offset not set",
                "This drive has no confirmed read offset in whipper.conf yet. "
                "Ripping without a confirmed offset can shift audio by a few "
                "samples per track and will affect AccurateRip verification.\n\n"
                "Use the Offset… button first for an accurate rip. Continue anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if proceed != QMessageBox.StandardButton.Yes:
                return

        self.settings.last_device = device

        options = RipOptions(
            device=device,
            output_dir=self.settings.output_dir,
            eject=self.settings.eject_when_done,
            allow_unknown=self.settings.allow_unknown,
            track_template=self.settings.track_template,
            disc_template=self.settings.disc_template,
            cover_art=self.settings.cover_art or None,
            keep_going=self.settings.keep_going,
        )

        self.worker = RipWorker(options)
        self.worker.progress_changed.connect(self.progress_bar.setValue)
        self.worker.track_progress_changed.connect(self.track_progress_bar.setValue)
        self.worker.track_started.connect(self._on_track_started)
        self.worker.track_filename.connect(self._on_track_filename)
        self.worker.track_verified.connect(self._on_track_verified)
        self.worker.album_info.connect(self._on_album_info)
        self.worker.output_directory.connect(self._on_output_directory)
        self.worker.log_line.connect(self.log_pane.appendPlainText)
        self.worker.finished_ok.connect(self._on_finished)
        self.worker.failed.connect(self._on_failed)

        self.rip_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.eject_btn.setEnabled(False)
        self.status_label.setText("Ripping…")
        self.progress_bar.setValue(0)
        self.track_progress_bar.setValue(0)
        self.log_pane.clear()
        self.album_label.setText("")
        self.track_table.setRowCount(0)
        self._current_rip_output_dir: str | None = None

        self.worker.start()

    def _cancel_rip(self):
        if self.worker:
            self.worker.cancel()
        self.cancel_btn.setEnabled(False)

    def _on_track_started(self, track_number: int):
        self.status_label.setText(f"Ripping track {track_number}…")

    def _on_output_directory(self, path: str):
        self._current_rip_output_dir = path

    def _on_finished(self):
        self.status_label.setText("Done")
        self.rip_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.eject_btn.setEnabled(True)
        self._auto_verify_log()

    def _auto_verify_log(self):
        binary = find_logchecker(self.settings.logchecker_path)
        if not binary:
            # Not configured -- this is an opt-in convenience, not a
            # required step, so stay silent rather than nag on every rip.
            # (Tools -> Verify Log still warns clearly when used manually.)
            return

        log_path = self._find_latest_log_file()
        if not log_path:
            return

        result = verify_log(log_path, binary)
        dialog = LogVerifyDialog(result, log_path, parent=self)
        dialog.exec()

    def _find_latest_log_file(self) -> str | None:
        """Locates the .log file whipper just wrote for this rip.

        Prefers the exact output directory captured from whipper's own
        "creating output directory" line during this rip. Falls back to
        scanning the whole configured output tree for the most recently
        modified .log file, in case that line wasn't seen (e.g. re-ripping
        into a folder that already existed, so whipper never needed to
        create it).
        """
        search_root = self._current_rip_output_dir or self.settings.output_dir
        if not search_root or not os.path.isdir(search_root):
            return None

        candidates = glob.glob(
            os.path.join(glob.escape(search_root), "**", "*.log"), recursive=True
        )
        if not candidates:
            return None
        return max(candidates, key=os.path.getmtime)

    def _on_failed(self, message: str):
        self.status_label.setText("Failed")
        self.rip_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.eject_btn.setEnabled(True)

        summary, _, detail = message.partition("\n\n")
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle("Rip failed")
        box.setText(summary)
        if detail:
            box.setDetailedText(detail)
        box.exec()
