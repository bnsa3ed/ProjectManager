"""Command-line interface for prpm."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

import click

from . import __version__
from .core import ProjectResult, process_project


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_projects(base_dir: Path) -> list[Path]:
    """Return all subdirectories that are not hidden and not PM_ folders."""
    return sorted(
        d for d in base_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".") and not d.name.startswith("PM_")
    )


def _setup_file_log(log_path: Path) -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.FileHandler(log_path, encoding="utf-8")],
    )


def _make_event_handler(verbose: bool) -> tuple[list, callable]:
    """Return (log_lines list, on_event callback) for a single project."""
    lines: list[str] = []
    file_log = logging.getLogger("prpm")

    def on_event(level: str, msg: str) -> None:
        lines.append(f"[{level.upper():12}] {msg}")
        file_log.info(f"[{level}] {msg}")

        if not verbose:
            # In compact mode only show warnings/errors inline
            if level == "missing":
                name = Path(msg).name
                click.echo(f"    {click.style('⚠ Missing:', fg='yellow')} {name}")
            elif level == "error":
                click.echo(f"    {click.style('✗', fg='red')} {msg}")
            return

        # Verbose: print every event
        if level == "copied":
            click.echo(f"    {click.style('✓', fg='green')} {msg}")
        elif level == "would_copy":
            click.echo(f"    {click.style('→', fg='cyan')} {Path(msg).name}")
        elif level == "missing":
            click.echo(f"    {click.style('⚠ Missing:', fg='yellow')} {Path(msg).name}")
        elif level == "error":
            click.echo(f"    {click.style('✗', fg='red')} {msg}")
        elif level == "warn":
            click.echo(f"    {click.style('⚠', fg='yellow')} {msg}")
        elif level == "info":
            click.echo(f"    {click.style('·', fg='bright_black')} {msg}")

    return lines, on_event


def _print_project_outcome(result: ProjectResult, dry_run: bool) -> None:
    """Print the one-line outcome for a project after processing."""
    status = result.status

    if status == "skipped_no_prproj":
        click.echo(f"  {click.style('○', fg='bright_black')} No .prproj found — skipped")
        return
    if status == "skipped_exists":
        click.echo(f"  {click.style('○', fg='bright_black')} Already collected — skipped  "
                   f"{click.style('(use --overwrite to redo)', fg='bright_black')}")
        return
    if status == "error":
        click.echo(f"  {click.style('✗ Error — could not process this project', fg='red')}")
        return

    verb = "Would collect" if dry_run else "Collected"
    parts = [click.style(f"{result.total_copied} file(s)", fg="green", bold=True)]
    if result.missing_on_disk:
        parts.append(click.style(f"{len(result.missing_on_disk)} missing", fg="yellow", bold=True))
    if result.copy_failed:
        parts.append(click.style(f"{len(result.copy_failed)} failed", fg="red", bold=True))

    click.echo(f"  {click.style('✓', fg='green')} {verb}: {', '.join(parts)}")

    if result.pm_dir and not dry_run:
        rel = result.pm_dir.relative_to(result.pm_dir.parent.parent) \
              if result.pm_dir.parent.parent.exists() else result.pm_dir
        click.echo(f"  {click.style('→', fg='bright_black')} {rel}/")


# ---------------------------------------------------------------------------
# CLI definition
# ---------------------------------------------------------------------------

@click.group(invoke_without_command=True, context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, "-V", "--version", prog_name="prpm")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """prpm — Premiere Project Manager

    Consolidates all media used in a Premiere Pro project into a single
    PM_<ProjectName> folder, making archiving and sharing easy.

    \b
    Quick start:
      cd /path/to/your/projects
      prpm run
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command()
@click.argument("project", required=False, metavar="[PROJECT]")
@click.option(
    "--preview", "-p",
    is_flag=True,
    help="Show what would be collected without copying anything.",
)
@click.option(
    "--overwrite", "-o",
    is_flag=True,
    help="Re-collect projects that already have a PM_ folder.",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Print each file as it is copied.",
)
@click.option(
    "--dir", "-d", "base_dir",
    default=".",
    show_default=True,
    metavar="PATH",
    help="Folder that contains your projects. Defaults to the current folder.",
)
def run(
    project: str | None,
    preview: bool,
    overwrite: bool,
    verbose: bool,
    base_dir: str,
) -> None:
    """Collect all media for your Premiere projects into PM_ folders.

    Optionally pass a PROJECT name to process only that one project.

    \b
    Examples:
      prpm run                          collect all projects in current folder
      prpm run "My Video"               collect one project by name
      prpm run --preview                preview without copying anything
      prpm run --verbose                show each file being copied
      prpm run --overwrite              redo already-collected projects
      prpm run --dir /path/to/projects  use a specific folder
    """
    base = Path(base_dir).resolve()
    if not base.is_dir():
        click.echo(click.style(f"Error: '{base}' is not a valid folder.", fg="red"), err=True)
        sys.exit(1)

    # Determine which projects to process
    if project:
        target = base / project
        if not target.is_dir():
            click.echo(click.style(f"Error: Project '{project}' not found in {base}", fg="red"), err=True)
            sys.exit(1)
        project_dirs = [target]
    else:
        project_dirs = _find_projects(base)

    if not project_dirs:
        click.echo("No project folders found.")
        return

    # Set up logging
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = base / f"PM_log_{timestamp}.log"
    _setup_file_log(log_path)

    # Header
    mode_label = (
        click.style("PREVIEW", fg="yellow", bold=True)
        if preview
        else click.style("COLLECT", fg="green", bold=True)
    )
    click.echo()
    click.echo(click.style("━" * 52, fg="bright_black"))
    click.echo(f"  prpm v{__version__}  ·  {mode_label}")
    click.echo(f"  {base}")
    click.echo(click.style("━" * 52, fg="bright_black"))
    click.echo()

    # Process each project
    results: list[ProjectResult] = []

    for project_dir in project_dirs:
        click.echo(click.style(f"📂  {project_dir.name}", bold=True))
        _, on_event = _make_event_handler(verbose)

        result = process_project(
            project_dir,
            dry_run=preview,
            overwrite=overwrite,
            on_event=on_event,
        )
        results.append(result)
        _print_project_outcome(result, preview)
        click.echo()

    # Grand summary
    processed = [r for r in results if r.status == "ok"]
    skipped   = sum(1 for r in results if r.status != "ok")
    total_ref    = sum(r.referenced    for r in processed)
    total_copied = sum(r.total_copied  for r in processed)
    total_missing = sum(len(r.missing_on_disk) for r in processed)
    total_failed  = sum(len(r.copy_failed)      for r in processed)
    problems = [r for r in processed if r.has_issues]

    click.echo(click.style("━" * 52, fg="bright_black"))
    click.echo(click.style("  Results", bold=True))
    click.echo(click.style("━" * 52, fg="bright_black"))
    click.echo(f"  Projects processed  {click.style(str(len(processed)), bold=True)}")
    if skipped:
        click.echo(f"  Projects skipped    {skipped}")
    click.echo(f"  Files referenced    {total_ref}")
    click.echo(
        f"  Files {'previewed' if preview else 'copied'}     "
        f"{click.style(str(total_copied), fg='green', bold=True)}"
    )
    if total_missing:
        click.echo(
            f"  Missing on disk     "
            f"{click.style(str(total_missing), fg='yellow', bold=True)}"
        )
    if total_failed:
        click.echo(
            f"  Copy failures       "
            f"{click.style(str(total_failed), fg='red', bold=True)}"
        )

    if problems:
        click.echo()
        click.echo(click.style("  Projects with missing files:", fg="yellow"))
        for r in problems:
            missing_n = len(r.missing_on_disk)
            failed_n  = len(r.copy_failed)
            parts = []
            if missing_n:
                parts.append(f"{missing_n} missing")
            if failed_n:
                parts.append(f"{failed_n} failed")
            click.echo(f"    · {r.project_name}  ({', '.join(parts)})")
        click.echo()
        click.echo(
            click.style("  Tip: ", fg="bright_black") +
            "missing files were not found on disk — they may have been "
            "moved, deleted, or are on a drive that is not currently connected."
        )

    click.echo()
    click.echo(f"  Full log → {log_path.name}")
    click.echo()
