#!/usr/bin/env python3
"""Post-install configuration for AI agent devcontainer.

Runs on container creation to set up:
- Claude Code settings (bypassPermissions mode)
- Pi path restrictions (protect sandbox configuration)
- Tmux configuration (200k history, mouse support)
- Directory ownership fixes for mounted volumes
"""

import contextlib
import json
import os
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
    print(f"[post_install] Claude settings configured: {settings_file}", file=sys.stderr)


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


def setup_zsh_config():
    """Set up zsh configuration with XDG fallback.

    Checks if ~/.config/zsh (mounted from host) has content.
    If yes, use it as ZDOTDIR. If no, ensure ~/.zshrc exists
    as fallback. Also ensures oh-my-zsh custom directory has
    correct ownership.
    """
    home = Path.home()
    xdg_zsh_dir = home / ".config" / "zsh"
    xdg_zshrc = xdg_zsh_dir / ".zshrc"
    home_zshrc = home / ".zshrc"
    omz_custom = home / ".oh-my-zsh" / "custom"

    # Check if host has zsh config in XDG location
    has_xdg_config = xdg_zsh_dir.exists() and any(xdg_zsh_dir.iterdir())

    if has_xdg_config:
        # Ensure .zshrc exists in XDG location (source the built-in custom config)
        if not xdg_zshrc.exists():
            # Create minimal .zshrc that sources oh-my-zsh and our custom config
            xdg_zshrc.write_text(
                '# Host zsh config\n'
                '# This file is sourced when ZDOTDIR is set to ~/.config/zsh\n\n'
                '# Source oh-my-zsh if available\n'
                'if [[ -f ~/.oh-my-zsh/oh-my-zsh.sh ]]; then\n'
                '  source ~/.oh-my-zsh/oh-my-zsh.sh\n'
                'fi\n\n'
                '# Source devcontainer custom config\n'
                '[[ -f ~/.zshrc.custom ]] && source ~/.zshrc.custom\n',
                encoding="utf-8"
            )
            print(f"[post_install] Created XDG zshrc: {xdg_zshrc}", file=sys.stderr)
        else:
            print(f"[post_install] Using host XDG zsh config: {xdg_zsh_dir}", file=sys.stderr)
    else:
        # Fallback: ensure ~/.zshrc exists (oh-my-zsh should have created it)
        # Just ensure it sources our custom config
        if home_zshrc.exists():
            content = home_zshrc.read_text(encoding="utf-8")
            if ".zshrc.custom" not in content:
                home_zshrc.write_text(
                    content + "\n# Source devcontainer custom config\n"
                    "[[ -f ~/.zshrc.custom ]] && source ~/.zshrc.custom\n",
                    encoding="utf-8"
                )
                print(f"[post_install] Updated home zshrc to source custom config", file=sys.stderr)
        else:
            # Create minimal zshrc
            home_zshrc.write_text(
                '# Minimal zshrc\n'
                '[[ -f ~/.zshrc.custom ]] && source ~/.zshrc.custom\n',
                encoding="utf-8"
            )
            print(f"[post_install] Created fallback zshrc: {home_zshrc}", file=sys.stderr)

    # Fix oh-my-zsh custom directory ownership
    if omz_custom.exists():
        uid = os.getuid()
        gid = os.getgid()
        try:
            stat_info = omz_custom.stat()
            if stat_info.st_uid != uid:
                subprocess.run(
                    ["sudo", "chown", "-R", f"{uid}:{gid}", str(omz_custom)],
                    check=True,
                    capture_output=True,
                )
                print(f"[post_install] Fixed omz custom ownership: {omz_custom}", file=sys.stderr)
        except (PermissionError, subprocess.CalledProcessError) as e:
            print(
                f"[post_install] Warning: Could not fix omz custom ownership: {e}",
                file=sys.stderr,
            )


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
        Path.home() / ".config" / "zsh",
        Path.home() / ".oh-my-zsh" / "custom",
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
                    print(f"[post_install] Fixed ownership: {dir_path}", file=sys.stderr)
            except (PermissionError, subprocess.CalledProcessError) as e:
                print(
                    f"[post_install] Warning: Could not fix ownership of {dir_path}: {e}",
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
    print(f"[post_install] Local git config created: {local_gitconfig}", file=sys.stderr)


def main():
    """Run all post-install configuration."""
    print("[post_install] Starting post-install configuration...", file=sys.stderr)

    setup_claude_settings()
    setup_pi_settings()
    setup_zsh_config()
    setup_tmux_config()
    fix_directory_ownership()
    setup_global_gitignore()

    print("[post_install] Configuration complete!", file=sys.stderr)


if __name__ == "__main__":
    main()
