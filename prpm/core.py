"""Core consolidation logic — parses .prproj files and copies media."""

from __future__ import annotations

import gzip
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# macOS/Windows system files that should never be collected
_SYSTEM_FILES: frozenset[str] = frozenset({
    "Icon\r",       # macOS folder icon (Icon + carriage-return)
    ".DS_Store",
    "desktop.ini",
    "Thumbs.db",
})


def _is_system_file(name: str) -> bool:
    return name.startswith("._") or name in _SYSTEM_FILES


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ProjectScan:
    """Result of scanning a project directory without copying anything."""
    project_dir: Path
    project_name: str
    status: str           # "ok" | "no_prproj" | "pm_exists" | "error"
    prproj: Path | None = None
    referenced_paths: list[str] = field(default_factory=list)
    final_files: list[Path] = field(default_factory=list)
    pm_dir: Path | None = None
    error_msg: str = ""


@dataclass
class ProjectResult:
    """Result of collecting files for one project."""
    project_name: str
    status: str           # "ok" | "skipped_no_prproj" | "skipped_exists" | "error"
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
EventCallback = Callable[[str, str], None]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def extract_media_paths(prproj_path: Path) -> list[str]:
    """Decompress and parse a .prproj XML, returning all unique absolute media paths."""
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
    try:
        return pm_dir / src.relative_to(project_dir)
    except ValueError:
        return pm_dir / "_external" / str(src).lstrip("/")


def _copy(src: Path, dst: Path) -> bool:
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Scan (read-only, no copying)
# ---------------------------------------------------------------------------

def scan_project(project_dir: Path, overwrite: bool = False) -> ProjectScan:
    """
    Inspect a project directory and return metadata about what would be collected.
    Does not copy anything.
    """
    scan = ProjectScan(
        project_dir=project_dir,
        project_name=project_dir.name,
        status="ok",
        pm_dir=project_dir / f"PM_{project_dir.name}",
    )

    prprojs = [p for p in project_dir.glob("*.prproj") if not _is_system_file(p.name)]
    if not prprojs:
        scan.status = "no_prproj"
        return scan

    scan.prproj = prprojs[0]

    if scan.pm_dir.exists() and not overwrite:
        scan.status = "pm_exists"

    try:
        scan.referenced_paths = extract_media_paths(scan.prproj)
    except RuntimeError as exc:
        scan.status = "error"
        scan.error_msg = str(exc)
        return scan

    final_dir = project_dir / "Final"
    if final_dir.is_dir():
        scan.final_files = [
            f for f in final_dir.rglob("*")
            if f.is_file() and not _is_system_file(f.name)
        ]

    return scan


# ---------------------------------------------------------------------------
# Collect (copies files)
# ---------------------------------------------------------------------------

def process_project(
    project_dir: Path,
    dry_run: bool = False,
    overwrite: bool = False,
    selected_paths: set[str] | None = None,
    on_event: EventCallback | None = None,
) -> ProjectResult:
    """
    Consolidate all media referenced by the Premiere project into a PM_<name> subfolder.

    Args:
        project_dir:    Path to the project folder.
        dry_run:        If True, report what would happen without copying.
        overwrite:      If True, re-process projects that already have a PM_ folder.
        selected_paths: If provided, only copy files whose absolute path is in this set.
                        The .prproj file is always copied regardless.
        on_event:       Optional callback (level, message) for progress reporting.
    """
    emit: EventCallback = on_event or (lambda _l, _m: None)
    result = ProjectResult(project_name=project_dir.name, status="ok")

    # ── Find .prproj ──────────────────────────────────────────────────────
    prprojs = [p for p in project_dir.glob("*.prproj") if not _is_system_file(p.name)]
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

    # ── Extract referenced paths ──────────────────────────────────────────
    try:
        referenced = extract_media_paths(prproj)
    except RuntimeError as exc:
        result.status = "error"
        emit("error", str(exc))
        return result

    result.referenced = len(referenced)
    emit("info", f"Found {len(referenced)} media file(s)")

    # ── Copy .prproj (always, not subject to selection) ───────────────────
    if not dry_run:
        if not _copy(prproj, pm_dir / prproj.name):
            result.copy_failed.append(str(prproj))
            emit("error", f"Failed to copy '{prproj.name}'")
    else:
        emit("info", f"Would create: {pm_dir.name}/")

    # ── Copy referenced media ─────────────────────────────────────────────
    for path_str in referenced:
        if selected_paths is not None and path_str not in selected_paths:
            emit("skipped", Path(path_str).name)
            continue

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

    # ── Copy Final folder ─────────────────────────────────────────────────
    final_src = project_dir / "Final"
    if final_src.is_dir():
        final_files = [
            f for f in final_src.rglob("*")
            if f.is_file() and not _is_system_file(f.name)
        ]
        skipped_final = 0
        for f in final_files:
            if selected_paths is not None and str(f) not in selected_paths:
                skipped_final += 1
                continue

            if dry_run:
                emit("would_copy", str(f))
                result.final_copied += 1
                continue

            dst = pm_dir / "Final" / f.relative_to(final_src)
            if _copy(f, dst):
                result.final_copied += 1
            else:
                result.copy_failed.append(str(f))

        label = f"Final/ ({result.final_copied}"
        if skipped_final:
            label += f", {skipped_final} skipped"
        label += " file(s))"
        if not dry_run or result.final_copied:
            emit("copied" if not dry_run else "would_copy", label)

    return result
