# Security Audit Report

**Project:** agent-devcontainer  
**Date:** 2026-03-08  
**Auditor:** AI assistant

## Executive Summary

This project is intended to provide a safer environment for running AI coding agents with minimal or disabled permission prompts by placing them inside a devcontainer rather than directly on the host system. The core security goal is to reduce host risk during code review, audit, and experimentation workflows.

The implementation does reduce some risk, but it should be understood as **risk reduction**, not a strong sandbox. The current design still exposes important host-connected surfaces, especially through the bind-mounted workspace, optional host config import, unrestricted outbound network access by default, and elevated container privileges.

## Scope Reviewed

The following files were reviewed:

- `README.md`
- `Dockerfile`
- `devcontainer.json`
- `install.sh`
- `post_install.py`
- `.zshrc`
- `.claude/settings.json`

## Intended Security Model

The codebase appears to aim for the following:

- run unrestricted AI coding agents in a container instead of on the host
- keep agent configs in Docker volumes
- optionally import host configs read-only, then copy them into writable in-container paths
- mount `.devcontainer/` read-only to reduce sandbox self-modification
- allow optional outbound network restriction via `iptables`
- provide a helper CLI (`devc`) for managing the environment

Relevant references:

- `README.md:15`
- `README.md:287-293`
- `devcontainer.json:73`
- `post_install.py:64-110`

---

## Findings

### 1. Workspace is a read-write host bind mount
**Severity:** High

**Affected code:**
- `devcontainer.json:73`

```json
"workspaceMount": "source=${localWorkspaceFolder},target=/workspace,type=bind,consistency=delegated"
```

**Issue**

The README emphasizes filesystem isolation, but the active workspace is directly bind-mounted from the host into the container. This means the target repository remains writable from inside the container.

**Impact**

A compromised agent, malicious dependency, or unsafe command can:

- modify files in the host checkout
- alter `.git/config`, hooks, CI files, scripts, or editor config in the repo
- persist changes that later execute when the repo is used from the host

This significantly weakens the “sandbox” claim for untrusted repositories.

**Recommendation**

- Offer a **volume-backed workspace** mode and make it the secure default
- Keep bind-mounted workspace support only as an explicit convenience mode
- Document clearly that the workspace itself is host-backed and writable

---

### 2. Host config import copies potentially sensitive data into a container running unrestricted agents
**Severity:** High

**Affected code:**
- `README.md:179-186`
- `install.sh:202`
- `install.sh:216`
- `install.sh:237`
- `install.sh:257`
- `install.sh:264`
- `post_install.py:116-176`
- `post_install.py:235-378`

**Issue**

The helper auto-detects host configs and mounts them read-only, then copies them into writable container paths. This includes:

- `~/.claude`
- `~/.pi`
- `~/.config/nvim`
- `~/.tmux`
- `~/.tmux.conf`

Although the original mount is read-only, the copied contents become fully available inside the container.

**Impact**

Because agents are configured to operate with minimal permission checks:

- Claude is set to `bypassPermissions` (`post_install.py:80`)
- pi uses `PI_DISABLE_PERMISSIONS=true` (`devcontainer.json:56`)

Sensitive material copied from host configs may be exposed to agents, including:

- API tokens
- session data
- local prompts or config secrets
- plugin code
- shell/editor automation

Neovim and tmux imports also increase execution surface because those configs may trigger arbitrary plugin/bootstrap logic.

**Recommendation**

- Make host config import **opt-in**, not default
- Separate credentials import from UI/editor config import
- Do not import Neovim/tmux/plugin directories by default
- Add explicit warnings that imported config may expose secrets to in-container agents

---

### 3. `.devcontainer` protection is weaker than documented
**Severity:** Medium-High

**Affected code:**
- `README.md:293`
- `post_install.py:64-110`
- `.claude/settings.json`

**Issue**

The README states that all agents are configured to deny access to `.devcontainer/**`. In practice:

