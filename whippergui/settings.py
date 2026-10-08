"""Persisted user settings via QSettings."""
import os

from PySide6.QtCore import QSettings

from whippergui.whipper_config import DEFAULT_DISC_TEMPLATE, DEFAULT_TRACK_TEMPLATE


class Settings:
    def __init__(self):
        # "whipper-gui" is a deliberately stable storage key (the app's
        # display name is "Whipper Frontend" as of the rename) — changing
        # this string would make QSettings look in a different location on
        # disk and silently lose every existing user's saved preferences.
        self._qs = QSettings("citizenkeith", "whipper-gui")

    @property
    def output_dir(self) -> str:
        return self._qs.value("output_dir", os.path.expanduser("~/Music/Ripped"))

    @output_dir.setter
    def output_dir(self, value: str):
        self._qs.setValue("output_dir", value)

    @property
    def last_device(self) -> str:
        return self._qs.value("last_device", "")

    @last_device.setter
    def last_device(self, value: str):
        self._qs.setValue("last_device", value)

    @property
    def track_template(self) -> str:
        return self._qs.value("track_template", DEFAULT_TRACK_TEMPLATE)

    @track_template.setter
    def track_template(self, value: str):
        self._qs.setValue("track_template", value)

    @property
    def disc_template(self) -> str:
        return self._qs.value("disc_template", DEFAULT_DISC_TEMPLATE)

    @disc_template.setter
    def disc_template(self, value: str):
        self._qs.setValue("disc_template", value)

    @property
    def allow_unknown(self) -> bool:
        # QSettings stores bools as strings on some platforms; normalize.
        value = self._qs.value("allow_unknown", True)
        return value if isinstance(value, bool) else str(value).lower() == "true"

    @allow_unknown.setter
    def allow_unknown(self, value: bool):
        self._qs.setValue("allow_unknown", value)

    @property
    def cover_art(self) -> str:
        # "", "file", "embed", or "complete" — "" means don't fetch cover art
        return self._qs.value("cover_art", "")

    @cover_art.setter
    def cover_art(self, value: str):
        self._qs.setValue("cover_art", value)

    @property
    def keep_going(self) -> bool:
        value = self._qs.value("keep_going", False)
        return value if isinstance(value, bool) else str(value).lower() == "true"

    @keep_going.setter
    def keep_going(self, value: bool):
        self._qs.setValue("keep_going", value)

    @property
    def max_retries(self) -> int:
        # Matches whipper's own default (5); 0 means retry forever.
        return int(self._qs.value("max_retries", 5))

    @max_retries.setter
    def max_retries(self, value: int):
        self._qs.setValue("max_retries", value)

    @property
    def eject_when_done(self) -> bool:
        value = self._qs.value("eject_when_done", False)
        return value if isinstance(value, bool) else str(value).lower() == "true"

    @eject_when_done.setter
    def eject_when_done(self, value: bool):
        self._qs.setValue("eject_when_done", value)

    @property
    def logchecker_path(self) -> str:
        # Empty means "look for 'logchecker' on PATH"
        return self._qs.value("logchecker_path", "")

    @logchecker_path.setter
    def logchecker_path(self, value: str):
        self._qs.setValue("logchecker_path", value)
