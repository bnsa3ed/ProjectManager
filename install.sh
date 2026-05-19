#!/usr/bin/env bash
# prpm installer — installs system-wide using pipx
# Usage: curl -fsSL https://raw.githubusercontent.com/bnsa3ed/ProjectManager/main/install.sh | bash

set -euo pipefail

# Prevent Homebrew from doing git-based auto-updates that read from stdin,
# which would consume the remaining bytes of the curl | bash pipe.
export HOMEBREW_NO_AUTO_UPDATE=1
export HOMEBREW_NO_INSTALL_CLEANUP=1
export HOMEBREW_NO_ENV_HINTS=1

BOLD=$(tput bold   2>/dev/null || printf '')
RESET=$(tput sgr0  2>/dev/null || printf '')
GREEN=$(tput setaf 2 2>/dev/null || printf '')
YELLOW=$(tput setaf 3 2>/dev/null || printf '')
RED=$(tput setaf 1 2>/dev/null || printf '')
CYAN=$(tput setaf 6 2>/dev/null || printf '')

echo ""
echo "${CYAN}${BOLD}  prpm — Premiere Project Manager${RESET}"
echo "${CYAN}  ─────────────────────────────────${RESET}"
echo ""

# ── Check Python ────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "${RED}  ✗  Python 3 not found.${RESET}"
    echo ""
    echo "     Download Python 3.9 or later from:"
    echo "     https://python.org/downloads"
    echo ""
    exit 1
fi

PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
PY_VER="$PY_MAJOR.$PY_MINOR"

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]; }; then
    echo "${RED}  ✗  Python $PY_VER found, but Python 3.9 or later is required.${RESET}"
    echo ""
    echo "     Download a newer version from: https://python.org/downloads"
    echo ""
    exit 1
fi

echo "  ${GREEN}✓${RESET}  Python $PY_VER"

# ── Find a working Python for pipx (some pre-release versions are broken) ───
# pipx/uv require platform.mac_ver() to return a value — Python 3.14 pre-releases fail this.
PIPX_PYTHON=""
if python3 -c "import platform; v=platform.mac_ver()[0]; assert v, 'empty'" 2>/dev/null; then
    PIPX_PYTHON=$(which python3)
else
    echo "  ${YELLOW}·${RESET}  Python $PY_VER has a known issue on this system — looking for a stable version..."
    for try_ver in 3.13 3.12 3.11 3.10 3.9; do
        try_bin="python$try_ver"
        # Also check Homebrew locations
        brew_bin="/opt/homebrew/opt/python@$try_ver/bin/python$try_ver"
        for candidate in "$try_bin" "$brew_bin"; do
            if command -v "$candidate" &>/dev/null 2>&1; then
                if "$candidate" -c "import platform; v=platform.mac_ver()[0]; assert v" 2>/dev/null; then
                    PIPX_PYTHON=$(command -v "$candidate")
                    found_ver=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
                    echo "  ${GREEN}✓${RESET}  Using Python $found_ver for installation"
                    break 2
                fi
            fi
        done
    done
    if [ -z "$PIPX_PYTHON" ]; then
        echo "${RED}  ✗  Could not find a working Python version (3.9–3.13).${RESET}"
        echo ""
        echo "     Install a stable version with:"
        echo "     brew install python@3.13"
        echo ""
        echo "     Then re-run the installer."
        echo ""
        exit 1
    fi
fi

# ── Install pipx if missing ──────────────────────────────────────────────────
if ! command -v pipx &>/dev/null; then
    echo "  ${YELLOW}·${RESET}  Installing pipx..."

    if command -v brew &>/dev/null; then
        # Homebrew Python blocks pip system-wide — use brew to install pipx instead
        brew install pipx --quiet </dev/null
    else
        python3 -m pip install --user pipx --quiet 2>/dev/null \
            || python3 -m pip install --user pipx --quiet --break-system-packages
    fi

    # Add common locations to PATH for this session
    export PATH="$PATH:$HOME/.local/bin"
    export PATH="$PATH:/opt/homebrew/bin"
    export PATH="$PATH:$HOME/Library/Python/$PY_VER/bin"
    export PATH="$PATH:$HOME/Library/Python/$PY_MAJOR/bin"
fi

if ! command -v pipx &>/dev/null; then
    echo "${RED}  ✗  Could not install pipx automatically.${RESET}"
    echo ""
    if command -v brew &>/dev/null; then
        echo "  Run this and try again:"
        echo ""
        echo "     brew install pipx"
        echo "     pipx install prpm"
    else
        echo "  Run this and try again:"
        echo ""
        echo "     python3 -m pip install --user pipx"
        echo "     pipx install prpm"
    fi
    echo ""
    exit 1
fi

echo "  ${GREEN}✓${RESET}  pipx ready"

# ── Always ensure pipx's bin dir is in PATH ──────────────────────────────────
# This is idempotent — safe to run even if already configured.
# It adds ~/.local/bin to the shell profile so future sessions find prpm.
pipx ensurepath --quiet </dev/null 2>/dev/null || true
# Also make it available in this session immediately.
PIPX_BIN_DIR="$(pipx environment --value PIPX_BIN_DIR 2>/dev/null || echo "$HOME/.local/bin")"
export PATH="$PATH:$PIPX_BIN_DIR"

# ── Install or upgrade prpm ───────────────────────────────────────────────────
echo "  ${YELLOW}·${RESET}  Installing prpm..."

PIPX_PYTHON_FLAG=""
[ -n "$PIPX_PYTHON" ] && PIPX_PYTHON_FLAG="--python $PIPX_PYTHON"

REPO="git+https://github.com/bnsa3ed/ProjectManager.git"

if pipx list 2>/dev/null | grep -q "prpm"; then
    # Uninstall first — `pipx install --force` silently ignores --python,
    # which causes uv to fail when the venv already exists.
    pipx uninstall prpm --quiet </dev/null 2>/dev/null || true
    ACTION="upgraded"
else
    ACTION="installed"
fi

# shellcheck disable=SC2086
pipx install "$REPO" $PIPX_PYTHON_FLAG --quiet </dev/null

echo "  ${GREEN}✓${RESET}  prpm $ACTION successfully"
echo ""
echo "${BOLD}  Get started:${RESET}"
echo ""
echo "     cd \"/path/to/your/projects\""
echo "     prpm run --preview"
echo ""

# PATH changes inside a curl|bash subshell never reach the parent terminal.
# Print the concrete export command so the user can paste it once.
echo "  ${YELLOW}⚠${RESET}  Run this in your terminal to activate prpm right now:"
echo ""
echo "     ${BOLD}export PATH=\"\$PATH:${PIPX_BIN_DIR}\"${RESET}"
echo ""
echo "  prpm will work automatically in all future terminal windows."
echo ""
