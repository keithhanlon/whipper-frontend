"""Runs OPSnet's logchecker (https://github.com/OPSnet/Logchecker) against
a finished rip's .log file.

This is a separate, optional external tool (PHP-based) — not something
whipper or this app installs. The user downloads logchecker.phar
themselves and points Settings at it (or just has it on PATH as
`logchecker`). We only ever shell out to its `analyze` command and parse
its plain-text output; we never touch its PHP internals.

Output format verified verbatim against OPSnet/Logchecker's own README:

    $ logchecker analyze --no_text path/to/file.log
    Ripper  : EAC
    Version : 1.0 beta 3
    Language: en
    Score   : 59
    Checksum: checksum_ok
    Details :
        Could not verify gap handling (-10 points)
        Could not verify id3 tag setting (-1 point)
        Range rip detected (-30 points)
"""
import re
import shutil
import subprocess
from dataclasses import dataclass, field

_FIELD_RE = re.compile(r"^(Ripper|Version|Language|Score|Checksum|Details)\s*:\s*(.*)$")


@dataclass
class LogVerifyResult:
    ripper: str = ""
    version: str = ""
    language: str = ""
    score: int | None = None
    checksum: str = ""
    details: list[str] = field(default_factory=list)
    error: str | None = None
    raw_output: str = ""


def find_logchecker(configured_path: str = "") -> str | None:
    """Resolves the logchecker binary: a configured path takes priority,
    otherwise fall back to whatever's on PATH as 'logchecker'.
    """
    if configured_path:
        return configured_path if shutil.which(configured_path) or _is_executable(configured_path) else None
    return shutil.which("logchecker")


def _is_executable(path: str) -> bool:
    import os

    return os.path.isfile(path) and os.access(path, os.X_OK)


def verify_log(log_path: str, binary: str) -> LogVerifyResult:
    try:
        result = subprocess.run(
            [binary, "analyze", "--no_text", log_path],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
        return LogVerifyResult(error=f"Couldn't run logchecker: {e}")

    output = result.stdout
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        return LogVerifyResult(
            error=f"logchecker exited with code {result.returncode}"
            + (f"\n\n{detail}" if detail else ""),
            raw_output=output,
        )

    return _parse_output(output)


def _parse_output(output: str) -> LogVerifyResult:
    parsed = LogVerifyResult(raw_output=output)
    lines = output.splitlines()
    in_details = False

    for line in lines:
        if in_details:
            # Detail entries are indented under the "Details :" header;
            # a non-indented (or blank) line ends the block.
            if line.strip() and line[0].isspace():
                parsed.details.append(line.strip())
                continue
            else:
                in_details = False

        m = _FIELD_RE.match(line)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()

        if key == "Ripper":
            parsed.ripper = value
        elif key == "Version":
            parsed.version = value
        elif key == "Language":
            parsed.language = value
        elif key == "Score":
            try:
                parsed.score = int(value)
            except ValueError:
                pass
        elif key == "Checksum":
            parsed.checksum = value
        elif key == "Details":
            in_details = True
            if value:
                parsed.details.append(value)

    return parsed