- Claude is configured in `post_install.py` only for `bypassPermissions`
- pi gets a deny rule for only `Read(.devcontainer/**)`
- the repo-local `.claude/settings.json` contains a deny rule, but it is not applied by `Dockerfile` or `post_install.py`

**Impact**

This creates a mismatch between documentation and enforcement.

The read-only bind mount for `.devcontainer` does provide meaningful protection, but the app-level restrictions do not appear to match the documented claim. For pi, denying only `Read(...)` is also a narrow control if broader permissions are already disabled.

**Recommendation**

- Apply explicit `.devcontainer` deny rules to **both** Claude and pi during post-create
- Deny more than read access if the agent supports it
- Update documentation to distinguish between filesystem-enforced and agent-enforced controls

---

### 4. Network is unrestricted by default, while the container has elevated network capabilities
**Severity:** Medium-High

**Affected code:**
- `README.md:248`
- `README.md:291`
- `devcontainer.json:16-17`

```json
"runArgs": [
  "--cap-add=NET_ADMIN",
  "--cap-add=NET_RAW"
]
```

**Issue**

The container has full outbound access by default and is granted `NET_ADMIN` and `NET_RAW` capabilities.

**Impact**

A malicious agent or dependency can:

- exfiltrate source code, credentials, or tokens
- modify firewall rules
- use raw sockets / packet crafting
- scan reachable internal network resources

This is especially relevant because the environment is designed for agents that can execute commands without normal confirmation prompts.

**Recommendation**

- Remove `NET_RAW` unless strictly necessary
- Gate `NET_ADMIN` behind an explicit opt-in profile
- Consider a secure profile with outbound allowlisting by default
- Document that default networking is broad and not a sandbox boundary

---

### 5. Passwordless sudo materially increases impact of compromise inside the container
**Severity:** Medium

**Affected code:**
- `README.md:300`
- `post_install.py:322-323`

**Issue**

The container user is documented as `vscode` with passwordless sudo. This is also used during post-create for recursive ownership fixes.

**Impact**

This expands what a compromised process or unrestricted agent can do inside the container, especially when combined with:

- full outbound network access
- extra Linux capabilities
- writable workspace and imported configs

This may be acceptable as a convenience tradeoff, but it weakens any “hardened sandbox” interpretation.

**Recommendation**

- Offer a reduced-privilege mode without passwordless sudo
- Limit sudo-enabled actions to setup-only workflows if possible
- Document this as a deliberate usability tradeoff

---

### 6. Remote installer and supply-chain trust model is weak
**Severity:** Medium

**Affected code:**
- `Dockerfile:93`
- `Dockerfile:103-105`
- `Dockerfile:111`
- `Dockerfile:121`
- `Dockerfile:127`

**Issue**

The image build uses several remote install flows that rely on upstream scripts or unverified artifacts:

- `curl | bash` for fnm
- `curl | bash` for Claude installer
- remote shell script for zsh-in-docker
- `curl | sh` for Starship
- npm global install of `@mariozechner/pi-coding-agent` without a pinned version
- plugin installation by name from marketplace
- GitHub release downloads without checksum verification

**Impact**

A compromised upstream installer, release artifact, or dependency could compromise the image build. Because this project is security-themed, supply-chain integrity matters more than usual.

**Recommendation**

- Pin versions for all third-party packages and plugins
- Verify checksums or signatures for downloaded artifacts
- Prefer package-manager installs over `curl | bash` where feasible
- Pin npm package versions explicitly

---

### 7. `devc mount` is a major footgun and defaults to read-write
**Severity:** Medium

**Affected code:**
- `install.sh:398-428`
- `README.md:173`

**Issue**

`devc mount` allows adding arbitrary host paths into the container, and mounts are writable unless `--readonly` is supplied.

**Impact**

Users can accidentally defeat the isolation model by mounting:

- `$HOME`
- `~/.ssh`
- cloud credentials
- password manager data
- general secrets directories

