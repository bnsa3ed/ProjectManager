# prpm — Premiere Project Manager

**One command to pack up everything a Premiere project needs into a single folder.**

When you finish editing, your project files are scattered everywhere — raw footage in one place, sounds from a pack in another, graphics from a shared drive somewhere else. `prpm` reads your `.prproj` file, finds every piece of media it references, and copies it all into a clean `PM_ProjectName` folder sitting right inside your project. Ready to archive, hand off, or back up.

---

## Requirements

- **Python 3.9 or later** — [Download Python](https://www.python.org/downloads/)
- **macOS** or **Linux** (Windows support coming soon)
- Adobe Premiere Pro projects (`.prproj` files)

---

## Install

### Recommended — one-line installer (macOS / Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/bnsa3ed/ProjectManager/main/install.sh | bash
```

This installs `prpm` system-wide using [pipx](https://pipx.pypa.io) so the `prpm` command is available everywhere, not just inside a specific folder.

### Alternative — pip

```bash
pip install prpm
```

> If you get "command not found" after installing with pip, use `pipx install prpm` instead, or add Python's scripts folder to your PATH.

---

## Quick Start

```bash
# 1. Open your terminal and navigate to your projects folder
cd "/Volumes/MyDrive/Reels/MyChannel"

# 2. Open the interactive file picker — review and toggle files before collecting
prpm run --preview

# 3. Or just collect everything immediately
prpm run
```

---

## What It Does

For each project folder that contains a `.prproj` file, `prpm` will:

1. Parse the Premiere project to find every media file it references
2. Copy all those files into a `PM_ProjectName/` subfolder inside the project
3. Also copy the `Final/` folder (your rendered exports) if it exists
4. Files from outside the project folder go into `_external/` to stay organised
5. Write a full log of everything copied and anything missing
6. Report a clear summary at the end

**Before:**
```
My Channel/
├── My Video/
│   ├── My Video.prproj
│   ├── raw_footage.mp4
│   ├── Final/
│   │   └── Export.mp4
│   └── Premiere Composer Files/
│       └── sounds...
├── Another Video/
│   └── ...
```

**After `prpm run`:**
```
My Channel/
├── My Video/
│   ├── My Video.prproj
│   ├── raw_footage.mp4
│   ├── Final/
│   ├── Premiere Composer Files/
│   └── PM_My Video/              ← new folder with everything
│       ├── My Video.prproj
│       ├── raw_footage.mp4
│       ├── Final/
│       ├── Premiere Composer Files/
│       └── _external/            ← files from outside the project
```

---

## Commands

### `prpm run` — Collect media

```
prpm run [PROJECT] [OPTIONS]
```

| Option | Short | Description |
|---|---|---|
| `--preview` | `-p` | Interactive file picker — see all files, toggle any off before collecting |
| `--overwrite` | `-o` | Re-collect projects that already have a PM_ folder |
| `--verbose` | `-v` | Print each file name as it is copied |
| `--dir PATH` | `-d` | Use a specific projects folder instead of the current directory |

**Examples:**

```bash
# Collect all projects in the current folder
prpm run

# Open interactive picker — review files before collecting
prpm run --preview

# Collect only one specific project
prpm run "My Video Title"

# Re-collect a project that was already processed
prpm run "My Video Title" --overwrite

# Collect from a specific folder path
prpm run --dir "/Volumes/MyDrive/Reels/MyChannel"

# Show each file as it copies
prpm run --verbose
```

---

## Interactive Preview (`--preview`)

Running `prpm run --preview` opens a full-screen file picker before anything is copied:

```
  42 files across 6 projects — toggle any file off to skip it.

  Space = toggle  ·  A = toggle all  ·  Enter = confirm  ·  Ctrl+C = cancel

? Select files to collect:
  ──── My Video ───────────────────────────────────────────
 ❯◉  My Video.prproj
  ◉  raw_footage.mp4
  ◉  Hollow Pop 06.wav  (Premiere Composer Files/...)
  ◉  Final/Export.mp4
  ──── Another Video ──────────────────────────────────────
  ◉  Another Video.prproj
  ◉  clip.mp4
  ○  ⚠  old_clip.mp4  [not found on disk]
```

- **All files are pre-selected** — just press Enter to collect everything
- **Toggle any file off** with Space to skip it
- **Missing files** (not on disk) are shown but cannot be selected
- **Press Ctrl+C** to cancel without copying anything
- After you confirm, only the selected files are collected

---

## Error Handling

`prpm` detects common problems and offers to fix them automatically:

**Missing dependency:**
```
  Missing dependency: questionary
  This package is required and can be installed automatically.

  Install 'questionary' now? [Y/n]:
```

**Permission error:**
```
  ERROR  Permission denied.

  Path: /Volumes/MyDrive/My Video/raw_footage.mp4

  Possible fixes:
    · Check that macOS hasn't blocked access to this folder
      (System Settings → Privacy & Security → Files and Folders)
```

**No disk space:**
```
  ERROR  Not enough disk space.

  Free up space on the destination drive and try again.
```

---

## Log File

Every run creates a `PM_log_YYYYMMDD_HHMMSS.log` file in your projects folder. It records every file copied, every missing file, and any errors — useful if you need to track down why something wasn't collected.

---

## FAQ

**Does it move or delete my original files?**
No. `prpm` only copies files. Your originals are never touched.

**Can I run it multiple times?**
Yes. By default it skips projects that already have a `PM_` folder. Use `--overwrite` to update an existing PM_ folder.

**What is the `_external` folder?**
Some projects reference files stored outside the project folder — sound packs, stock footage, graphics from another project. Those go into `_external/` so they're collected but kept separate.

**A file shows as "missing" — what do I do?**
The file was referenced in Premiere but can't be found on disk. Common causes: it's on an external drive that isn't plugged in, it's in a cloud folder that isn't synced, or it was deleted. Connect the drive or re-sync the cloud folder, then run `prpm run --overwrite` again.

**Does it work with After Effects files?**
Yes. `.aegraphic` and other After Effects-linked files referenced in your Premiere project are collected like any other media.

---

## License

MIT — free to use, share, and modify.
