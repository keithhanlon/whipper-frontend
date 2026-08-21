# Whipper Frontend

A Qt (PySide6) GUI for [whipper](https://github.com/whipper-team/whipper), an
accurate, AccurateRip-verifying CD ripper for Linux (in the spirit of EAC/XLD).
Whipper Frontend wraps whipper's own command-line interface via subprocess. It never imports whipper's internals — so it stays compatible across whipper
version bumps rather than depending on an unstable internal API.

## Features

- Drive detection and read-offset determination (wraps `whipper drive
  analyze` / `whipper offset find`), with the confirmed offset stored in
  whipper's own config.
- Rip a disc with live dual progress bars (overall disc + current track),
  a live track table, and album info, all parsed from whipper's own
  real-time output.
- Custom track/disc file naming templates, with live validation against
  whipper's actual template rules.
- Cover art fetching (save to file, embed in FLAC, or both).
- Optional filename sanitization for VFAT/exFAT/Windows-formatted drives
  and network shares.
- "Keep ripping if one track fails" and "rip even if metadata isn't
  found" options for damaged or obscure discs.
- Eject button, and an optional auto-eject-when-finished setting.
- Rip log verification via [OPSnet's logchecker](https://github.com/OPSnet/Logchecker)
  which runs
  automatically after each rip if configured, with color-coded results.

## Requirements

- Linux, with a desktop environment (developed primarily on KDE Plasma)
- [whipper](https://github.com/whipper-team/whipper) installed and on `PATH`
- Python 3.10+ and PySide6 (see Setup below for two ways to get this)
- Optional: PHP (`php-cli`) and
  [logchecker.phar](https://github.com/OPSnet/Logchecker/releases) for log
  verification

## Setup

### Option A: Debian package (recommended on Debian/Ubuntu-based systems)

A `.deb` is available under `debian/` — build it yourself with:

```bash
sudo apt install debhelper-compat
dpkg-buildpackage -us -uc -b
```

This produces `../whipper-frontend_<version>_all.deb` in the parent
directory. Install it with:

```bash
sudo apt install ./whipper-frontend_<version>_all.deb
```

This pulls in `whipper`, the system PySide6 packages, and all other
dependencies automatically — no virtual environment needed. The app is then
available as `whipper-frontend` on your `PATH` and in your application menu.

### Option B: Run from source

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

## Project layout

```
main.py                     Entry point when run from source
requirements.txt
debian/                     .deb packaging (control, rules, desktop entry, icon)
whippergui/
  app.py                    QApplication bootstrap, checks whipper is on PATH
  main_window.py            Main window: drive picker, track table, controls
  rip_worker.py             QThread wrapping the `whipper cd rip` subprocess
  offset_dialog.py          Drive read-offset determination UI
  offset_worker.py          QThread wrapping `whipper drive analyze`/`offset find`
  offset_utils.py           Reads whipper's own config for stored offsets
  device_utils.py           Optical drive detection
  settings.py               Persisted app settings (QSettings)
  settings_dialog.py        Tabbed Settings window
  templates_dialog.py       Track/disc naming template editor
  whipper_config.py         Reads/writes whipper's own config file
  log_verify.py             Runs and parses OPSnet's logchecker
  log_verify_dialog.py      Log verification results window
```

## License

GPLv3 — see [LICENSE](LICENSE). This project wraps whipper (also GPLv3) via
subprocess rather than linking against it, but is released under the same
license as a courtesy, given its purpose.
