"""Dialog for editing the track/disc file naming templates whipper uses."""
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from whippergui.whipper_config import (
    DEFAULT_DISC_TEMPLATE,
    DEFAULT_TRACK_TEMPLATE,
    SHARED_PLACEHOLDERS,
    TRACK_ONLY_PLACEHOLDERS,
    validate_disc_template,
    validate_track_template,
)


def _placeholder_legend_text() -> str:
    lines = ["Track-only:"]
    for var, desc in TRACK_ONLY_PLACEHOLDERS.items():
        lines.append(f"  {var}  {desc}")
    lines.append("")
    lines.append("Track + disc:")
    for var, desc in SHARED_PLACEHOLDERS.items():
        lines.append(f"  {var}  {desc}")
    return "\n".join(lines)


class TemplatesDialog(QDialog):
    """Edits whipper's --track-template / --disc-template values.

    These aren't stored in whipper.conf (whipper has no config-file
    equivalent for them — they're CLI-args-only), so they're persisted in
    this app's own QSettings and passed at rip time instead.
    """

    def __init__(self, current_track_template: str, current_disc_template: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("File & Folder Naming")
        self.resize(560, 420)

        self.track_template: str | None = None
        self.disc_template: str | None = None

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Controls how whipper names ripped files and folders, using "
            "whipper's own template variables (verbatim from its --help)."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()

        self.track_edit = QLineEdit(current_track_template)
        self.track_edit.textChanged.connect(self._validate)
        form.addRow("Track filename template:", self.track_edit)

        self.disc_edit = QLineEdit(current_disc_template)
        self.disc_edit.textChanged.connect(self._validate)
        form.addRow("Disc (.cue/.log) template:", self.disc_edit)

        layout.addLayout(form)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #c0392b;")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        reset_btn = QPushButton("Reset to whipper's defaults")
        reset_btn.clicked.connect(self._reset_defaults)
        layout.addWidget(reset_btn)

        legend = QLabel(_placeholder_legend_text())
        legend.setStyleSheet("color: gray; font-family: monospace;")
        layout.addWidget(legend, stretch=1)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self._on_accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self._validate()

    def _reset_defaults(self):
        self.track_edit.setText(DEFAULT_TRACK_TEMPLATE)
        self.disc_edit.setText(DEFAULT_DISC_TEMPLATE)

    def _validate(self):
        track_err = validate_track_template(self.track_edit.text())
        disc_err = validate_disc_template(self.disc_edit.text())
        err = track_err or disc_err
        self.error_label.setText(err or "")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(err is None)

    def _on_accept(self):
        self.track_template = self.track_edit.text()
        self.disc_template = self.disc_edit.text()
        self.accept()
