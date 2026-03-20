# Stage0 Launch — full toolchain for launch.sh through umbrella `make launch-all`
# (merge containers, npm/pipenv builds, docker build/push via mounted host daemon).
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PATH="/root/.local/bin:${PATH}"

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    make \
    jq \
    gnupg \
    openssh-client \
    build-essential \
    python3.12 \
    python3.12-venv \
    pipx \
    && rm -rf /var/lib/apt/lists/*

# Docker CLI + buildx (uses host engine via /var/run/docker.sock)
RUN install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc && \
    chmod a+r /etc/apt/keyrings/docker.asc && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu noble stable" > /etc/apt/sources.list.d/docker.list && \
    apt-get update && apt-get install -y --no-install-recommends \
        docker-ce-cli \
        docker-buildx-plugin \
        docker-compose-plugin && \
    rm -rf /var/lib/apt/lists/*

# GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | \
    gpg --dearmor -o /usr/share/keyrings/githubcli-archive-keyring.gpg && \
    chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list && \
    apt-get update && apt-get install -y --no-install-recommends gh && \
    rm -rf /var/lib/apt/lists/*

# Node.js 22 LTS (npm run build-package for SPAs, etc.)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# yq
RUN curl -sSL "https://github.com/mikefarah/yq/releases/latest/download/yq_linux_$(dpkg --print-architecture)" -o /usr/local/bin/yq && \
    chmod +x /usr/local/bin/yq

# pipenv (umbrella validate + pipenv run build-package for APIs)
RUN pipx install pipenv

# Vite on PATH (DeveloperEdition/stage0 `make validate`)
RUN npm install -g vite

RUN git config --global user.name "Stage0 Launch" && \
    git config --global user.email "stage0-launch@localhost"

COPY launch.sh /launch.sh
RUN chmod +x /launch.sh

# Mount: ./Specifications -> /specifications, launchpad host dir -> /launchpad, docker.sock. Set GITHUB_TOKEN.
ENTRYPOINT ["/launch.sh"]