The README warns about this, but the CLI default remains unsafe.

**Recommendation**

- Make mounts read-only by default
- Require an explicit `--readwrite` flag for writable mounts
- Reject or heavily warn on dangerous sources such as `/`, `$HOME`, `~/.ssh`, and cloud credential directories

---

### 8. Validation against sandbox self-modification is useful but incomplete
**Severity:** Medium

**Affected code:**
- `install.sh:81-90`

**Issue**

The helper prevents use of `SYS_ADMIN` in `runArgs`, which is good defense in depth. However, the validation is narrow.

**Impact**

Other dangerous changes may still undermine the security model, including:

- `--privileged`
- overly broad capabilities
- Docker socket mounts
- additional sensitive host mounts
- risky lifecycle commands

**Recommendation**

Expand validation to reject or warn on:

- `--privileged`
- Docker socket mounts
- `cap-add=ALL`
- writable mounts to sensitive host paths
- suspicious `initializeCommand` / lifecycle hooks

---

### 9. Preserving symlinks during config import can widen execution/access surface
**Severity:** Low-Medium

**Affected code:**
- `post_install.py:54`
- `post_install.py:266`
- `post_install.py:378`

**Issue**

The config import logic preserves symlinks when copying host content into writable in-container paths.

**Impact**

Symlinks inside imported configs may later be followed by tools in the container, leading to surprising behavior or a broader-than-expected access surface. This is not necessarily a host escape, but it makes the environment harder to reason about safely.

**Recommendation**

- Reject symlinks during config import
- Or resolve/import only a small allowlisted subset of files

---

### 10. Host git config is included into in-container git config
**Severity:** Low

**Affected code:**
- `devcontainer.json:49`
- `post_install.py:397-450`

**Issue**

The container includes host `~/.gitconfig` read-only and then references it from a local git config.

**Impact**

Host git config can define:

- shell aliases
- credential helpers
- custom pagers or filters
- behavior that assumes a trusted local environment

This does not directly break host isolation, but it increases in-container execution surface and may leak identity or behavior assumptions into the sandbox.

**Recommendation**

- Consider importing only minimal identity settings
- Warn users that host git config may include executable helpers or aliases

---

## Positive Security Properties

The project does include some good controls:

- `.devcontainer/` is mounted read-only inside the container (`devcontainer.json:50`)
- Docker socket is not mounted by default (`README.md:291`)
- agent config target paths are persisted in Docker volumes
- documentation does warn about dangerous host mounts and unrestricted network access
- `check_no_sys_admin()` in `install.sh` is a useful defense-in-depth measure
- host `.gitconfig` is treated as read-only and wrapped by local git config

## Overall Assessment

This project is best described as a **convenience-first devcontainer that reduces some host risk when running unrestricted coding agents**, not as a strong sandbox for hostile or highly untrusted code.

The main reasons are:

1. the workspace remains a writable host bind mount
2. host configs may be copied into the container by default
3. agents are intentionally granted broad execution freedom
4. networking is unrestricted by default
5. the container has elevated privileges relative to a hardened review environment

## Priority Remediation Plan

### Highest priority

1. Make a **volume-backed workspace** the secure default
2. Make host config import **opt-in**
3. Remove `NET_RAW` and make `NET_ADMIN` opt-in
4. Enforce `.devcontainer` deny rules consistently for all agents
5. Change `devc mount` to default to read-only
6. Pin and verify third-party installers and artifacts

### Medium priority

7. Expand `devcontainer.json` safety validation beyond `SYS_ADMIN`
8. Reduce or eliminate passwordless sudo in hardened mode
9. Restrict or sanitize imported config content, especially symlinks and plugin directories

## Conclusion

The core idea is sound and practical, and several defense-in-depth decisions are thoughtful. However, the current implementation should not be presented as a strong sandbox without clearer qualification. The most important hardening work is to reduce host coupling, restrict imported secrets/config, and tighten container privileges and network exposure.
