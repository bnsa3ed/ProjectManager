"""Core consolidation logic — parses .prproj files and copies media."""

from __future__ import annotations

import gzip
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ProjectResult:
    project_name: str
    status: str  # "ok" | "skipped_no_prproj" | "skipped_exists" | "error"
    prproj: Path | None = None
    pm_dir: Path | None = None
    referenced: int = 0
    media_copied: int = 0
    final_copied: int = 0
    missing_on_disk: list[str] = field(default_factory=list)
    copy_failed: list[str] = field(default_factory=list)

    @property
    def total_copied(self) -> int:
        return self.media_copied + self.final_copied

    @property
    def has_issues(self) -> bool:
        return bool(self.missing_on_disk or self.copy_failed)


# Event callback: (level, message)
# Levels: "info" | "warn" | "error" | "skip" | "copied" | "missing" | "would_copy"
EventCallback = Callable[[str, str], None]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def extract_media_paths(prproj_path: Path) -> list[str]:
    """Decompress and parse a .prproj XML, returning all unique media file paths."""
    try:
        with gzip.open(prproj_path, "rb") as fh:
            content = fh.read().decode("utf-8", errors="replace")
    except Exception as exc:
        raise RuntimeError(f"Cannot read '{prproj_path.name}': {exc}") from exc

    raw = re.findall(r"<ActualMediaFilePath>([^<]+)</ActualMediaFilePath>", content)
    seen: set[str] = set()
    paths: list[str] = []
    for p in raw:
        p = p.strip()
        if p and p.startswith("/") and p not in seen:
            seen.add(p)
            paths.append(p)
    return paths


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def _destination(src: Path, project_dir: Path, pm_dir: Path) -> Path:
    """
    Map a source file to its destination inside pm_dir.
    Files inside the project folder keep their relative path.
    Files from outside go into _external/ preserving their absolute path structure.
    """
    try:
        return pm_dir / src.relative_to(project_dir)
    except ValueError:
        return pm_dir / "_external" / str(src).lstrip("/")


def _copy(src: Path, dst: Path) -> bool:
    """Copy src → dst, creating parent directories as needed."""
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def process_project(
    project_dir: Path,
    dry_run: bool = False,
    overwrite: bool = False,
    on_event: EventCallback | None = None,
) -> ProjectResult:
    """
    Consolidate all media referenced by the Premiere project inside project_dir
    into a PM_<name> subfolder.

    Args:
        project_dir: Path to the project folder (must contain a .prproj file).
        dry_run:     If True, report what would happen without copying anything.
        overwrite:   If True, re-process projects that already have a PM_ folder.
        on_event:    Optional callback receiving (level, message) for each action.

    Returns:
        A ProjectResult describing what happened.
    """
    emit: EventCallback = on_event or (lambda _l, _m: None)
    result = ProjectResult(project_name=project_dir.name, status="ok")

    # ── Find .prproj ─────────────────────────────────────────────────────
    prprojs = [p for p in project_dir.glob("*.prproj") if not p.name.startswith("._")]
    if not prprojs:
        result.status = "skipped_no_prproj"
        emit("skip", "No .prproj file found")
        return result

    if len(prprojs) > 1:
        emit("warn", f"Multiple .prproj files found — using '{prprojs[0].name}'")

    prproj = prprojs[0]
    result.prproj = prproj

    pm_dir = project_dir / f"PM_{project_dir.name}"
    result.pm_dir = pm_dir

    if pm_dir.exists() and not overwrite:
        result.status = "skipped_exists"
        emit("skip", "PM folder already exists — use --overwrite to redo")
        return result

    # ── Extract referenced paths ─────────────────────────────────────────
    try:
        referenced = extract_media_paths(prproj)
    except RuntimeError as exc:
        result.status = "error"
        emit("error", str(exc))
        return result

    result.referenced = len(referenced)
    emit("info", f"Found {len(referenced)} media file(s)")

    if dry_run:
        emit("info", f"Would create: {pm_dir.name}/")

    # ── Copy .prproj ─────────────────────────────────────────────────────
    if not dry_run:
        if not _copy(prproj, pm_dir / prproj.name):
            result.copy_failed.append(str(prproj))
            emit("error", f"Failed to copy '{prproj.name}'")

    # ── Copy referenced media ─────────────────────────────────────────────
    for path_str in referenced:
        src = Path(path_str)
        if not src.exists():
            result.missing_on_disk.append(path_str)
            emit("missing", path_str)
            continue

        if dry_run:
            emit("would_copy", path_str)
            result.media_copied += 1
            continue

        dst = _destination(src, project_dir, pm_dir)
        if _copy(src, dst):
            result.media_copied += 1
            emit("copied", src.name)
        else:
            result.copy_failed.append(path_str)
            emit("error", f"Failed to copy '{src.name}'")

    # ── Copy Final folder (rendered exports) ─────────────────────────────
    final_src = project_dir / "Final"
    if final_src.is_dir():
        final_files = [
            f for f in final_src.rglob("*")
            if f.is_file() and not f.name.startswith("._")
        ]
        if dry_run:
            emit("info", f"Would copy Final/ ({len(final_files)} file(s))")
            result.final_copied = len(final_files)
        else:
            for f in final_files:
                dst = pm_dir / "Final" / f.relative_to(final_src)
                if _copy(f, dst):
                    result.final_copied += 1
                else:
                    result.copy_failed.append(str(f))
            emit("copied", f"Final/ ({result.final_copied}/{len(final_files)} file(s))")

    return result
