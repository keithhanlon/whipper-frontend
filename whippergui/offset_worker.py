"""Background worker for drive-offset detection.

Runs `whipper drive analyze` (records cache-defeat capability) followed by
`whipper offset find` (confirms or searches for the drive's read offset by
ripping a disc that's in the AccurateRip database). Both are long-running,
disc-reading subprocesses, so — same as ripping itself — this must never
run on the GUI thread.
"""
import os
import re
import subprocess

from PySide6.QtCore import QThread, Signal

# These match whipper's actual printed/logged strings verbatim (see
# whipper/command/offset.py). In particular, _OFFSET_FOUND_RE must only
# match the final confirmation print — NOT the "trying read offset N..."
# line logged for every candidate offset — because in auto-search mode
# whipper tries many offsets in sequence before (maybe) confirming one;
# matching the first "read offset" mention in the output would report
# the first *attempted* offset rather than the one actually confirmed.
_OFFSET_FOUND_RE = re.compile(r"Read offset of device is:\s*(-?\d+)")
_NO_OFFSET_RE = re.compile(
    r"no matching offset found|AccurateRip entry not found|"
    r"needs a CD with at least 3 tracks"
)


class OffsetWorker(QThread):
    log_line = Signal(str)
    stage_changed = Signal(str)        # "analyzing" / "finding"
    finished_ok = Signal(int)          # confirmed/found offset
    failed = Signal(str)

    def __init__(self, device: str, known_offset: int | None = None, parent=None):
        super().__init__(parent)
        self._device = device
        self._known_offset = known_offset
        self._process: subprocess.Popen | None = None
        self._cancelled = False

    def cancel(self):
        self._cancelled = True
        if self._process and self._process.poll() is None:
            self._process.terminate()

    def run(self):
        self.stage_changed.emit("analyzing")
        if not self._run_step(["whipper", "drive", "analyze", "-d", self._device]):
            return
        if self._cancelled:
            self.failed.emit("Cancelled")
            return

        self.stage_changed.emit("finding")
        find_cmd = ["whipper", "offset", "find", "-d", self._device]
        if self._known_offset is not None:
            # whipper's -o/--offsets flag is actually a candidate LIST
            # (comma/colon-separated), defaulting to whipper's full known-
            # offsets list when omitted. Passing a single value restricts
            # the search to just that one candidate, which is functionally
            # a "confirm this value" mode even though it isn't a dedicated
            # flag for that in whipper itself.
            find_cmd += ["-o", str(self._known_offset)]

        output_lines: list[str] = []
        if not self._run_step(find_cmd, collect_into=output_lines):
            return
        if self._cancelled:
            self.failed.emit("Cancelled")
            return

        full_output = "\n".join(output_lines)
        match = _OFFSET_FOUND_RE.search(full_output)
        if match:
            self.finished_ok.emit(int(match.group(1)))
        elif _NO_OFFSET_RE.search(full_output):
            self.failed.emit(
                "No offset could be confirmed on this disc. Try a more popular "
                "CD, or enter the offset manually if you know it from "
                "AccurateRip's drive offset database."
            )
        else:
            self.failed.emit(
                "offset find finished but no offset value could be parsed from "
                "its output — check the log below."
            )

    def _run_step(self, cmd: list[str], collect_into: list[str] | None = None) -> bool:
        """Run one subprocess step, streaming lines. Returns False on failure."""
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                # Same fix as rip_worker.py: force whipper's own Python to
                # run unbuffered, since some of its output uses plain
                # print() which Python silently block-buffers whenever
                # stdout isn't a real terminal (i.e. whenever it's piped,
                # as it always is here).
                env=dict(os.environ, PYTHONUNBUFFERED="1"),
            )
        except FileNotFoundError:
            self.failed.emit("whipper executable not found on PATH")
            return False

        assert self._process.stdout is not None
        for raw_line in self._process.stdout:
            line = raw_line.rstrip("\n")
            self.log_line.emit(line)
            if collect_into is not None:
                collect_into.append(line)

        return_code = self._process.wait()
        if self._cancelled:
            return False
        if return_code != 0:
            self.failed.emit(f"'{' '.join(cmd)}' exited with code {return_code}")
            return False
        return True
