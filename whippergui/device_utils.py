"""Detect optical drives available to whipper."""
import re
import subprocess
from dataclasses import dataclass

# Matches whipper's actual `whipper drive list` output, e.g.:
#   drive: /dev/sr0, vendor: HL-DT-ST, model: DVDRAM GP65NW60 , release: PF00
# (see whipper/command/drive.py — List.do())
_DRIVE_LINE_RE = re.compile(
    r"drive:\s*(/dev/\S+),\s*vendor:\s*(.*?),\s*model:\s*(.*?),\s*release:\s*(.*?)\s*$"
)


@dataclass
class DriveInfo:
    device: str        # e.g. /dev/sr0
    vendor: str
    model: str
    release: str = ""

    @property
    def label(self) -> str:
        return f"{self.device} — {self.vendor} {self.model}".strip()


def list_drives() -> list[DriveInfo]:
    """Parse `whipper drive list` output into DriveInfo objects.

    Requires pycdio to be installed for whipper to report vendor/model/
    release at all — without it, whipper prints only an error and no
    drive lines, so we fall back to a raw /dev/sr* scan (device path
    only, no vendor/model — offset-file matching won't work in that
    case since it relies on vendor/model, not just the device path).
    """
    drives: list[DriveInfo] = []
    try:
        result = subprocess.run(
            ["whipper", "drive", "list"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        for line in result.stdout.splitlines():
            m = _DRIVE_LINE_RE.search(line)
            if m:
                device, vendor, model, release = m.groups()
                drives.append(
                    DriveInfo(
                        device=device,
                        vendor=vendor.strip(),
                        model=model.strip(),
                        release=release.strip(),
                    )
                )
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    if not drives:
        drives = _scan_dev_fallback()

    return drives


def _scan_dev_fallback() -> list[DriveInfo]:
    import glob

    return [
        DriveInfo(device=dev, vendor="Unknown", model="")
        for dev in sorted(glob.glob("/dev/sr*"))
    ]
