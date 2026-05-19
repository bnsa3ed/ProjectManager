"""Interactive two-level file picker: project list → per-project file review."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from .core import ProjectScan

_MAX_NAME = 44
_MAX_PATH = 36


def _trunc(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def _file_label(path_str: str, project_dir: Path) -> str:
    """One-line plain-text label: filename + folder hint."""
    src = Path(path_str)
    try:
        rel = src.relative_to(project_dir)
        parts = rel.parts
        hint = _trunc("/".join(parts[:-1]), _MAX_PATH) if len(parts) > 2 else ""
    except ValueError:
        hint = "external"

    name = _trunc(src.name, _MAX_NAME)
    tag_w = 9   # "[media]  " width
    if hint:
        return f"{name:<{_MAX_NAME}}  {hint}"
    return name


def _count_missing(scan: ProjectScan) -> int:
    return sum(1 for p in scan.referenced_paths if not Path(p).exists())


# ---------------------------------------------------------------------------
# Shared questionary style
# ---------------------------------------------------------------------------

def _make_style():
    from questionary import Style
    return Style([
        ("separator",          "fg:#555555"),
        ("pointer",            "fg:#00aaff bold"),
        ("highlighted",        "fg:#ffffff bg:#1a1a2e bold"),
        ("checkbox-selected",  "fg:#00dd00"),
        ("selected",           "fg:#00dd00"),
        ("checkbox",           "fg:#666666"),
        ("disabled",           "fg:#cc8800 italic"),
        ("instruction",        "fg:#555555"),
        ("question",           "fg:#ffffff bold"),
        ("answer",             "fg:#00dd00 bold"),
    ])


# ---------------------------------------------------------------------------
# Screen 1 — project list
# ---------------------------------------------------------------------------

def _select_projects(scans: list[ProjectScan]) -> list[ProjectScan] | None:
    import questionary

    style = _make_style()
    choices = []

    for scan in scans:
        total = 1 + len(scan.referenced_paths) + len(scan.final_files)
        missing = _count_missing(scan)
        name = _trunc(scan.project_name, 40)

        if missing:
            stats = f"{total} files   ⚠ {missing} missing"
        else:
            stats = f"{total} files"

        choices.append(questionary.Choice(
            title=f"  {name:<42}  {stats}",
            value=scan,
            checked=True,
        ))

    click.echo()
    click.echo(click.style(
        "  Space = toggle  ·  A = toggle all  ·  Enter = confirm  ·  Ctrl+C = cancel",
        fg="bright_black",
    ))
    click.echo()

    result = questionary.checkbox(
        "Select projects to collect:",
        choices=choices,
        style=style,
        instruction=" ",
    ).ask()

    return result  # None on Ctrl+C


# ---------------------------------------------------------------------------
# Screen 2+ — per-project file review
# ---------------------------------------------------------------------------

def _select_files(scan: ProjectScan, index: int, total: int) -> set[str] | None:
    import questionary

    style = _make_style()
    choices = []
    missing_count = _count_missing(scan)

    # .prproj
    if scan.prproj:
        choices.append(questionary.Choice(
            title=f"  [proj]    {_trunc(scan.prproj.name, _MAX_NAME)}",
            value=str(scan.prproj),
            checked=True,
        ))

    # Media files
    for path_str in scan.referenced_paths:
        exists = Path(path_str).exists()
        label = _file_label(path_str, scan.project_dir)
        if exists:
            choices.append(questionary.Choice(
                title=f"  [media]   {label}",
                value=path_str,
                checked=True,
            ))
        else:
            choices.append(questionary.Choice(
                title=f"  [miss]    {label}",
                value=path_str,
                checked=False,
                disabled="not on disk",
            ))

    # Final/ files
    for f in scan.final_files:
        rel = f.relative_to(scan.project_dir / "Final")
        hint = str(rel.parent) if rel.parent != Path(".") else ""
        label = f"{_trunc(f.name, _MAX_NAME):<{_MAX_NAME}}  {hint}" if hint else _trunc(f.name, _MAX_NAME)
        choices.append(questionary.Choice(
            title=f"  [final]   {label}",
            value=str(f),
            checked=True,
        ))

    # Header
    progress = click.style(f"[{index}/{total}]", fg="bright_black")
    name     = click.style(scan.project_name, bold=True)
    warn     = click.style(f"  ⚠ {missing_count} missing", fg="yellow") if missing_count else ""
    click.echo()
    click.echo(f"  {progress}  {name}{warn}")
    click.echo(click.style("  ─" * 28, fg="bright_black"))

    result = questionary.checkbox(
        "Files to collect:",
        choices=choices,
        style=style,
        instruction=" (Enter to accept all)",
    ).ask()

    return set(result) if result is not None else None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def interactive_select(scans: list[ProjectScan]) -> set[str] | None:
    """
    Two-level interactive selection:
      1. Project list  — select / deselect entire projects
      2. File review   — for each selected project, review its files

    Returns the flat set of selected file paths, or None if cancelled.
    """
    active = [s for s in scans if s.status in ("ok", "pm_exists") and s.prproj]
    if not active:
        click.echo(click.style("  No projects found.", fg="yellow"))
        return None

    total_files  = sum(1 + len(s.referenced_paths) + len(s.final_files) for s in active)
    total_missing = sum(_count_missing(s) for s in active)

    click.echo()
    click.echo(
        f"  {click.style(str(len(active)), bold=True)} projects  ·  "
        f"{click.style(str(total_files), bold=True)} files total"
        + (f"  ·  {click.style(str(total_missing) + ' missing', fg='yellow')}" if total_missing else "")
    )

    # ── Screen 1: project selection ───────────────────────────────────────
    selected_scans = _select_projects(active)
    if selected_scans is None:
        click.echo(click.style("\n  Cancelled.\n", fg="bright_black"))
        return None
    if not selected_scans:
        click.echo(click.style("\n  No projects selected.\n", fg="yellow"))
        return None

    # ── Screen 2+: per-project file review ───────────────────────────────
    click.echo()
    click.echo(
        f"  {click.style(str(len(selected_scans)), bold=True)} project(s) selected — "
        "now review files for each one."
    )

    all_paths: set[str] = set()
    for i, scan in enumerate(selected_scans, 1):
        paths = _select_files(scan, i, len(selected_scans))
        if paths is None:
            click.echo(click.style("\n  Cancelled.\n", fg="bright_black"))
            return None
        all_paths.update(paths)

    return all_paths
