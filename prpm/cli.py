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


# ─────────────────────────────────────────────────────────────────────────────
# Design tokens  (research: semantic symbols, dim for secondary, no borders)
# ─────────────────────────────────────────────────────────────────────────────

def _c(text: str, **kw) -> str:
    return click.style(text, **kw)

OK    = _c("✓", fg="green",        bold=True)
FAIL  = _c("✗", fg="red",          bold=True)
WARN  = _c("⚠", fg="yellow",       bold=True)
SKIP  = _c("○", fg="bright_black")
ARROW = _c("›", fg="cyan",         bold=True)
DOT   = _c("·", fg="bright_black")

def _dim(t: str)  -> str: return _c(t, fg="bright_black")
def _bold(t: str) -> str: return _c(t, bold=True)
def _green(t: str)-> str: return _c(t, fg="green",  bold=True)
def _yellow(t: str)->str: return _c(t, fg="yellow", bold=True)
def _red(t: str)  -> str: return _c(t, fg="red",    bold=True)
def _cyan(t: str) -> str: return _c(t, fg="cyan",   bold=True)

_RULE = _dim("  " + "─" * 54)

BANNER = (
    "\n"
    + _c("  prpm", fg="cyan", bold=True)
    + _c("  —  Premiere Project Manager  ", fg="white")
    + _dim(f"v{__version__}")
    + "\n"
    + _dim("  " + "─" * 54)
    + "\n"
    + _dim("  Collect  ·  Archive  ·  Share")
    + "\n"
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

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
            # Compact mode: only surface warnings and errors
            if level == "missing":
                click.echo(f"     {WARN} {_yellow('Missing:')} {Path(msg).name}")
            elif level == "error":
                click.echo(f"     {FAIL} {msg}")
            return

        # Verbose: one line per file
        if level == "copied":
            click.echo(f"     {OK} {msg}")
        elif level == "skipped":
            click.echo(f"     {SKIP} {_dim('skipped:')} {msg}")
        elif level == "missing":
            click.echo(f"     {WARN} {_yellow('missing:')} {Path(msg).name}")
        elif level == "error":
            click.echo(f"     {FAIL} {msg}")
        elif level in ("warn",):
            click.echo(f"     {WARN} {msg}")
        elif level == "info":
            click.echo(f"     {DOT} {_dim(msg)}")

    return lines, on_event


def _print_project_outcome(result: ProjectResult) -> None:
    """One or two lines summarising the outcome for a single project."""
    if result.status == "skipped_no_prproj":
        click.echo(f"  {SKIP}  {_dim('No .prproj found — skipped')}")
        return
    if result.status == "skipped_exists":
        click.echo(f"  {SKIP}  {_dim('Already collected')}  {_dim('(use --overwrite to redo)')}")
        return
    if result.status == "error":
        click.echo(f"  {FAIL}  {_red('Could not process this project')}")
        return

    # Build status parts
    parts: list[str] = [_green(f"{result.total_copied} files collected")]
    if result.missing_on_disk:
        parts.append(_yellow(f"{len(result.missing_on_disk)} missing"))
    if result.copy_failed:
        parts.append(_red(f"{len(result.copy_failed)} failed"))

    click.echo(f"  {OK}  " + f"  {DOT}  ".join(parts))

    # Output path on second line
    if result.pm_dir:
        try:
            rel = result.pm_dir.relative_to(result.pm_dir.parent.parent)
        except ValueError:
            rel = result.pm_dir
        click.echo(f"     {ARROW}  {_dim(str(rel) + '/')}")


# ─────────────────────────────────────────────────────────────────────────────
# CLI definition
# ─────────────────────────────────────────────────────────────────────────────

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
      prpm run --preview      ← interactive picker + collect
      prpm run                ← collect everything immediately
    """
    check_python_version()
    if ctx.invoked_subcommand is None:
        click.echo(BANNER)
        click.echo(ctx.get_help())


@cli.command()
@click.argument("project", required=False, metavar="[PROJECT]")
@click.option("--preview", "-p", is_flag=True,
              help="Interactive picker: review projects and files before collecting.")
@click.option("--overwrite", "-o", is_flag=True,
              help="Re-collect projects that already have a PM_ folder.")
@click.option("--verbose", "-v", is_flag=True,
              help="Print each file name as it is copied.")
@click.option("--dir", "-d", "base_dir", default=".", show_default=True, metavar="PATH",
              help="Folder containing your projects (defaults to current folder).")
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
      prpm run --preview                interactive picker before collecting
      prpm run --verbose                show each file being copied
      prpm run --overwrite              redo already-collected projects
      prpm run --dir /path/to/folder    use a specific folder
    """
    def _run() -> None:
        base = Path(base_dir).resolve()
        if not base.is_dir():
            click.echo(f"\n  {FAIL}  {_red(str(base) + ' is not a valid folder.')}\n")
            sys.exit(1)

        if project:
            target = base / project
            if not target.is_dir():
                click.echo(f"\n  {FAIL}  {_red(f'Project not found: {project}')}\n")
                sys.exit(1)
            project_dirs = [target]
        else:
            project_dirs = _find_projects(base)

        if not project_dirs:
            click.echo(f"\n  {WARN}  No project folders found in {base}\n")
            return

        # ── Banner + context line ────────────────────────────────────────
        click.echo(BANNER)
        mode_badge = _yellow("PREVIEW") if preview else _green("COLLECT")
        click.echo(f"  {mode_badge}  {_dim(str(base))}")

        # ── File log ─────────────────────────────────────────────────────
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path  = base / f"PM_log_{timestamp}.log"
        _setup_file_log(log_path)

        # ── Interactive preview ──────────────────────────────────────────
        selected_paths: set[str] | None = None

        if preview:
            if not check_questionary():
                sys.exit(1)

            from .selector import interactive_select

            # Scan phase — shown on one line, overwritten on completion
            click.echo(f"\n  {DOT}  Scanning {len(project_dirs)} project(s)...", nl=False)
            scans: list[ProjectScan] = [
                scan_project(d, overwrite=overwrite) for d in project_dirs
            ]
            found = sum(1 for s in scans if s.status in ("ok", "pm_exists"))
            click.echo(f"\r  {OK}  {found} project(s) scanned.              ")

            selected_paths = interactive_select(scans)
            if selected_paths is None:
                return  # user cancelled

        # ── Collection header ────────────────────────────────────────────
        click.echo()
        click.echo(_RULE)
        click.echo(f"  {_bold('Collecting')}")
        click.echo(_RULE)
        click.echo()

        # ── Per-project collection ────────────────────────────────────────
        results: list[ProjectResult] = []

        for project_dir in project_dirs:
            click.echo(f"  {_cyan('❯')}  {_bold(project_dir.name)}")
            _, on_event = _make_event_handler(verbose)

            result = run_with_error_handling(
                process_project,
                project_dir,
                dry_run=False,
                overwrite=overwrite,
                selected_paths=selected_paths,
                on_event=on_event,
            )
            results.append(result)
            _print_project_outcome(result)
            click.echo()

        # ── Final summary ────────────────────────────────────────────────
        processed      = [r for r in results if r.status == "ok"]
        skipped        = sum(1 for r in results if r.status != "ok")
        total_copied   = sum(r.total_copied        for r in processed)
        total_missing  = sum(len(r.missing_on_disk) for r in processed)
        total_failed   = sum(len(r.copy_failed)     for r in processed)
        problems       = [r for r in processed if r.has_issues]

        click.echo(_RULE)
        click.echo(f"  {_bold('Done')}")
        click.echo(_RULE)
        click.echo()

        click.echo(f"  {OK}  {_green(str(total_copied))} files collected"
                   + (f"   across {_bold(str(len(processed)))} project(s)" if len(processed) > 1 else ""))
        if skipped:
            click.echo(f"  {SKIP}  {_dim(str(skipped) + ' project(s) skipped')}")
        if total_missing:
            click.echo(f"  {WARN}  {_yellow(str(total_missing) + ' files missing on disk')}")
        if total_failed:
            click.echo(f"  {FAIL}  {_red(str(total_failed) + ' files failed to copy')}")

        if problems:
            click.echo()
            click.echo(f"  {_dim('Projects with issues:')}")
            for r in problems:
                parts = []
                if r.missing_on_disk: parts.append(f"{len(r.missing_on_disk)} missing")
                if r.copy_failed:     parts.append(f"{len(r.copy_failed)} failed")
                click.echo(f"     {DOT}  {r.project_name}  {_dim('(' + ', '.join(parts) + ')')}")
            click.echo()
            click.echo(
                f"  {_dim('Tip:')} missing files may be on a drive that is not connected,\n"
                f"       or a cloud folder that is not synced."
            )

        click.echo()
        click.echo(f"  {_dim('Log saved to')}  {ARROW}  {_dim(log_path.name)}")
        click.echo()

    run_with_error_handling(_run)
