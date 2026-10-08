"""Background worker that runs `whipper cd rip` without blocking the GUI."""
import os
import re
import subprocess
from dataclasses import dataclass, field

from PySide6.QtCore import QThread, Signal

# Whipper's rip output goes through three phases:
#   1. Initial TOC read:      "Reading table  NN %"
#   2. Per-track ripping — see _RipProgressTracker's docstring below for
#      why this only tracks Reading/Verifying/CRC-match, not all 9 of
#      whipper's internal sub-stages.
#   3. Final AccurateRip check across all tracks:
#                              "Getting length of audio track (F of N) ...  NN %"
#
# Phase 2 (actual disc reading) dominates real elapsed time by far, so it
# gets the large majority of the weight below.
_TOC_READ_RE = re.compile(r"Reading table\s+(\d{1,3})\s*%")

# Discriminate Reading vs Verifying by their literal text (not by numeric
# stage index) — the index is more fragile than it looks, since it can
# shift depending on settings (e.g. whether cover art fetching is on)
# changing the total stage count.
_READING_RE = re.compile(r"[Rr]eading track \d+ of \d+.*?\.\.\.\s*(\d{1,3})\s*%")
_VERIFYING_RE = re.compile(r"[Vv]erifying track \d+ of \d+.*?\.\.\.\s*(\d{1,3})\s*%")

_FINAL_CHECK_RE = re.compile(
    r"Getting length of audio track\s*\((\d+)\s+of\s+(\d+)\)\s*\.\.\.\s*(\d{1,3})\s*%"
)
# Anchored to whipper's one-time-per-track announcement line, e.g.:
#   "INFO:whipper.command.cd:ripping track 1 of 9: 01. Artist - Title.flac"
# — deliberately NOT matching on any "track" substring, since the final
# AccurateRip summary ("track  1: rip accurate ...") also contains the word
# "track" and would otherwise falsely re-trigger track_started after the
# rip has already finished. Also captures the filename, so the GUI can show
# what whipper itself named each track without a separate metadata lookup.
_TRACK_START_INFO_RE = re.compile(r"ripping track (\d+) of (\d+):\s*(.+?)\s*$")

# From the "Matching releases:" block whipper prints once it identifies the
# disc on MusicBrainz — verified verbatim against a real completed rip:
#     Artist  : Yes
#     Title   : Classic Yes
_ALBUM_ARTIST_RE = re.compile(r"^Artist\s*:\s*(.+?)\s*$")
_ALBUM_TITLE_RE = re.compile(r"^Title\s*:\s*(.+?)\s*$")

# Verified verbatim: "INFO:whipper.command.cd:CRCs match for track N"
_CRC_MATCH_RE = re.compile(r"CRCs match for track (\d+)")

# Verified verbatim against whipper/program/cdrdao.py:
#   logger.info("creating output directory %s", t_dirn)
_OUTPUT_DIR_RE = re.compile(r"creating output directory (.+?)\s*$")

_TOC_WEIGHT = 3
_RIP_WEIGHT = 92
_CHECK_WEIGHT = 5


