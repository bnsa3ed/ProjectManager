"""Interactive multi-select file picker for --preview mode."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from .core import ProjectScan


# ---------------------------------------------------------------------------
# Display helpers  (plain text only — no click.style inside questionary titles)
# ---------------------------------------------------------------------------

def _label(path_str: str, project_dir: Path) -> str:
    """Short, readable label for a file — plain text, no ANSI codes."""
    src = Path(path_str)
    try:
        rel = src.relative_to(project_dir)
        parts = rel.parts
        if len(parts) > 2:
            folder = "/".join(parts[:-1])
            return f"{src.name}   ({folder})"
        return str(rel)
    except ValueError:
        return f"{src.name}   [external]"


# ---------------------------------------------------------------------------
# Build questionary choice list
# ---------------------------------------------------------------------------

def _build_choices(scans: list[ProjectScan]) -> list:
    import questionary

    choices = []

    for scan in scans:
        if scan.status not in ("ok", "pm_exists"):
            continue

        # ── Project separator ─────────────────────────────────────────────
        choices.append(questionary.Separator(f"  {scan.project_name}"))

        # ── .prproj file ──────────────────────────────────────────────────
        if scan.prproj:
            choices.append(questionary.Choice(
                title=f"  {scan.prproj.name}",
                value=str(scan.prproj),
                checked=True,
            ))

        # ── Referenced media files ────────────────────────────────────────
        for path_str in scan.referenced_paths:
            src = Path(path_str)
            exists = src.exists()
            label = _label(path_str, scan.project_dir)

            if exists:
                choices.append(questionary.Choice(
                    title=f"  {label}",
                    value=path_str,
                    checked=True,
                ))
            else:
                choices.append(questionary.Choice(
                    title=f"  [missing]  {label}",
                    value=path_str,
                    checked=False,
                    disabled="not on disk",
                ))

        # ── Final/ folder files ───────────────────────────────────────────
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

    # questionary style — all coloring lives here, never inside title strings
    style = Style([
        ("separator",      "fg:#888888 bold"),
        ("checkbox",       "fg:#00cc00"),
        ("checkbox-selected", "fg:#00cc00 bold"),
        ("pointer",        "fg:#00aaff bold"),
        ("highlighted",    "fg:#ffffff bold"),
        ("selected",       "fg:#00cc00"),
        ("disabled",       "fg:#ffaa00 italic"),
        ("instruction",    "fg:#888888"),
        ("question",       "fg:#ffffff bold"),
        ("answer",         "fg:#00cc00 bold"),
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
    click.echo()

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
