# Claude Code Devcontainer
# Based on Microsoft devcontainer image for better devcontainer integration
ARG UV_VERSION=0.10.0
FROM ghcr.io/astral-sh/uv:${UV_VERSION}@sha256:78a7ff97cd27b7124a5f3c2aefe146170793c56a1e03321dd31a289f6d82a04f AS uv
FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04@sha256:d94c97dd9cacf183d0a6fd12a8e87b526e9e928307674ae9c94139139c0c6eae

ARG TZ
ENV TZ="$TZ"

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install additional system packages (base image already includes git, curl, sudo, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
	# Sandboxing support for Claude Code
	bubblewrap \
	socat \
	# Modern CLI tools
	fd-find \
	ripgrep \
	tmux \
	zsh \
	# Build tools
	build-essential \
	cmake \
	ninja-build \
	gettext \
	# Utilities
	jq \
	nano \
	unzip \
	vim \
	# Network tools (for security testing)
	dnsutils \
	ipset \
	iptables \
	iproute2 \
	&& apt-get clean && rm -rf /var/lib/apt/lists/*

# Install git-delta
ARG GIT_DELTA_VERSION=0.18.2
RUN ARCH=$(dpkg --print-architecture) && \
	curl -fsSL "https://github.com/dandavison/delta/releases/download/${GIT_DELTA_VERSION}/git-delta_${GIT_DELTA_VERSION}_${ARCH}.deb" -o /tmp/git-delta.deb && \
	dpkg -i /tmp/git-delta.deb && \
	rm /tmp/git-delta.deb

# Install uv (Python package manager) via multi-stage copy
COPY --from=uv /uv /usr/local/bin/uv

# Install fzf from GitHub releases (newer than apt, includes built-in shell integration)
ARG FZF_VERSION=0.67.0
RUN ARCH=$(dpkg --print-architecture) && \
	case "${ARCH}" in \
	amd64) FZF_ARCH="linux_amd64" ;; \
	arm64) FZF_ARCH="linux_arm64" ;; \
	*) echo "Unsupported architecture: ${ARCH}" && exit 1 ;; \
	esac && \
	curl -fsSL "https://github.com/junegunn/fzf/releases/download/v${FZF_VERSION}/fzf-${FZF_VERSION}-${FZF_ARCH}.tar.gz" | tar -xz -C /usr/local/bin

# Build and install Neovim from latest stable source
ARG NEOVIM_VERSION=0.11.6
RUN git clone --depth 1 --branch "v${NEOVIM_VERSION}" https://github.com/neovim/neovim.git /tmp/neovim && \
	cd /tmp/neovim && \
	make CMAKE_BUILD_TYPE=Release && \
	make install && \
	rm -rf /tmp/neovim

# Create directories and set ownership (combined for fewer layers)
RUN mkdir -p /commandhistory /workspace /home/vscode/.claude /home/vscode/.pi/agent /opt && \
	touch /commandhistory/.bash_history && \
	touch /commandhistory/.zsh_history && \
	chown -R vscode:vscode /commandhistory /workspace /home/vscode/.claude /home/vscode/.pi /home/vscode/.config /opt

# Set environment variables
ENV DEVCONTAINER=true
ENV SHELL=/bin/zsh
ENV EDITOR=nano
ENV VISUAL=nano
ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8
ENV LANGUAGE=en_US:en

WORKDIR /workspace

# Switch to non-root user for remaining setup
USER vscode

# Set PATH early so claude and other user-installed binaries are available
ENV PATH="/home/vscode/.local/bin:$PATH"

# Install fnm (Fast Node Manager) and Node 24 (Active LTS) - must be before npm install
ARG NODE_VERSION=24
ENV FNM_DIR="/home/vscode/.fnm"
RUN curl -fsSL https://fnm.vercel.app/install | bash -s -- --install-dir "$FNM_DIR" --skip-shell && \
	export PATH="$FNM_DIR:$PATH" && \
	eval "$(fnm env)" && \
	fnm install ${NODE_VERSION} && \
	fnm default ${NODE_VERSION}

# Add fnm to PATH for subsequent RUN commands
ENV PATH="/home/vscode/.fnm:$PATH"

# Install Claude Code natively with marketplace plugins
RUN curl -fsSL https://claude.ai/install.sh | bash && \
	claude plugin marketplace add trailofbits/skills && \
	claude plugin marketplace add trailofbits/skills-curated

# TODO: add this back once the issue is fixed. Refer https://github.com/anthropics/claude-code/issues/14360
# RUN claude plugin marketplace add anthropic/skills 

# Install pi coding agent (use fnm exec to ensure Node.js environment is active)
RUN eval "$(fnm env --shell bash)" && npm install -g @mariozechner/pi-coding-agent

# Install Python 3.13 via uv (fast binary download, not source compilation)
RUN uv python install 3.13 --default

# Install ast-grep (AST-based code search)
RUN uv tool install ast-grep-cli

# Install Oh My Zsh
ARG ZSH_IN_DOCKER_VERSION=1.2.1
RUN sh -c "$(curl -fsSL https://github.com/deluan/zsh-in-docker/releases/download/v${ZSH_IN_DOCKER_VERSION}/zsh-in-docker.sh)" -- \
	-p git \
	-x

# Install Starship prompt
RUN mkdir -p /home/vscode/.local/bin && \
	curl -sS https://starship.rs/install.sh | sh -s -- -y --bin-dir /home/vscode/.local/bin

# Copy zsh configuration
COPY --chown=vscode:vscode .zshrc /home/vscode/.zshrc

# Copy post_install script
COPY --chown=vscode:vscode post_install.py /opt/post_install.py
