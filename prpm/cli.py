"""Command-line interface for prpm."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

import click

from . import __version__
from .core import ProjectResult, ProjectScan, process_project, scan_project
from .errors import check_python_version, check_questionary, run_with_error_handling


# ---------------------------------------------------------------------------
# Terminal design constants
# ---------------------------------------------------------------------------

_LINE = click.style('  ' + '─' * 50, fg='bright_black')

BANNER = (
    "\n"
    + click.style("  prpm", fg="cyan", bold=True)
    + click.style("  —  Premiere Project Manager  ", fg="white")
    + click.style(f"v{__version__}", fg="bright_black")
    + "\n"
    + _LINE
    + "\n"
    + click.style("  Collect  ·  Archive  ·  Share", fg="bright_black")
    + "\n"
)

DIV   = _LINE
TICK  = click.style('✓', fg='green')
CROSS = click.style('✗', fg='red')
WARN  = click.style('⚠', fg='yellow')
SKIP  = click.style('○', fg='bright_black')
ARROW = click.style('→', fg='bright_black')
DOT   = click.style('·', fg='bright_black')


def _h(text: str) -> str:
    """Bold white heading."""
    return click.style(text, bold=True)


def _dim(text: str) -> str:
    return click.style(text, fg='bright_black')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_projects(base_dir: Path) -> list[Path]:
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


def _make_event_handler(verbose: bool) -> tuple[list[str], callable]:
    lines: list[str] = []
    file_log = logging.getLogger("prpm")

    def on_event(level: str, msg: str) -> None:
        lines.append(f"[{level.upper():12}] {msg}")
        file_log.info(f"[{level}] {msg}")

        if not verbose:
            if level == "missing":
                click.echo(f"   {WARN} {click.style('Missing:', fg='yellow')} {Path(msg).name}")
            elif level == "error":
                click.echo(f"   {CROSS} {msg}")
            return

        if level == "copied":
            click.echo(f"   {TICK} {msg}")
        elif level == "would_copy":
            click.echo(f"   {ARROW} {Path(msg).name}")
        elif level == "skipped":
            click.echo(f"   {SKIP} Skipped: {msg}")
        elif level == "missing":
            click.echo(f"   {WARN} {click.style('Missing:', fg='yellow')} {Path(msg).name}")
        elif level == "error":
            click.echo(f"   {CROSS} {msg}")
        elif level == "warn":
            click.echo(f"   {WARN} {msg}")
        elif level == "info":
            click.echo(f"   {DOT} {msg}")

    return lines, on_event


def _print_project_outcome(result: ProjectResult, dry_run: bool) -> None:
    if result.status == "skipped_no_prproj":
        click.echo(f"  {SKIP} {_dim('No .prproj found — skipped')}")
        return
    if result.status == "skipped_exists":
        click.echo(f"  {SKIP} {_dim('Already collected — skipped')}  "
                   f"{_dim('(use --overwrite to redo)')}")
        return
    if result.status == "error":
        click.echo(f"  {CROSS} {click.style('Could not process this project', fg='red')}")
        return

    verb = "Would collect" if dry_run else "Collected"
    parts = [click.style(f"{result.total_copied} file(s)", fg="green", bold=True)]
    if result.missing_on_disk:
        parts.append(click.style(f"{len(result.missing_on_disk)} missing", fg="yellow", bold=True))
    if result.copy_failed:
        parts.append(click.style(f"{len(result.copy_failed)} failed", fg="red", bold=True))

    click.echo(f"  {TICK} {verb}: {', '.join(parts)}")

    if result.pm_dir and not dry_run:
        try:
            rel = result.pm_dir.relative_to(result.pm_dir.parent.parent)
        except ValueError:
            rel = result.pm_dir
        click.echo(f"  {ARROW} {_dim(str(rel) + '/')}")


# ---------------------------------------------------------------------------
# CLI definition
# ---------------------------------------------------------------------------

@click.group(
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"], "max_content_width": 80},
)
@click.version_option(__version__, "-V", "--version", prog_name="prpm")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """prpm — Premiere Project Manager

    Consolidates all media used in a Premiere Pro project into a single
    PM_<ProjectName> folder, making archiving and sharing easy.

    \b
    Quick start:
      cd /path/to/your/projects
      prpm run --preview      ← interactive file picker
      prpm run                ← collect everything
    """
    check_python_version()
    if ctx.invoked_subcommand is None:
        click.echo(BANNER)
        click.echo(ctx.get_help())


@cli.command()
@click.argument("project", required=False, metavar="[PROJECT]")
@click.option("--preview", "-p", is_flag=True,
              help="Open interactive file picker — toggle files on/off before collecting.")
@click.option("--overwrite", "-o", is_flag=True,
              help="Re-collect projects that already have a PM_ folder.")
@click.option("--verbose", "-v", is_flag=True,
              help="Print each file name as it is copied.")
@click.option("--dir", "-d", "base_dir", default=".", show_default=True, metavar="PATH",
              help="Folder containing your projects (default: current folder).")
def run(
    project: str | None,
    preview: bool,
    overwrite: bool,
    verbose: bool,
    base_dir: str,
) -> None:
    """Collect all media for your Premiere projects into PM_ folders.

    Pass a PROJECT name to process only that one project.

    \b
    Examples:
      prpm run                          collect all projects
      prpm run "My Video"               collect one project
      prpm run --preview                interactive file picker
      prpm run --verbose                show each file being copied
      prpm run --overwrite              redo already-collected projects
      prpm run --dir /path/to/folder    use a specific folder
    """
    def _run():
        base = Path(base_dir).resolve()
        if not base.is_dir():
            msg = f"'{base}' is not a valid folder."
            click.echo(f"\n  {CROSS} {click.style(msg, fg='red')}\n")
            sys.exit(1)

        if project:
            target = base / project
            if not target.is_dir():
                msg = f"Project '{project}' not found in {base}"
                click.echo(f"\n  {CROSS} {click.style(msg, fg='red')}\n")
                sys.exit(1)
            project_dirs = [target]
        else:
            project_dirs = _find_projects(base)

        if not project_dirs:
            click.echo(f"\n  {WARN} No project folders found in {base}\n")
            return

        # ── Header ───────────────────────────────────────────────────────
        click.echo(BANNER)

        mode_label = (
            click.style("PREVIEW", fg="yellow", bold=True)
            if preview
            else click.style("COLLECT", fg="green", bold=True)
        )
        click.echo(f"  {mode_label}  {_dim(str(base))}")
        click.echo()

        # ── Setup logging ────────────────────────────────────────────────
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = base / f"PM_log_{timestamp}.log"
        _setup_file_log(log_path)

        # ── Interactive preview ──────────────────────────────────────────
        selected_paths: set[str] | None = None

        if preview:
            if not check_questionary():
                sys.exit(1)

            from .selector import interactive_select

            click.echo(f"  {DOT} Scanning projects...", nl=False)
            scans: list[ProjectScan] = [
                scan_project(d, overwrite=overwrite) for d in project_dirs
            ]
            click.echo(f"\r  {TICK} Scanning complete.           ")
            click.echo()

            selected_paths = interactive_select(scans)
            if selected_paths is None:
                return  # user cancelled

            click.echo()
            click.echo(DIV)
            click.echo(f"  {_h('Collecting selected files...')}")
            click.echo(DIV)
            click.echo()

        # ── Collect ──────────────────────────────────────────────────────
        results: list[ProjectResult] = []

        for project_dir in project_dirs:
            click.echo(f" {click.style('📂', bold=True)}  {_h(project_dir.name)}")
            _, on_event = _make_event_handler(verbose or preview)

            result = run_with_error_handling(
                process_project,
                project_dir,
                dry_run=False,
                overwrite=overwrite,
                selected_paths=selected_paths,
                on_event=on_event,
            )
            results.append(result)
            _print_project_outcome(result, dry_run=False)
            click.echo()

        # ── Summary ──────────────────────────────────────────────────────
        processed   = [r for r in results if r.status == "ok"]
        skipped     = sum(1 for r in results if r.status != "ok")
        total_ref   = sum(r.referenced    for r in processed)
        total_copied = sum(r.total_copied for r in processed)
        total_missing = sum(len(r.missing_on_disk) for r in processed)
        total_failed  = sum(len(r.copy_failed)      for r in processed)
        problems = [r for r in processed if r.has_issues]

        click.echo(DIV)
        click.echo(f"  {_h('Results')}")
        click.echo(DIV)
        click.echo(f"  Projects processed  {_h(str(len(processed)))}")
        if skipped:
            click.echo(f"  Projects skipped    {skipped}")
        click.echo(f"  Files referenced    {total_ref}")
        click.echo(
            f"  Files collected     "
            f"{click.style(str(total_copied), fg='green', bold=True)}"
        )
        if total_missing:
            click.echo(
                f"  {click.style('Missing on disk', fg='yellow')}    "
                f"{click.style(str(total_missing), fg='yellow', bold=True)}"
            )
        if total_failed:
            click.echo(
                f"  {click.style('Copy failures', fg='red')}      "
                f"{click.style(str(total_failed), fg='red', bold=True)}"
            )

        if problems:
            click.echo()
            click.echo(f"  {click.style('Projects with missing files:', fg='yellow')}")
            for r in problems:
                parts = []
                if r.missing_on_disk:
                    parts.append(f"{len(r.missing_on_disk)} missing")
                if r.copy_failed:
                    parts.append(f"{len(r.copy_failed)} failed")
                click.echo(f"    {DOT} {r.project_name}  {_dim('(' + ', '.join(parts) + ')')}")
            click.echo()
            click.echo(
                f"  {_dim('Tip: missing files may be on an unplugged drive or unsynced cloud folder.')}"
            )

        click.echo()
        click.echo(f"  {_dim('Log')}  {ARROW}  {_dim(log_path.name)}")
        click.echo()

    run_with_error_handling(_run)
