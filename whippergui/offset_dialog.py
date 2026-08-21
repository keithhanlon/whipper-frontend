"""Dialog for determining/confirming a drive's read offset."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
)

from whippergui.offset_utils import find_offset_for_drive
from whippergui.offset_worker import OffsetWorker

ACCURATERIP_OFFSET_DB_URL = "http://www.accuraterip.com/driveoffsets.htm"


class OffsetDialog(QDialog):
    """Walks the user through `whipper drive analyze` + `whipper offset find`."""

    def __init__(self, device: str, vendor: str, model: str, release: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Determine Drive Offset")
        self.resize(520, 420)

        self._device = device
        self._vendor = vendor
        self._release = release
        self._model = model
        self._worker: OffsetWorker | None = None
        self.confirmed_offset: int | None = None

        self._build_ui()
        self._show_existing_offset()

    # ---- UI ----------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)

        intro = QLabel(
            "Insert a well-known, popular CD (one likely to be in the "
            "AccurateRip database) before starting. This rips test tracks "
            "to confirm the drive's read offset — it does not save any "
            "audio files.\n\n"
            f"If you already know your drive's offset from AccurateRip's "
            f"own database ({ACCURATERIP_OFFSET_DB_URL}), enter it below "
            "to confirm it directly instead of searching."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.existing_label = QLabel()
        self.existing_label.setStyleSheet("color: gray;")
        self.existing_label.setWordWrap(True)
        layout.addWidget(self.existing_label)

        self.known_radio = QRadioButton("I know the offset — confirm this value:")
        self.known_radio.setChecked(True)
        layout.addWidget(self.known_radio)

        offset_row = QHBoxLayout()
        offset_row.addSpacing(20)
        self.offset_spin = QSpinBox()
        self.offset_spin.setRange(-2000, 2000)
        self.offset_spin.setValue(0)
        offset_row.addWidget(self.offset_spin)
        offset_row.addStretch(1)
        layout.addLayout(offset_row)

        self.search_radio = QRadioButton(
            "Search for it automatically (no known value — can be slow, "
            "may rip many times)"
        )
        layout.addWidget(self.search_radio)

        self.status_label = QLabel("Idle")
        layout.addWidget(self.status_label)

        self.log_pane = QPlainTextEdit()
        self.log_pane.setReadOnly(True)
        self.log_pane.setMaximumBlockCount(2000)
        layout.addWidget(self.log_pane, stretch=1)

        action_row = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.clicked.connect(self._start)
        action_row.addWidget(self.start_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel)
        action_row.addWidget(self.cancel_btn)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def _show_existing_offset(self):
        existing = find_offset_for_drive(self._vendor, self._model, self._release)
        if existing and existing.read_offset is not None:
            self.existing_label.setText(
                f"Currently configured for this drive: offset "
                f"{existing.read_offset:+d} (from whipper.conf)."
            )
            self.offset_spin.setValue(existing.read_offset)
        else:
            self.existing_label.setText(
                "No offset currently configured for this drive in whipper.conf."
            )

    # ---- Actions -------------------------------------------------------

    def _start(self):
        known_offset = self.offset_spin.value() if self.known_radio.isChecked() else None

        self._worker = OffsetWorker(self._device, known_offset=known_offset)
        self._worker.log_line.connect(self.log_pane.appendPlainText)
        self._worker.stage_changed.connect(self._on_stage_changed)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)

        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.known_radio.setEnabled(False)
        self.search_radio.setEnabled(False)
        self.offset_spin.setEnabled(False)
        self.log_pane.clear()
        self.status_label.setText("Starting…")

        self._worker.start()

    def _cancel(self):
        if self._worker:
            self._worker.cancel()
        self.cancel_btn.setEnabled(False)

    def _on_stage_changed(self, stage: str):
        text = {
            "analyzing": "Checking drive cache behavior (whipper drive analyze)…",
            "finding": "Determining read offset (whipper offset find)… this can take a while.",
        }.get(stage, stage)
        self.status_label.setText(text)

    def _on_finished(self, offset: int):
        self.confirmed_offset = offset
        self.status_label.setText(
            f"Confirmed offset: {offset:+d} (written to whipper.conf by whipper)."
        )
        self._reset_controls()

    def _on_failed(self, message: str):
        self.status_label.setText("Failed")
        self.log_pane.appendPlainText(f"\n--- {message} ---")
        self._reset_controls()

    def _reset_controls(self):
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.known_radio.setEnabled(True)
        self.search_radio.setEnabled(True)
        self.offset_spin.setEnabled(True)
