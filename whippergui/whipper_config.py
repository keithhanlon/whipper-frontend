"""Read and write settings in whipper's own [main] config section.

Unlike offset_utils.py (read-only, since whipper itself owns writing drive
offsets), this module DOES write to whipper.conf — but only ever to keys
under [main] that this GUI itself introduces a UI for. It always reads the
full file first and writes the full file back via configparser, so any
other section (in particular every [drive:...] section whipper manages) is
preserved untouched.
"""
import configparser
import os
import re

CONFIG_PATH = os.path.join(
    os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
    "whipper",
    "whipper.conf",
)

# Matches whipper's own PathFilter option names (whipper/common/path.py),
# stored as path_filter_<name> under [main].
_VFAT_KEY = "path_filter_vfat"

# whipper's own defaults and validation rule, verified against
# whipper/command/cd.py and whipper/common/common.py (validate_template).
# These are GUI-only settings (there's no [main] config key for them in
# whipper itself) — we pass them as -- track-template/--disc-template CLI
# args at rip time instead, via Settings.track_template/disc_template.
DEFAULT_TRACK_TEMPLATE = "%r/%A - %d/%t. %a - %n"
DEFAULT_DISC_TEMPLATE = "%r/%A - %d/%A - %d"

_TRACK_TEMPLATE_INVALID_RE = re.compile(r"%[^ABCDIMNRSTXacdnrstxy]")
_DISC_TEMPLATE_INVALID_RE = re.compile(r"%[^ABCDIMNRSTXcdrxy]")

# Placeholder legend, verbatim from whipper's own TEMPLATE_DESCRIPTION
# (whipper/command/cd.py), for display in the GUI.
TRACK_ONLY_PLACEHOLDERS = {
    "%t": "track number",
    "%a": "track artist",
    "%n": "track title",
    "%s": "track sort name",
}
SHARED_PLACEHOLDERS = {
    "%A": "release artist",
    "%S": "release sort name",
    "%B": "release barcode",
    "%C": "release catalog number",
    "%c": "release disambiguation comment",
    "%d": "release title (with disambiguation)",
    "%D": "disc title (without disambiguation)",
    "%I": "MusicBrainz Disc ID",
    "%M": "total number of discs in the chosen release",
    "%N": "number of current disc",
    "%T": "medium title",
    "%y": "release year",
    "%r": "release type, lowercase",
    "%R": "release type, normal case",
    "%x": "audio extension, lowercase",
    "%X": "audio extension, uppercase",
}


def validate_track_template(template: str) -> str | None:
    """Mirrors whipper's own validate_template() for kind='track'.

    Returns None if valid, or an error message naming the bad variable(s).
    """
    if "%" in template:
        matches = _TRACK_TEMPLATE_INVALID_RE.findall(template)
        if matches:
            return "Invalid track template variable(s): " + ", ".join(matches)
    return None


def validate_disc_template(template: str) -> str | None:
    """Mirrors whipper's own validate_template() for kind='disc'."""
    if "%" in template:
        matches = _DISC_TEMPLATE_INVALID_RE.findall(template)
        if matches:
            return "Invalid disc template variable(s): " + ", ".join(matches)
    return None


def _read_parser() -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    if os.path.exists(CONFIG_PATH):
        parser.read(CONFIG_PATH)
    return parser


def get_path_filter_vfat() -> bool:
    """Whether whipper is configured to replace VFAT/exFAT-illegal chars

    (" * / : < > ? \\ |) with underscores in generated filenames.
    Defaults to False, matching whipper's own default.
    """
    parser = _read_parser()
    if not parser.has_section("main"):
        return False
    return parser.getboolean("main", _VFAT_KEY, fallback=False)


def set_path_filter_vfat(enabled: bool) -> None:
    """Enable/disable whipper's VFAT-safe filename filtering.

    Reads the full existing config (if any), sets only this one key under
    [main], and writes the full config back — every other section and key
    whipper has written (drive offsets, cache-defeat flags, etc.) is
    preserved exactly as-is.
    """
    parser = _read_parser()
    if not parser.has_section("main"):
        parser.add_section("main")
    parser.set("main", _VFAT_KEY, "True" if enabled else "False")

    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        parser.write(f)
