"""Interactive two-level file picker: project list → per-project file review."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from .core import ProjectScan

_MAX_NAME = 44
_MAX_PATH = 36


# ─────────────────────────────────────────────────────────────────────────────
# Typography helpers  (research-backed: whitespace > borders, symbol > color)
# ─────────────────────────────────────────────────────────────────────────────

def _trunc(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def _sym(s: str, color: str) -> str:
    return click.style(s, fg=color, bold=True)


# Consistent symbol palette
OK    = _sym("✓", "green")
WARN  = _sym("⚠", "yellow")
SKIP  = _sym("○", "bright_black")
ARROW = click.style("›", fg="cyan", bold=True)
DIM   = lambda t: click.style(t, fg="bright_black")   # noqa: E731


def _spacer() -> None:
    click.echo()


def _rule() -> None:
    click.echo(DIM("  " + "─" * 54))


def _step_header(step: str, title: str, subtitle: str = "") -> None:
    """
    Clean step header — no boxes, just whitespace + typography.
    Pattern from Vercel/Railway: dim step counter, bold title, muted subtitle.
    """
    _spacer()
    click.echo(f"  {DIM(step)}  {click.style(title, bold=True)}")
    if subtitle:
        click.echo(f"       {DIM(subtitle)}")
    _rule()
    _spacer()


def _hint(shortcuts: dict[str, str]) -> None:
    """
    Keyboard hint bar — subtle, below the header, before the prompt.
    Pattern: key in cyan, description in dim, separated by spaces.
    """
    parts = [
        f"{click.style(k, fg='cyan', bold=True)} {DIM(v)}"
        for k, v in shortcuts.items()
    ]
    click.echo("  " + DIM("  ·  ").join(parts))
    _spacer()


# ─────────────────────────────────────────────────────────────────────────────
# Questionary style  (applied to the interactive widget, not the surrounding text)
# ─────────────────────────────────────────────────────────────────────────────

def _qstyle():
    from questionary import Style
    return Style([
        ("separator",          "fg:#444444"),
        ("pointer",            "fg:#00aaff bold"),
        ("highlighted",        "fg:#ffffff bg:#1a2035 bold"),
        ("checkbox-selected",  "fg:#00cc66"),
        ("selected",           "fg:#00cc66"),
        ("checkbox",           "fg:#555555"),
        ("disabled",           "fg:#cc8800 italic"),
        ("instruction",        "fg:#333333"),       # hidden — we print hints ourselves
        ("question",           "fg:#888888"),
        ("answer",             "fg:#00cc66 bold"),
    ])


# ─────────────────────────────────────────────────────────────────────────────
# Data helpers
# ─────────────────────────────────────────────────────────────────────────────

def _missing(scan: ProjectScan) -> int:
    return sum(1 for p in scan.referenced_paths if not Path(p).exists())


def _nfiles(scan: ProjectScan) -> int:
    return 1 + len(scan.referenced_paths) + len(scan.final_files)


def _file_label(path_str: str, project_dir: Path) -> str:
    """Plain-text filename + context hint.  No ANSI codes — questionary renders titles literally."""
    src = Path(path_str)
    try:
        rel  = src.relative_to(project_dir)
        hint = _trunc("/".join(rel.parts[:-1]), _MAX_PATH) if len(rel.parts) > 2 else ""
    except ValueError:
        hint = "external"
    name = _trunc(src.name, _MAX_NAME)
    return f"{name:<{_MAX_NAME}}  {hint}" if hint else name


# ─────────────────────────────────────────────────────────────────────────────
# Screen 1 — project list
# ─────────────────────────────────────────────────────────────────────────────

def _screen_projects(active: list[ProjectScan]) -> list[ProjectScan] | None:
    import questionary

    _step_header(
        "1 / 2",
        "Select projects",
        "All projects are pre-selected — deselect any you want to skip",
    )
    _hint({
        "Space": "toggle",
        "A":     "select / deselect all",
        "Enter": "confirm and continue",
        "Ctrl+C":"cancel",
    })

    choices = []
    for scan in active:
        n       = _nfiles(scan)
        missing = _missing(scan)
        name    = _trunc(scan.project_name, 40)
        stats   = f"{n} files"
        if missing:
            stats += f"   ⚠ {missing} missing"
        choices.append(questionary.Choice(
            title=f"  {name:<42}  {stats}",
            value=scan,
            checked=True,
        ))

    return questionary.checkbox(
        "Projects:",
        choices=choices,
        style=_qstyle(),
        instruction=" ",
    ).ask()


# ─────────────────────────────────────────────────────────────────────────────
# Screen 1.5 — collect-all vs review
# ─────────────────────────────────────────────────────────────────────────────

def _screen_mode(selected: list[ProjectScan]) -> str | None:
    """Returns 'all' | 'review' | None if cancelled."""
    import questionary

    total   = sum(_nfiles(s)   for s in selected)
    missing = sum(_missing(s)  for s in selected)
    n       = len(selected)

    _spacer()
    # Confirmation line — green checkmark, counts
    check_part = f"{OK}  {click.style(str(n), bold=True)} project(s) selected"
    file_part  = f"{click.style(str(total), bold=True)} files"
    miss_part  = f"  {WARN} {click.style(str(missing) + ' missing', fg='yellow')}" if missing else ""
    click.echo(f"  {check_part}  {DIM('·')}  {file_part}{miss_part}")

    _step_header(
        "2 / 2",
        "How would you like to proceed?",
    )
    _hint({
        "↑ ↓":   "move",
        "Enter":  "confirm",
        "Ctrl+C": "cancel",
    })

    return questionary.select(
        "Action:",
        choices=[
            questionary.Choice(
                title=f"  ⚡  Collect everything now     {total} files, no review",
                value="all",
            ),
            questionary.Choice(
                title=f"  🔍  Review files one by one    go through each project",
                value="review",
            ),
        ],
        style=_qstyle(),
        instruction=" ",
    ).ask()


# ─────────────────────────────────────────────────────────────────────────────
# Screen 2+  — per-project file review
# ─────────────────────────────────────────────────────────────────────────────

def _screen_files(scan: ProjectScan, index: int, total: int) -> set[str] | None:
    import questionary

    missing = _missing(scan)
    n       = _nfiles(scan)

    subtitle = f"{n} files" + (f"   ·   ⚠ {missing} not found on disk" if missing else "")

    _step_header(
        f"Project  {index} / {total}",
        scan.project_name,
        subtitle,
    )
    _hint({
        "Space":  "toggle",
        "Enter":  "accept all and continue",
        "Ctrl+C": "cancel",
    })

    choices = []

    if scan.prproj:
        choices.append(questionary.Choice(
            title=f"  [proj]    {_trunc(scan.prproj.name, _MAX_NAME)}",
            value=str(scan.prproj),
            checked=True,
        ))

    for path_str in scan.referenced_paths:
        exists = Path(path_str).exists()
        label  = _file_label(path_str, scan.project_dir)
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

    for f in scan.final_files:
        rel   = f.relative_to(scan.project_dir / "Final")
        hint  = str(rel.parent) if rel.parent != Path(".") else ""
        label = f"{_trunc(f.name, _MAX_NAME):<{_MAX_NAME}}  {hint}" if hint else _trunc(f.name, _MAX_NAME)
        choices.append(questionary.Choice(
            title=f"  [final]   {label}",
            value=str(f),
            checked=True,
        ))

    result = questionary.checkbox(
        "Files:",
        choices=choices,
        style=_qstyle(),
        instruction=" ",
    ).ask()

    return set(result) if result is not None else None


# ─────────────────────────────────────────────────────────────────────────────
# Pre-collection summary
# ─────────────────────────────────────────────────────────────────────────────

def _print_ready(selected: list[ProjectScan], chosen: set[str]) -> None:
    _spacer()
    _rule()
    click.echo(f"  {click.style('Ready to collect', bold=True)}")
    _rule()
    _spacer()

    total_chosen  = 0
    total_missing = 0
    total_skipped = 0

    for scan in selected:
        all_paths = (
            ([str(scan.prproj)] if scan.prproj else [])
            + scan.referenced_paths
            + [str(f) for f in scan.final_files]
        )
        n_chosen  = sum(1 for p in all_paths if p in chosen)
        n_missing = _missing(scan)
        n_skipped = len(all_paths) - n_chosen - n_missing

        total_chosen  += n_chosen
        total_missing += n_missing
        total_skipped += n_skipped

        parts = [click.style(f"{n_chosen} files", fg="green")]
        if n_missing:
            parts.append(click.style(f"{n_missing} missing", fg="yellow"))
        if n_skipped:
            parts.append(DIM(f"{n_skipped} skipped"))

        click.echo(
            f"  {OK}  {_trunc(scan.project_name, 38):<40}  "
            + DIM("·  ") + "  ".join(parts)
        )

    _spacer()
    summary = f"  {click.style(str(total_chosen), fg='green', bold=True)} files will be collected"
    if total_skipped:
        summary += f"   {DIM(str(total_skipped) + ' manually skipped')}"
    if total_missing:
        summary += f"   {click.style(str(total_missing) + ' missing on disk', fg='yellow')}"
    click.echo(summary)
    _spacer()


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def interactive_select(scans: list[ProjectScan]) -> set[str] | None:
    """
    Three-screen interactive selection flow:
      Screen 1   — project list with stats (short, one row per project)
      Screen 1.5 — ⚡ collect all now  OR  🔍 review files
      Screen 2+  — per-project file review (one questionary per project)

    Returns the flat set of chosen file paths, or None if cancelled.
    """
    active        = [s for s in scans if s.status in ("ok", "pm_exists") and s.prproj]
    total_files   = sum(_nfiles(s)   for s in active)
    total_missing = sum(_missing(s)  for s in active)

    if not active:
        click.echo(click.style("  No projects found.", fg="yellow"))
        return None

    # Overview banner
    _spacer()
    click.echo(
        f"  {click.style(str(len(active)), fg='cyan', bold=True)} projects  "
        f"{DIM('·')}  "
        f"{click.style(str(total_files), bold=True)} files total"
        + (f"  {DIM('·')}  {click.style(str(total_missing) + ' missing', fg='yellow')}" if total_missing else "")
    )

    # ── Screen 1: project selection ───────────────────────────────────────
    selected = _screen_projects(active)
    if not selected:
        msg = "\n  Cancelled.\n" if selected is None else "\n  No projects selected.\n"
        click.echo(DIM(msg))
        return None

    # ── Screen 1.5: collect all or review ────────────────────────────────
    mode = _screen_mode(selected)
    if mode is None:
        click.echo(DIM("\n  Cancelled.\n"))
        return None

    if mode == "all":
        chosen: set[str] = set()
        for scan in selected:
            if scan.prproj:
                chosen.add(str(scan.prproj))
            for p in scan.referenced_paths:
                if Path(p).exists():
                    chosen.add(p)
            for f in scan.final_files:
                chosen.add(str(f))
        _print_ready(selected, chosen)
        return chosen

    # ── Screen 2+: per-project file review ───────────────────────────────
    chosen = set()
    for i, scan in enumerate(selected, 1):
        paths = _screen_files(scan, i, len(selected))
        if paths is None:
            click.echo(DIM("\n  Cancelled.\n"))
            return None
        chosen.update(paths)

    _print_ready(selected, chosen)
    return chosen
