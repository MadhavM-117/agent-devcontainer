#!/usr/bin/env python3
"""Post-install configuration for AI agent devcontainer.

Runs on container creation to set up:
- Claude Code settings (bypassPermissions mode)
- Pi path restrictions (protect sandbox configuration)
- Tmux configuration (200k history, mouse support)
- Writable Neovim config import from optional host mount
- Directory ownership fixes for mounted volumes
"""

import contextlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def setup_claude_settings():
    """Configure Claude Code with bypassPermissions enabled."""
    claude_dir = Path.home() / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)

    settings_file = claude_dir / "settings.json"

    # Load existing settings or start fresh
    settings = {}
    if settings_file.exists():
        with contextlib.suppress(json.JSONDecodeError):
            settings = json.loads(settings_file.read_text())

    # Set bypassPermissions mode
    if "permissions" not in settings:
        settings["permissions"] = {}
    settings["permissions"]["defaultMode"] = "bypassPermissions"

    settings_file.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    print(
        f"[post_install] Claude settings configured: {settings_file}", file=sys.stderr
    )


def setup_pi_settings():
    """Configure pi coding agent with path restrictions to protect sandbox config."""
    pi_dir = Path.home() / ".pi" / "agent"
    pi_dir.mkdir(parents=True, exist_ok=True)

    settings_file = pi_dir / "settings.json"

    # Load existing settings or start fresh
    settings = {}
    if settings_file.exists():
        with contextlib.suppress(json.JSONDecodeError):
            settings = json.loads(settings_file.read_text())

    # Add path deny rules to prevent modification of devcontainer sandbox config
    if "permission" not in settings:
        settings["permission"] = {}
    if "deny" not in settings["permission"]:
        settings["permission"]["deny"] = []

    # Ensure .devcontainer is denied (prevents sandbox self-modification)
    deny_patterns = settings["permission"]["deny"]
    if "Read(.devcontainer/**)" not in deny_patterns:
        deny_patterns.append("Read(.devcontainer/**)")

    settings_file.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    print(f"[post_install] Pi settings configured: {settings_file}", file=sys.stderr)


def setup_tmux_config():
    """Configure tmux with 200k history, mouse support, and vi keys."""
    tmux_conf = Path.home() / ".tmux.conf"

    if tmux_conf.exists():
        print("[post_install] Tmux config exists, skipping", file=sys.stderr)
        return

    config = """\
# 200k line scrollback history
set-option -g history-limit 200000

# Enable mouse support
set -g mouse on

# Use vi keys in copy mode
setw -g mode-keys vi

# Start windows and panes at 1, not 0
set -g base-index 1
setw -g pane-base-index 1

# Renumber windows when one is closed
set -g renumber-windows on

# Faster escape time for vim
set -sg escape-time 10

# True color support
set -g default-terminal "tmux-256color"
set -ag terminal-overrides ",xterm-256color:RGB"

# Terminal features (ghostty, cursor shape in vim)
set -as terminal-features ",xterm-ghostty:RGB"
set -as terminal-features ",xterm*:RGB"
set -ga terminal-overrides ",xterm*:colors=256"
set -ga terminal-overrides '*:Ss=\\E[%p1%d q:Se=\\E[ q'

# Status bar
set -g status-style 'bg=#333333 fg=#ffffff'
set -g status-left '[#S] '
set -g status-right '%Y-%m-%d %H:%M'
"""
    tmux_conf.write_text(config, encoding="utf-8")
    print(f"[post_install] Tmux configured: {tmux_conf}", file=sys.stderr)


def fix_directory_ownership():
    """Fix ownership of mounted volumes that may have root ownership."""
    uid = os.getuid()
    gid = os.getgid()

    dirs_to_fix = [
        Path.home() / ".claude",
        Path("/commandhistory"),
        Path.home() / ".config" / "gh",
        Path.home() / ".config" / "nvim",
        Path.home() / ".config" / "nvim-host",
    ]

    for dir_path in dirs_to_fix:
        if dir_path.exists():
            try:
                # Use sudo to fix ownership if needed
                stat_info = dir_path.stat()
                if stat_info.st_uid != uid:
                    subprocess.run(
                        ["sudo", "chown", "-R", f"{uid}:{gid}", str(dir_path)],
                        check=True,
                        capture_output=True,
                    )
                    print(
                        f"[post_install] Fixed ownership: {dir_path}", file=sys.stderr
                    )
            except (PermissionError, subprocess.CalledProcessError) as e:
                print(
                    f"[post_install] Warning: Could not fix ownership of {dir_path}: {e}",
                    file=sys.stderr,
                )


