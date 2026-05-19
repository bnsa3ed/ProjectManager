"""Friendly error handling and auto-fix suggestions for prpm."""

from __future__ import annotations

import subprocess
import sys
from typing import NoReturn

import click


# ---------------------------------------------------------------------------
# Auto-fix helper
# ---------------------------------------------------------------------------

def _offer_install(package: str) -> bool:
    """Ask the user if they want to install a missing package. Returns True if installed."""
    click.echo(
        f"\n  {click.style('Missing dependency:', fg='yellow', bold=True)} "
        f"{click.style(package, bold=True)}"
    )
    click.echo(f"  This package is required and can be installed automatically.\n")

    if click.confirm(f"  Install {package!r} now?", default=True):
        click.echo(f"  Installing {package}...\n")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            click.echo(f"\n  {click.style('✓', fg='green')} {package} installed successfully.")
            click.echo("  Please re-run your command.\n")
            return True
        else:
            click.echo(f"\n  {click.style('✗', fg='red')} Installation failed.\n")
            click.echo(f"  Try running manually:\n    pip install {package}\n")
            return False
    else:
        click.echo(f"\n  To install manually:\n    pip install {package}\n")
        return False


# ---------------------------------------------------------------------------
# Per-error handlers
# ---------------------------------------------------------------------------

def handle_import_error(exc: ImportError) -> NoReturn:
    """Handle a missing Python package with an install offer."""
    name = exc.name or str(exc)
    package = name.split(".")[0]

    click.echo()
    click.echo(click.style("  ERROR  ", fg="red", bold=True) + "A required package is not installed.")
    _offer_install(package)
    sys.exit(1)


def handle_permission_error(exc: PermissionError) -> NoReturn:
    click.echo()
    click.echo(click.style("  ERROR  ", fg="red", bold=True) + "Permission denied.")
    click.echo(f"\n  {click.style('Path:', fg='bright_black')} {exc.filename}")
    click.echo()
    click.echo("  Possible fixes:")
    if sys.platform == "darwin":
        click.echo("    · Check that macOS hasn't blocked access to this folder")
        click.echo("      (System Settings → Privacy & Security → Files and Folders)")
        click.echo("    · Try running: chmod -R u+rw \"<your projects folder>\"")
    else:
        click.echo("    · Make sure you have read/write access to the folder")
        click.echo("    · Try running the command with administrator privileges")
    click.echo()
    sys.exit(1)


def handle_disk_full() -> NoReturn:
    click.echo()
    click.echo(click.style("  ERROR  ", fg="red", bold=True) + "Not enough disk space.")
    click.echo()
    click.echo("  Free up space on the destination drive and try again.")
    click.echo()
    sys.exit(1)


def handle_python_version() -> NoReturn:
    v = sys.version_info
    click.echo()
    click.echo(
        click.style("  ERROR  ", fg="red", bold=True)
        + f"Python {v.major}.{v.minor} is too old. prpm requires Python 3.9 or later."
    )
    click.echo()
    click.echo("  Download a newer version from: https://python.org/downloads")
    click.echo()
    sys.exit(1)


def handle_unexpected(exc: Exception) -> NoReturn:
    click.echo()
    click.echo(click.style("  UNEXPECTED ERROR  ", fg="red", bold=True))
    click.echo(f"\n  {type(exc).__name__}: {exc}")
    click.echo()
    click.echo("  Please report this at:")
    click.echo("  https://github.com/bnsa3ed/ProjectManager/issues")
    click.echo()
    sys.exit(1)


# ---------------------------------------------------------------------------
# Entry guard
# ---------------------------------------------------------------------------

def check_python_version() -> None:
    if sys.version_info < (3, 9):
        handle_python_version()


def check_questionary() -> bool:
    """
    Verify questionary is importable.
    If not, offer to install it and return False (caller should abort or restart).
    Returns True if available.
    """
    try:
        import questionary  # noqa: F401
        return True
    except ImportError:
        return _offer_install("questionary")


def run_with_error_handling(func, *args, **kwargs):
    """Call func(*args, **kwargs), translating exceptions into friendly messages."""
    try:
        return func(*args, **kwargs)
    except ImportError as exc:
        handle_import_error(exc)
    except PermissionError as exc:
        handle_permission_error(exc)
    except OSError as exc:
        import errno
        if exc.errno == errno.ENOSPC:
            handle_disk_full()
        raise
    except SystemExit:
        raise
    except Exception as exc:
        handle_unexpected(exc)
