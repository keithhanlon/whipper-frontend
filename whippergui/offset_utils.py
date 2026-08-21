"""Read whipper's own config file to surface configured drive offsets.

Whipper writes a section per drive it has seen, keyed by
`drive:VENDOR:MODEL:RELEASE`, e.g.:

    [drive:TSSTcorp:CDDVDW SE-T084M :TD01]
    vendor = TSSTcorp
    model = CDDVDW SE-T084M
    release = TD01
    defeats_cache = True
    read_offset = 6

We only ever read this file — writing to it is left entirely to whipper
itself (`whipper drive analyze` / `whipper offset find`), so there's no
risk of the GUI corrupting a config whipper depends on.
"""
import configparser
import os
from dataclasses import dataclass

from whippergui.whipper_config import CONFIG_PATH


def config_path() -> str:
    return CONFIG_PATH


@dataclass
class ConfiguredDrive:
    section: str
    vendor: str
    model: str
    release: str
    defeats_cache: bool | None
    read_offset: int | None

    @property
    def label(self) -> str:
        offset = "not set" if self.read_offset is None else f"{self.read_offset:+d}"
        return f"{self.vendor} {self.model} ({self.release}) — offset {offset}"


def list_configured_drives() -> list[ConfiguredDrive]:
    path = config_path()
    if not os.path.exists(path):
        return []

    parser = configparser.ConfigParser()
    parser.read(path)

    drives = []
    for section in parser.sections():
        if not section.startswith("drive:"):
            continue
        get = lambda key, default="": parser.get(section, key, fallback=default)
        offset_raw = parser.get(section, "read_offset", fallback=None)
        cache_raw = parser.get(section, "defeats_cache", fallback=None)
        drives.append(
            ConfiguredDrive(
                section=section,
                vendor=get("vendor"),
                model=get("model"),
                release=get("release"),
                defeats_cache=(cache_raw.lower() == "true") if cache_raw else None,
                read_offset=int(offset_raw) if offset_raw not in (None, "") else None,
            )
        )
    return drives


def find_offset_for_drive(
    vendor: str, model: str, release: str = ""
) -> ConfiguredDrive | None:
    """Match against a DriveInfo's vendor/model(/release) strings.

    whipper's own vendor/model/release strings (from pycdio) are the
    source of truth for the section name, so an exact match on all three
    is preferred when we have a release value; falls back to a looser
    vendor/model substring match otherwise (e.g. the /dev/sr* scan
    fallback in device_utils, which never has a release).
    """
    vendor_l, model_l, release_l = (
        vendor.lower().strip(),
        model.lower().strip(),
        release.lower().strip(),
    )
    configured = list_configured_drives()

    if release_l:
        for drive in configured:
            if (
                drive.vendor.lower() == vendor_l
                and drive.model.lower() == model_l
                and drive.release.lower() == release_l
            ):
                return drive

    for drive in configured:
        if vendor_l and vendor_l in drive.vendor.lower():
            if not model_l or model_l in drive.model.lower():
                return drive
    return None
