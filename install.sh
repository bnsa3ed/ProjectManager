#!/usr/bin/env bash
# prpm installer — installs system-wide using pipx
# Usage: curl -fsSL https://raw.githubusercontent.com/bnsa3ed/ProjectManager/main/install.sh | bash

set -euo pipefail

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

# ── Install pipx if missing ──────────────────────────────────────────────────
if ! command -v pipx &>/dev/null; then
    echo "  ${YELLOW}·${RESET}  Installing pipx..."

    if command -v brew &>/dev/null; then
        # Homebrew Python blocks pip system-wide — use brew to install pipx instead
        brew install pipx --quiet
    else
        python3 -m pip install --user pipx --quiet 2>/dev/null \
            || python3 -m pip install --user pipx --quiet --break-system-packages
    fi

    # Ensure pipx's bin dir is on PATH and add it to shell profile
    python3 -m pipx ensurepath --quiet 2>/dev/null || true

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

# ── Install or upgrade prpm ───────────────────────────────────────────────────
echo "  ${YELLOW}·${RESET}  Installing prpm..."

if pipx list 2>/dev/null | grep -q "prpm"; then
    pipx upgrade prpm --quiet
    ACTION="upgraded"
else
    pipx install prpm --quiet
    ACTION="installed"
fi

echo "  ${GREEN}✓${RESET}  prpm $ACTION successfully"
echo ""
echo "${BOLD}  Get started:${RESET}"
echo ""
echo "     cd \"/path/to/your/projects\""
echo "     prpm run --preview"
echo ""
echo "  ${YELLOW}Note:${RESET} If 'prpm' is not found, close and reopen your terminal first."
echo ""
