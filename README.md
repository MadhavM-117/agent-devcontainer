# Agent Devcontainer

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)

A sandboxed development environment for running AI coding agents without confirmation prompts, safely enabled. Built at [Trail of Bits](https://www.trailofbits.com/) for security audit workflows.

> **Currently supported:** [Claude Code](https://claude.ai/code) and [pi](https://github.com/badlogic/pi-mono)
>
> This project is designed to be extensible—additional agents can be added by following the pattern in [Dockerfile](./Dockerfile) and [post_install.py](./post_install.py). See [#contributing-a-new-agent](#contributing-a-new-agent) for details.

**Contents:** [Why Use This?](#why-use-this) • [Prerequisites](#prerequisites) • [Quick Start](#quick-start) • [Security Model](#security-model) • [Troubleshooting](#troubleshooting)

## Why Use This?

Running AI coding agents (like Claude Code with `bypassPermissions`) on your host machine is risky—they can execute any command without confirmation. This devcontainer provides **filesystem isolation** so you get the productivity benefits of unrestricted AI agents without risking your host system.

**Designed for:**

- **Security audits**: Review client code without risking your host
- **Untrusted repositories**: Explore unknown codebases safely
- **Experimental work**: Let agents modify code freely in isolation
- **Multi-repo engagements**: Work on multiple related repositories
- **Agent comparison**: Switch between agents depending on your workflow

### Currently Available Agents

The following agents are pre-installed and configured:

| Agent | Command | Description |
|-------|---------|-------------|
| **Claude Code** | `claude` (or `claude-yolo`) | Anthropic's official agent with marketplace skills. Use `claude-yolo` to run without permission prompts. |
| **pi** | `pi` | Minimal, hackable agent with extensions & TypeScript SDK. Runs without confirmation prompts by default. |

*Want to add another agent? See the [contributing guide](#development) or open an issue.*

## Prerequisites

- **Docker runtime** (one of):
  - [Docker Desktop](https://docker.com/products/docker-desktop) - ensure it's running
  - [OrbStack](https://orbstack.dev/)
  - [Colima](https://github.com/abiosoft/colima): `brew install colima docker && colima start`

- **For terminal workflows** (one-time install):

  ```bash
  npm install -g @devcontainers/cli
  git clone https://github.com/MadhavM-117/agent-devcontainer ~/.agent-devcontainer
  ~/.agent-devcontainer/install.sh self-install
  ```

<details>
<summary><strong>Optimizing Colima for Apple Silicon</strong></summary>

Colima's defaults (QEMU + sshfs) are conservative. For better performance:

```bash
# Stop and delete current VM (removes containers/images)
colima stop && colima delete

# Start with optimized settings
colima start \
  --cpu 4 \
  --memory 8 \
  --disk 100 \
  --vm-type vz \
  --vz-rosetta \
  --mount-type virtiofs
```

Adjust `--cpu` and `--memory` based on your Mac (e.g., 6/16 for Pro, 8/32 for Max).

| Option | Benefit |
|--------|---------|
| `--vm-type vz` | Apple Virtualization.framework (faster than QEMU) |
| `--mount-type virtiofs` | 5-10x faster file I/O than sshfs |
| `--vz-rosetta` | Run x86 containers via Rosetta |

Verify with `colima status` - should show "macOS Virtualization.Framework" and "virtiofs".

</details>

## Quick Start

Choose the pattern that fits your workflow:

### Pattern A: Per-Project Container (Isolated)

Each project gets its own container with independent volumes. Best for one-off reviews, untrusted repos, or when you need isolation between projects.

**Terminal:**

```bash
git clone <untrusted-repo>
cd untrusted-repo
devc .          # Installs template + starts container
devc shell      # Opens shell in container
```

**VS Code / Cursor:**

1. Install the Dev Containers extension:
   - VS Code: `ms-vscode-remote.remote-containers`
   - Cursor: `anysphere.remote-containers`

2. Set up the devcontainer (choose one):

   ```bash
   # Option A: Use devc (recommended)
   devc .

   # Option B: Clone manually
   git clone https://github.com/MadhavM-117/agent-devcontainer .devcontainer/
   ```

3. Open **your project folder** in VS Code, then:
   - Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux)
   - Type "Reopen in Container" and select **Dev Containers: Reopen in Container**

### Pattern B: Shared Workspace Container (Grouped)

A parent directory contains the devcontainer config, and you clone multiple repos inside. Shared volumes across all repos. Best for client engagements, related repositories, or ongoing work.

```bash
# Create workspace for a client engagement
mkdir -p ~/sandbox/client-name
cd ~/sandbox/client-name
devc .          # Install template + start container
devc shell      # Opens shell in container

# Inside container:
git clone <client-repo-1>
git clone <client-repo-2>
cd client-repo-1
claude          # Ready to work
```

## CLI Helper Commands

```
devc .              Install template + start container in current directory
devc up             Start the devcontainer
devc rebuild        Rebuild container (preserves persistent volumes)
devc down           Stop the container
devc shell          Open zsh shell in container
devc exec CMD       Execute command inside the container
devc upgrade        Upgrade Claude Code agent in the container
devc mount SRC DST  Add a bind mount (host → container)
devc template DIR   Copy devcontainer files to directory
devc self-install   Install devc to ~/.local/bin
```

> **Note:** The built-in `devc upgrade` currently only upgrades Claude Code. To upgrade pi or other agents, run their respective upgrade commands inside the container, or rebuild with `devc rebuild`.

## File Sharing

### VS Code / Cursor

Drag files from your host into the VS Code Explorer panel — they are copied into `/workspace/` automatically. No configuration needed.

### Terminal: `devc mount`

To make a host directory available inside the container:

```bash
devc mount ~/drop /drop           # Read-write
devc mount ~/secrets /secrets --readonly
```

This adds a bind mount to `devcontainer.json` and recreates the container. Existing mounts are preserved across `devc template` updates.

**Tip:** A shared "drop folder" is useful for passing files in without mounting your entire home directory.

> **Security note:** Avoid mounting large host directories (e.g., `$HOME`). Every mounted path is writable from inside the container unless `--readonly` is specified, which undermines the filesystem isolation this project provides.

### Neovim in the container (optional host config)

Neovim is usable in the container out of the box. When you run `devc .` or `devc template`, the helper auto-detects a host config at `~/.config/nvim` and (if present) mounts it read-only to `~/.config/nvim-host` in the container, then copies it to a writable `~/.config/nvim` during post-create.

This gives you your local Neovim setup while still allowing in-container writes (for example, plugin lock/state updates).

To disable this behavior, set:

```bash
DEVC_DISABLE_LOCAL_NVIM=1
```

before running `devc .` / `devc template`.

## Network Isolation

By default, containers have full outbound network access. For stricter security, use iptables to restrict network access.

### When to Enable Network Isolation

- Reviewing code that may contain malicious dependencies
- Auditing software with telemetry or phone-home behavior
- Maximum isolation for highly sensitive reviews

### Example: Agent APIs + GitHub + Package Registries

```bash
# AI agent APIs
sudo iptables -A OUTPUT -d api.anthropic.com -j ACCEPT  # Claude Code
sudo iptables -A OUTPUT -d api.openai.com -j ACCEPT     # OpenAI models (pi)

# Code repositories
sudo iptables -A OUTPUT -d github.com -j ACCEPT
sudo iptables -A OUTPUT -d raw.githubusercontent.com -j ACCEPT

# Package registries
sudo iptables -A OUTPUT -d registry.npmjs.org -j ACCEPT
sudo iptables -A OUTPUT -d pypi.org -j ACCEPT
sudo iptables -A OUTPUT -d files.pythonhosted.org -j ACCEPT

# Localhost
sudo iptables -A OUTPUT -o lo -j ACCEPT

# Drop everything else
sudo iptables -A OUTPUT -j DROP
```

### Trade-offs

- Blocks package managers unless you allowlist registries
- May break tools that require network access
- DNS resolution still works (consider blocking if paranoid)

## Security Model

This devcontainer provides **filesystem isolation** but not complete sandboxing.

**Sandboxed:** Filesystem (host files inaccessible), processes (isolated from host), package installations (stay in container)

**Not sandboxed:** Network (full outbound by default—see [Network Isolation](#network-isolation)), git identity (`~/.gitconfig` mounted read-only), Docker socket (not mounted by default)

Claude Code is configured with `bypassPermissions` to run commands without confirmation. Pi runs without confirmation prompts by default. This would be risky on a host machine, but the container itself is the sandbox. All agents are configured to deny access to `.devcontainer/**` to prevent self-modification of the sandbox configuration.

## Container Details

| Component | Details |
|-----------|---------|
| Base | Ubuntu 24.04, Node.js 24 (LTS), Python 3.13 + uv, zsh |
| User | `vscode` (passwordless sudo), working dir `/workspace` |
| Tools | `rg`, `fd`, `tmux`, `fzf`, `delta`, `iptables`, `ipset` |
| AI Agents | Claude Code, [pi](https://github.com/badlogic/pi-mono) (more can be added) |
| Volumes (survive rebuilds) | Command history (`/commandhistory`), agent configs (`~/.claude`, `~/.pi`), GitHub CLI auth (`~/.config/gh`) |
| Host mounts | `~/.gitconfig` (read-only), `.devcontainer/` (read-only), optional `~/.config/nvim` import via `~/.config/nvim-host` |
| Auto-configured | Claude skills (anthropics, trailofbits), git-delta, optional writable Neovim config copy |

Volumes are stored outside the container, so your shell history, agent settings, and `gh` login persist even after `devc rebuild`. Host `~/.gitconfig` is mounted read-only for git identity.

### Per-Agent Configuration

Each agent has its own configuration directory mounted as a volume:

| Agent | Config Path | Environment Variable |
|-------|-------------|---------------------|
| Claude Code | `~/.claude` | `CLAUDE_CONFIG_DIR` |
| pi | `~/.pi` | `PI_CONFIG_DIR` |

## Troubleshooting

### "devcontainer CLI not found"

```bash
npm install -g @devcontainers/cli
```

### Container won't start

1. Check Docker is running
2. Try rebuilding: `devc rebuild`
3. Check logs: `docker logs $(docker ps -lq)`

### Agent configuration not persisting

Each agent stores config in its own volume. If ownership is wrong:

```bash
# Fix Claude Code config
sudo chown -R $(id -u):$(id -g) ~/.claude

# Fix pi config
sudo chown -R $(id -u):$(id -g) ~/.pi

# Fix GitHub CLI auth
sudo chown -R $(id -u):$(id -g) ~/.config/gh
```

### Neovim config not appearing in container

The Neovim host-config import only applies to the `devc` workflow (`devc .` / `devc template`).

- Ensure host config exists at `~/.config/nvim`
- Ensure `DEVC_DISABLE_LOCAL_NVIM` is not set to `1`, `true`, or `yes`
- Recreate/rebuild after changes: `devc rebuild`

To explicitly disable host Neovim import:

```bash
DEVC_DISABLE_LOCAL_NVIM=1 devc .
```

### Python/uv not working

Python is managed via uv:

```bash
uv run script.py              # Run a script
uv add package                # Add project dependency
uv run --with requests py.py  # Ad-hoc dependency
```

### Adding a new agent

To add support for another AI agent:

1. **Dockerfile**: Add installation commands and create config directory
2. **devcontainer.json**: Add volume mount for agent config and any required env vars
3. **post_install.py**: Add setup function to configure permissions
4. **.zshrc**: Add shell aliases if desired
5. **install.sh**: Update mount filtering in `extract_mounts_to_file()`
6. **README.md**: Add to the agent table and update documentation

## Development

### Building Locally

Build the image manually:

```bash
devcontainer build --workspace-folder .
```

Test the container:

```bash
devcontainer up --workspace-folder .
devcontainer exec --workspace-folder . zsh
```

### Contributing a New Agent

To add support for another AI agent to the agent-devcontainer:

1. **Dockerfile**: Add installation commands and create the config directory
   ```dockerfile
   # Install <agent>
   RUN npm install -g @<publisher>/<agent>-coding-agent
   
   # Create directory (do this in the combined mkdir step)
   RUN mkdir -p /home/vscode/.<agent> ...
   ```

2. **devcontainer.json**: Add volume mount and environment variables
   ```json
   "mounts": [
     "source=<agent>-config-${devcontainerId},target=/home/vscode/.<agent>,type=volume",
     ...
   ],
   "containerEnv": {
     "<AGENT>_CONFIG_DIR": "/home/vscode/.<agent>",
     "<AGENT>_DISABLE_PERMISSIONS": "true",
     ...
   }
   ```

3. **post_install.py**: Add setup function in the pattern of `setup_claude_settings()` or `setup_pi_settings()`

4. **install.sh**: Add the agent's config path to the mount filtering in `extract_mounts_to_file()`

5. **.zshrc**: Add shell alias if desired (e.g., `<agent>-yolo`)

6. **README.md**: 
   - Add the agent to the "Currently Available Agents" table
   - Update the "Per-Agent Configuration" table
   - Add any agent-specific network endpoints to the iptables example

See [Contributing](CONTRIBUTING.md) for PR guidelines (coming soon). For now, open an issue to discuss new agent additions.
