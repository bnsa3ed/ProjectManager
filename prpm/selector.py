"""Interactive multi-select file picker for --preview mode."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from .core import ProjectScan

_MAX_NAME = 42   # max chars for filename before truncation
_MAX_PATH = 36   # max chars for the folder-path hint


def _trunc(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def _label(path_str: str, project_dir: Path) -> tuple[str, str]:
    """
    Return (filename, hint) as plain strings.
    hint is the folder context or tag — empty string if not needed.
    """
    src = Path(path_str)
    try:
        rel = src.relative_to(project_dir)
        parts = rel.parts
        hint = _trunc("/".join(parts[:-1]), _MAX_PATH) if len(parts) > 2 else ""
    except ValueError:
        hint = "external"
    return _trunc(src.name, _MAX_NAME), hint


def _row(tag: str, name: str, hint: str) -> str:
    """Format one choice title as fixed columns — plain text only."""
    tag_col  = f"{tag:<7}"          # 7-char left-aligned tag
    name_col = f"{name:<{_MAX_NAME}}"
    if hint:
        return f"{tag_col}  {name_col}  {hint}"
    return f"{tag_col}  {name_col}"


def _build_choices(scans: list[ProjectScan]) -> list:
    import questionary

    choices = []

    for scan in scans:
        if scan.status not in ("ok", "pm_exists"):
            continue

        # ── Project header separator ──────────────────────────────────────
        choices.append(questionary.Separator(""))
        choices.append(questionary.Separator(f"  {scan.project_name}"))
        choices.append(questionary.Separator(f"  {'─' * 55}"))

        # ── .prproj file ──────────────────────────────────────────────────
        if scan.prproj:
            choices.append(questionary.Choice(
                title=_row("[proj]", _trunc(scan.prproj.name, _MAX_NAME), ""),
                value=str(scan.prproj),
                checked=True,
            ))

        # ── Referenced media ──────────────────────────────────────────────
        for path_str in scan.referenced_paths:
            name, hint = _label(path_str, scan.project_dir)
            exists = Path(path_str).exists()

            if exists:
                choices.append(questionary.Choice(
                    title=_row("[media]", name, hint),
                    value=path_str,
                    checked=True,
                ))
            else:
                choices.append(questionary.Choice(
                    title=_row("[miss]", name, hint or "not on disk"),
                    value=path_str,
                    checked=False,
                    disabled="not on disk",
                ))

        # ── Final/ folder ─────────────────────────────────────────────────
        for f in scan.final_files:
            rel = f.relative_to(scan.project_dir / "Final")
            choices.append(questionary.Choice(
                title=_row("[final]", _trunc(f.name, _MAX_NAME), str(rel.parent) if rel.parent != Path(".") else ""),
                value=str(f),
                checked=True,
            ))

    return choices


def interactive_select(scans: list[ProjectScan]) -> set[str] | None:
    """
    Show an interactive multi-select list of all files across all projects.
    Returns the set of selected file paths, or None if the user cancelled.
    """
    import questionary
    from questionary import Style

    style = Style([
        ("separator",         "fg:#555555"),
        ("pointer",           "fg:#00aaff bold"),
        ("highlighted",       "fg:#ffffff bg:#333333 bold"),
        # checked items
        ("checkbox-selected", "fg:#00dd00"),
        ("selected",          "fg:#00dd00"),
        # unchecked
        ("checkbox",          "fg:#888888"),
        # disabled (missing files)
        ("disabled",          "fg:#cc8800 italic"),
        ("instruction",       "fg:#555555"),
        ("question",          "fg:#ffffff bold"),
        ("answer",            "fg:#00dd00 bold"),
    ])

    active_scans = [s for s in scans if s.status in ("ok", "pm_exists") and s.prproj]
    total_files = sum(
        1 + len(s.referenced_paths) + len(s.final_files)
        for s in active_scans
    )

    click.echo()
    click.echo(
        f"  {click.style(str(total_files), bold=True)} files across "
        f"{click.style(str(len(active_scans)), bold=True)} projects"
    )
    click.echo(click.style(
        "  Space = toggle  ·  A = toggle all  ·  Enter = confirm  ·  Ctrl+C = cancel",
        fg="bright_black",
    ))

    choices = _build_choices(scans)
    if not choices:
        click.echo(click.style("  No files found.", fg="yellow"))
        return None

    result = questionary.checkbox(
        "Select files to collect:",
        choices=choices,
        style=style,
        instruction=" ",
    ).ask()

    if result is None:
        click.echo(click.style("\n  Cancelled.\n", fg="bright_black"))
        return None

    return set(result)
