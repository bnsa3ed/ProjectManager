"""Interactive multi-select file picker for --preview mode."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from .core import ProjectScan


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _short_display(path_str: str, project_dir: Path) -> str:
    """Human-readable label for a file path relative to its project."""
    src = Path(path_str)
    try:
        rel = src.relative_to(project_dir)
        parts = rel.parts
        if len(parts) > 2:
            return f"{src.name}  ({click.style('/'.join(parts[:-1]), fg='bright_black')})"
        return str(rel)
    except ValueError:
        return f"{src.name}  ({click.style('external', fg='bright_black')})"


# ---------------------------------------------------------------------------
# Build questionary choice list
# ---------------------------------------------------------------------------

def _build_choices(scans: list[ProjectScan]) -> list:
    import questionary

    choices = []
    for scan in scans:
        if scan.status not in ("ok", "pm_exists"):
            continue

        # Project separator header
        choices.append(
            questionary.Separator(
                f"\n  {'─' * 4}  {scan.project_name}  {'─' * max(0, 44 - len(scan.project_name))}"
            )
        )

        # .prproj file — always pre-selected
        if scan.prproj:
            choices.append(questionary.Choice(
                title=click.style(f"  {scan.prproj.name}", fg="cyan"),
                value=str(scan.prproj),
                checked=True,
            ))

        # Referenced media files
        for path_str in scan.referenced_paths:
            src = Path(path_str)
            exists = src.exists()
            label = _short_display(path_str, scan.project_dir)

            if exists:
                choices.append(questionary.Choice(
                    title=f"  {label}",
                    value=path_str,
                    checked=True,
                ))
            else:
                choices.append(questionary.Choice(
                    title=click.style(f"  ⚠  {label}  [not found on disk]", fg="yellow"),
                    value=path_str,
                    checked=False,
                    disabled="not on disk",
                ))

        # Final/ folder files
        for f in scan.final_files:
            rel = f.relative_to(scan.project_dir / "Final")
            choices.append(questionary.Choice(
                title=f"  Final/{rel}",
                value=str(f),
                checked=True,
            ))

    return choices


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def interactive_select(scans: list[ProjectScan]) -> set[str] | None:
    """
    Show an interactive multi-select list of all files across all projects.
    Returns the set of selected file paths, or None if the user cancelled.
    """
    import questionary
    from questionary import Style

    style = Style([
        ("separator",     "fg:ansicyan bold"),
        ("checkbox",      "fg:ansigreen"),
        ("pointer",       "fg:ansicyan bold"),
        ("highlighted",   "fg:ansiwhite bold"),
        ("selected",      "fg:ansigreen"),
        ("disabled",      "fg:ansiyellow"),
        ("instruction",   "fg:ansibrightblack"),
        ("question",      "fg:ansiwhite bold"),
        ("answer",        "fg:ansigreen bold"),
    ])

    total_files = sum(
        1 + len(s.referenced_paths) + len(s.final_files)
        for s in scans if s.status in ("ok", "pm_exists") and s.prproj
    )

    click.echo()
    click.echo(
        f"  {click.style(str(total_files), bold=True)} files across "
        f"{click.style(str(sum(1 for s in scans if s.status in ('ok', 'pm_exists'))), bold=True)} "
        f"projects — toggle any file off to skip it.\n"
    )
    click.echo(click.style(
        "  Space = toggle  ·  A = toggle all  ·  Enter = confirm  ·  Ctrl+C = cancel\n",
        fg="bright_black",
    ))

    choices = _build_choices(scans)
    if not choices:
        click.echo(click.style("  No files found to select.", fg="yellow"))
        return None

    result = questionary.checkbox(
        "Select files to collect:",
        choices=choices,
        style=style,
        instruction=" ",
    ).ask()

    # ask() returns None on Ctrl+C
    if result is None:
        click.echo(click.style("\n  Cancelled.\n", fg="bright_black"))
        return None

    return set(result)
