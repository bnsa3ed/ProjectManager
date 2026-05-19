# prpm — Premiere Project Manager

**One command to pack up everything a Premiere project needs into a single folder.**

When you finish editing, your project files are scattered everywhere — raw footage in one place, sounds from a pack in another, graphics from a shared drive somewhere else. `prpm` reads your `.prproj` file, finds every piece of media it references, and copies it all into a clean `PM_ProjectName` folder sitting right inside your project. Ready to archive, hand off, or back up.

---

## Requirements

- **Python 3.9 or later** — [Download Python](https://www.python.org/downloads/)
- **Adobe Premiere Pro** projects (`.prproj` files)
- Works on **macOS** and **Windows**

---

## Install

```bash
pip install prpm
```

That's it. The `prpm` command is now available in your terminal.

> **Tip:** If you get a "command not found" error after installing, try `pip install --user prpm` and restart your terminal.

---

## Quick Start

```bash
# 1. Open your terminal and navigate to your projects folder
cd /Volumes/MyDrive/Reels/MyChannel

# 2. Preview what will be collected (nothing is copied yet)
prpm run --preview

# 3. Collect everything
prpm run
```

---

## What It Does

For each project folder that contains a `.prproj` file, `prpm` will:

1. Parse the Premiere project to find every media file it references
2. Copy all those files into a `PM_ProjectName/` subfolder
3. Also copy the `Final/` folder (your rendered exports) if it exists
4. Write a full log of everything that was copied and anything that was missing
5. Report a summary at the end

**Before:**
```
My Channel/
├── My Video/
│   ├── My Video.prproj
│   ├── raw_footage.mp4
│   ├── Final/
│   │   └── My Video - Export.mp4
│   └── Premiere Composer Files/
│       └── ...
├── Another Video/
│   └── ...
```

**After running `prpm run`:**
```
My Channel/
├── My Video/
│   ├── My Video.prproj
│   ├── raw_footage.mp4
│   ├── Final/
│   │   └── My Video - Export.mp4
│   ├── Premiere Composer Files/
│   │   └── ...
│   └── PM_My Video/              ← new folder
│       ├── My Video.prproj
│       ├── raw_footage.mp4
│       ├── Final/
│       │   └── My Video - Export.mp4
│       ├── Premiere Composer Files/
│       │   └── ...
│       └── _external/            ← files from outside the project folder
│           └── ...
```

---

## Commands

### `prpm run` — Collect media

```
prpm run [PROJECT] [OPTIONS]
```

| Option | Short | Description |
|---|---|---|
| `--preview` | `-p` | Show what would be collected without copying anything |
| `--overwrite` | `-o` | Re-collect projects that already have a PM_ folder |
| `--verbose` | `-v` | Print each file name as it is copied |
| `--dir PATH` | `-d` | Use a specific projects folder instead of the current directory |

**Examples:**

```bash
# Collect all projects in the current folder
prpm run

# Preview without copying (safe to run any time)
prpm run --preview

# Collect only one specific project
prpm run "My Video Title"

# Re-collect a project you already ran (updates the PM_ folder)
prpm run "My Video Title" --overwrite

# Collect from a specific folder path
prpm run --dir "/Volumes/MyDrive/Reels/MyChannel"

# Show each file as it copies
prpm run --verbose

# Combine options
prpm run "My Video" --overwrite --verbose
```

---

## Understanding the Output

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  prpm v1.0.0  ·  COLLECT
  /Volumes/MyDrive/Reels/MyChannel
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📂  My Video
  ✓ Collected: 8 file(s)
  → My Video/PM_My Video/

📂  Another Video
  ⚠ Missing: old_clip.mp4
  ✓ Collected: 5 file(s), 1 missing
  → Another Video/PM_Another Video/

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Results
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Projects processed  2
  Files referenced    13
  Files copied        13
  Missing on disk     1

  Full log → PM_log_20260519_110234.log
```

**What "Missing on disk" means:** The Premiere project references a file that no longer exists on your computer — it may have been deleted, moved, or is on a drive that isn't plugged in. These files cannot be collected, but everything else still will be.

---

## Log File

Every run creates a `PM_log_YYYYMMDD_HHMMSS.log` file in your projects folder. It contains a full record of every file copied, every file that was missing, and any errors — useful if you need to track down why a file wasn't collected.

---

## FAQ

**Does it move or delete my original files?**
No. `prpm` only copies files. Your originals are never touched.

**Can I run it multiple times?**
Yes. By default it skips projects that already have a `PM_` folder. Use `--overwrite` to update an existing PM_ folder.

**What is the `_external` folder?**
When a project references files stored outside the project folder (e.g. sound packs, graphics from another project, downloads), those files are placed inside `_external/` to keep them organized separately.

**A file shows as "missing" — what do I do?**
The file was referenced in Premiere but can't be found on disk. Common causes: the file was deleted, it's on an external drive that isn't connected, or it was on a cloud drive that isn't synced. Connect the drive or re-sync the cloud folder, then run `prpm run --overwrite` again.

**Does it work with After Effects files?**
Yes. `.aegraphic` and other After Effects-linked files that are referenced in your Premiere project will be collected like any other media file.

---

## License

MIT — free to use, share, and modify.