class _RipProgressTracker:
    """Converts whipper's per-substage percentages into overall + per-track values.

    Deliberately does NOT try to track all 9 of whipper's internal
    sub-stages individually (Reading, CRC-check, Verifying, CRC-check,
    Encoding, CRC-check, Peak-level, Tag-writing, Cover-art) — an earlier
    version of this attempted exactly that, using a generic "(stage_idx of
    stage_total) ... pct%" pattern shared by all 9. It turned out
    unreliable in real use: several of those stages complete fast enough
    that whipper's own task-runner doesn't always emit a progress callback
    for them at all, so relying on catching each individual transition
    left the bar plateauing unpredictably.

    Instead, this only relies on THREE anchors that have proven to appear
    reliably every time: Reading's own percentage (0-50% of a track),
    Verifying's own percentage (50-90%), and the "CRCs match for track N"
    line, which snaps straight to 100% — collapsing the 6 fast trailing
    stages (encode/tag/cover-art/etc.) into a single reliable jump instead
    of trying to visualize each one individually.
    """

    def __init__(self):
        self.total_tracks: int | None = None

    def compute(self, line: str, current_track: int | None) -> tuple[int | None, int | None]:
        """Returns (overall_pct, track_pct) — either may be None if this line
        doesn't carry that kind of progress info. track_pct only applies
        during phase 2 (actual track reading/verifying); it's None during
        the initial TOC read and the final AccurateRip check phases, since
        "current track progress" doesn't mean anything in those phases.

        current_track is the track number RipWorker is currently tracking
        (from the last "ripping track N of M:" line) — needed here since
        none of these per-line patterns carry a track number themselves.
        self.total_tracks is set by RipWorker directly from that same line.
        """
        stage_fraction: float | None = None

        m = _READING_RE.search(line)
        if m:
            stage_fraction = 0.5 * (int(m.group(1)) / 100)

        m = _VERIFYING_RE.search(line)
        if m:
            stage_fraction = 0.5 + 0.4 * (int(m.group(1)) / 100)

        if _CRC_MATCH_RE.search(line):
            stage_fraction = 1.0

        if stage_fraction is not None and current_track is not None and self.total_tracks:
            track_fraction = (
                (current_track - 1) + stage_fraction
            ) / self.total_tracks
            overall = self._clamp(_TOC_WEIGHT + _RIP_WEIGHT * track_fraction)
            track_only = self._clamp(stage_fraction * 100)
            return overall, track_only

        m = _FINAL_CHECK_RE.search(line)
        if m:
            idx, total, pct = (int(g) for g in m.groups())
            if total <= 0:
                return None, None
            fraction = ((idx - 1) + pct / 100) / total
            overall = self._clamp(_TOC_WEIGHT + _RIP_WEIGHT + _CHECK_WEIGHT * fraction)
            return overall, None

        m = _TOC_READ_RE.search(line)
        if m:
            pct = int(m.group(1))
            overall = self._clamp(_TOC_WEIGHT * (pct / 100))
            return overall, None

        return None, None

    @staticmethod
    def _clamp(value: float) -> int:
        return max(0, min(100, round(value)))


@dataclass
class RipOptions:
    device: str
    output_dir: str
    offset: int | None = None            # drive read offset; omit to use whipper's configured default
    eject: bool = False                  # whether to eject the disc after a successful rip
    allow_unknown: bool = False          # -U: rip anyway if metadata lookup fails
    track_template: str | None = None    # None = use whipper's own default
    disc_template: str | None = None     # None = use whipper's own default
    cover_art: str | None = None         # None, "file", "embed", or "complete"
    keep_going: bool = False             # -k: don't abort the disc if one track fails
    max_retries: int | None = None       # -r: None = use whipper's own default (5); 0 = infinite
    extra_args: list[str] = field(default_factory=list)

    def to_cli_args(self) -> list[str]:
        """Build args for `whipper ...` (not including the 'whipper' binary itself).

        Correct shape, per whipper's actual argparse structure:
            whipper [-e EJECT_MODE] cd -d DEVICE rip [-o OFFSET] -O OUTPUT_DIR
                    [-U] [--track-template T] [--disc-template T]
                    [-C {file,embed,complete}] [-k]

        -e/--eject is a TOP-LEVEL flag (before 'cd'), not part of 'rip'.
        -d/--device belongs to 'cd', not to 'rip'.
        There is no -f/--format flag anywhere — whipper always rips to FLAC.
        """
        args = ["-e", "success" if self.eject else "never"]
        args += ["cd", "-d", self.device, "rip"]
        if self.offset is not None:
            args += ["-o", str(self.offset)]
        args += ["-O", self.output_dir]
        if self.allow_unknown:
            args += ["-U"]
        if self.track_template:
            args += ["--track-template", self.track_template]
        if self.disc_template:
            args += ["--disc-template", self.disc_template]
        if self.cover_art:
            args += ["-C", self.cover_art]
        if self.keep_going:
            args += ["-k"]
        if self.max_retries is not None:
            args += ["-r", str(self.max_retries)]
        args += self.extra_args
        return args


