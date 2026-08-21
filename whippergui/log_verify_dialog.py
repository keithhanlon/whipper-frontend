"""Dialog showing the result of running OPSnet's logchecker on a .log file."""
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from whippergui.log_verify import LogVerifyResult

_OPSNET_URL = "https://github.com/OPSnet/Logchecker"


class LogVerifyDialog(QDialog):
    def __init__(self, result: LogVerifyResult, log_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Log Verification")
        self.resize(480, 380)

        layout = QVBoxLayout(self)

        path_label = QLabel(log_path)
        path_label.setStyleSheet("color: gray;")
        path_label.setWordWrap(True)
        layout.addWidget(path_label)

        if result.error:
            error_label = QLabel(result.error)
            error_label.setWordWrap(True)
            error_label.setStyleSheet("color: #c0392b;")
            layout.addWidget(error_label)
        else:
            score_label = QLabel(self._score_text(result))
            score_label.setStyleSheet(f"font-size: 20pt; font-weight: bold; color: {self._score_color(result.score)};")
            layout.addWidget(score_label)

            summary = QLabel(
                f"Ripper: {result.ripper or 'unknown'}"
                + (f" {result.version}" if result.version else "")
                + f"    Checksum: {result.checksum or 'unknown'}"
            )
            summary.setStyleSheet("color: gray;")
            layout.addWidget(summary)

            # logchecker only ever reports what deducted points — it doesn't
            # return a checklist of every possible check with a pass/fail
            # for each. So every listed item here IS a problem (colored
            # red); a clean log just has an empty list, shown in green as
            # the honest equivalent of "everything passed" rather than
            # inventing a "passed" list the tool never actually returned.
            if result.details:
                layout.addWidget(QLabel("Issues found:"))
                details_list = QListWidget()
                for detail in result.details:
                    item = QListWidgetItem(detail)
                    item.setForeground(QColor("#c0392b"))
                    details_list.addItem(item)
                layout.addWidget(details_list, stretch=1)
            else:
                passed_label = QLabel("No issues found.")
                passed_label.setStyleSheet("color: #2ecc71; font-weight: bold;")
                layout.addWidget(passed_label)

        credit = QLabel(f'Powered by <a href="{_OPSNET_URL}">OPSnet Logchecker</a>')
        credit.setStyleSheet("color: gray;")
        credit.setOpenExternalLinks(True)
        layout.addWidget(credit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.accept)
        layout.addWidget(buttons)

    @staticmethod
    def _score_text(result: LogVerifyResult) -> str:
        if result.score is None:
            return "Score: unknown"
        return f"Score: {result.score} / 100"

    @staticmethod
    def _score_color(score: int | None) -> str:
        if score is None:
            return "gray"
        if score >= 90:
            return "#2ecc71"
        if score >= 70:
            return "#e67e22"
        return "#c0392b"