def setup_nvim_config():
    """Set up writable Neovim config in container from optional host mount.

    If /home/vscode/.config/nvim-host exists (read-only host bind mount), copy it
    to ~/.config/nvim (writable in-container path). This keeps host config safe
    while allowing plugin managers to write lock/state files as needed.

    Behavior can be disabled with DEVC_DISABLE_LOCAL_NVIM=1/true/yes.
    """
    disable = os.environ.get("DEVC_DISABLE_LOCAL_NVIM", "0").lower()
    if disable in {"1", "true", "yes"}:
        print(
            "[post_install] Skipping Neovim host config import (DEVC_DISABLE_LOCAL_NVIM is set)",
            file=sys.stderr,
        )
        return

    host_nvim = Path.home() / ".config" / "nvim-host"
    container_nvim = Path.home() / ".config" / "nvim"

    if not host_nvim.exists():
        print(
            f"[post_install] No host Neovim config mount found at {host_nvim}; skipping",
            file=sys.stderr,
        )
        return

    if not host_nvim.is_dir():
        print(
            f"[post_install] Host Neovim mount is not a directory: {host_nvim}; skipping",
            file=sys.stderr,
        )
        return

    container_nvim.parent.mkdir(parents=True, exist_ok=True)

    if container_nvim.exists() and not container_nvim.is_symlink():
        shutil.rmtree(container_nvim)
    elif container_nvim.is_symlink() or container_nvim.is_file():
        container_nvim.unlink()

    shutil.copytree(host_nvim, container_nvim, symlinks=True)
    print(
        f"[post_install] Imported host Neovim config to writable path: {container_nvim}",
        file=sys.stderr,
    )


def setup_global_gitignore():
    """Set up global gitignore and local git config.

    Since ~/.gitconfig is mounted read-only from host, we create a local
    config file that includes the host config and adds container-specific
    settings like core.excludesfile and delta configuration.

    GIT_CONFIG_GLOBAL env var (set in devcontainer.json) points git to this
    local config as the "global" config.
    """
    home = Path.home()
    gitignore = home / ".gitignore_global"
    local_gitconfig = home / ".gitconfig.local"
    host_gitconfig = home / ".gitconfig"

    # Create global gitignore with common patterns
    patterns = """\
# Claude Code
.claude/

# macOS
.DS_Store
.AppleDouble
.LSOverride
._*

# Python
*.pyc
*.pyo
__pycache__/
*.egg-info/
.eggs/
*.egg
.venv/
venv/
.mypy_cache/
.ruff_cache/

# Node
node_modules/
.npm/

# Editors
*.swp
*.swo
*~
.idea/
.vscode/
*.sublime-*

# Misc
*.log
.env.local
.env.*.local
"""
    gitignore.write_text(patterns, encoding="utf-8")
    print(f"[post_install] Global gitignore created: {gitignore}", file=sys.stderr)

    # Create local git config that includes host config and sets excludesfile + delta
    # Delta config is included here so it works even if host doesn't have it configured
    local_config = f"""\
# Container-local git config
# Includes host config (mounted read-only) and adds container settings

[include]
    path = {host_gitconfig}

[core]
    excludesfile = {gitignore}
    pager = delta

[interactive]
    diffFilter = delta --color-only

[delta]
    navigate = true
    light = false
    line-numbers = true
    side-by-side = false

[merge]
    conflictstyle = diff3

[diff]
    colorMoved = default

[gpg "ssh"]
    program = /usr/bin/ssh-keygen
"""
    local_gitconfig.write_text(local_config, encoding="utf-8")
    print(
        f"[post_install] Local git config created: {local_gitconfig}", file=sys.stderr
    )


def main():
    """Run all post-install configuration."""
    print("[post_install] Starting post-install configuration...", file=sys.stderr)

    setup_claude_settings()
    setup_pi_settings()
    setup_tmux_config()
    setup_nvim_config()
    fix_directory_ownership()
    setup_global_gitignore()

    print("[post_install] Configuration complete!", file=sys.stderr)


if __name__ == "__main__":
    main()