class RipWorker(QThread):
    progress_changed = Signal(int)         # 0-100, overall disc progress
    track_progress_changed = Signal(int)   # 0-100, current track only
    track_started = Signal(int)            # track number
    track_filename = Signal(int, str)      # track number, filename whipper is writing
    track_verified = Signal(int)           # track number whose CRC matched (AccurateRip)
    album_info = Signal(str, str)          # album artist, album title
    output_directory = Signal(str)         # directory whipper is writing tracks/log into
    log_line = Signal(str)                 # raw output line, for a log pane
    finished_ok = Signal()
    failed = Signal(str)                   # error message

    def __init__(self, options: RipOptions, parent=None):
        super().__init__(parent)
        self._options = options
        self._process: subprocess.Popen | None = None
        self._cancelled = False
        self._progress = _RipProgressTracker()
        self._current_track: int | None = None
        self._pending_album_artist: str | None = None
        self._pending_album_title: str | None = None
        self._album_emitted = False

    def cancel(self):
        """Request cancellation; terminates the subprocess if running."""
        self._cancelled = True
        if self._process and self._process.poll() is None:
            self._process.terminate()

    def run(self):
        cmd = ["whipper", *self._options.to_cli_args()]
        # Force whipper's own Python interpreter to run unbuffered. Some of
        # its output (album/disc metadata) uses plain print(), which Python
        # silently switches to full block buffering — instead of immediate
        # line buffering — whenever stdout isn't a real terminal, which is
        # exactly our situation since we pipe it. Without this, those
        # specific lines can sit invisible in whipper's internal buffer for
        # a long time, while logger-based output (which always goes to
        # stderr, never block-buffered) still comes through immediately —
        # which is exactly the split symptom this was causing.
        env = dict(os.environ, PYTHONUNBUFFERED="1")
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
            )
        except FileNotFoundError:
            self.failed.emit("whipper executable not found on PATH")
            return

        assert self._process.stdout is not None
        recent_lines: list[str] = []
        for raw_line in self._process.stdout:
            line = raw_line.rstrip("\n")
            self.log_line.emit(line)
            self._parse_line(line)
            recent_lines.append(line)
            if len(recent_lines) > 15:
                recent_lines.pop(0)

        return_code = self._process.wait()

        if self._cancelled:
            self.failed.emit("Rip cancelled")
        elif return_code != 0:
            # Show whatever whipper actually said just before it exited,
            # not just the exit code — e.g. an unhandled Python traceback
            # (network errors fetching cover art, etc.) — so the real
            # cause is visible without having to scroll the log manually.
            tail = "\n".join(line for line in recent_lines if line.strip())
            detail = f"\n\n{tail}" if tail else ""
            self.failed.emit(f"whipper exited with code {return_code}{detail}")
        else:
            self.progress_changed.emit(100)
            self.track_progress_changed.emit(100)
            self.finished_ok.emit()

    def _parse_line(self, line: str):
        output_dir_match = _OUTPUT_DIR_RE.search(line)
        if output_dir_match:
            self.output_directory.emit(output_dir_match.group(1))

        album_artist_match = _ALBUM_ARTIST_RE.match(line)
        if album_artist_match:
            self._pending_album_artist = album_artist_match.group(1)
        album_title_match = _ALBUM_TITLE_RE.match(line)
        if album_title_match:
            self._pending_album_title = album_title_match.group(1)
        if self._pending_album_artist and self._pending_album_title and not self._album_emitted:
            self.album_info.emit(self._pending_album_artist, self._pending_album_title)
            self._album_emitted = True

        crc_match = _CRC_MATCH_RE.search(line)
        if crc_match:
            self.track_verified.emit(int(crc_match.group(1)))

        start_match = _TRACK_START_INFO_RE.search(line)
        if start_match:
            # A CRC mismatch (rather than a normal "CRCs match" line) would
            # mean this track never got the 1.0 stage_fraction snap from
            # _CRC_MATCH_RE — belt-and-suspenders snap to 100 here too,
            # since a new track only ever starts once the previous one's
            # full pipeline (including any retries) has actually finished.
            if self._current_track is not None:
                self.track_progress_changed.emit(100)

            self._current_track = int(start_match.group(1))
            self._progress.total_tracks = int(start_match.group(2))
            self.track_started.emit(self._current_track)
            self.track_filename.emit(self._current_track, start_match.group(3))
            self.track_progress_changed.emit(0)

        overall_pct, track_pct = self._progress.compute(line, self._current_track)
        if overall_pct is not None:
            self.progress_changed.emit(overall_pct)
        if track_pct is not None:
            self.track_progress_changed.emit(track_pct)
