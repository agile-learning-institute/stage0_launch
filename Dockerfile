# Stage0 Launch — Flask + toolchain for bootstrap / umbrella automation
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PATH="/root/.local/bin:${PATH}" \
    PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git make jq gnupg openssh-client build-essential \
    python3.12 python3.12-venv python3-pip pipx \
    && rm -rf /var/lib/apt/lists/*

RUN pipx install pipenv

RUN install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc && \
    chmod a+r /etc/apt/keyrings/docker.asc && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu noble stable" > /etc/apt/sources.list.d/docker.list && \
    apt-get update && apt-get install -y --no-install-recommends \
        docker-ce-cli docker-buildx-plugin docker-compose-plugin && \
    rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | \
    gpg --dearmor -o /usr/share/keyrings/githubcli-archive-keyring.gpg && \
    chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list && \
    apt-get update && apt-get install -y --no-install-recommends gh && \
    rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

RUN curl -sSL "https://github.com/mikefarah/yq/releases/latest/download/yq_linux_$(dpkg --print-architecture)" -o /usr/local/bin/yq && \
    chmod +x /usr/local/bin/yq

RUN npm install -g vite

RUN git config --global user.name "Stage0 Launch" && \
    git config --global user.email "stage0-launch@localhost"

WORKDIR /app

RUN install -d -m 0755 /Launchpad

COPY Pipfile ./
RUN pip3 install --no-cache-dir --break-system-packages \
    "flask>=3.0" "gunicorn>=22.0" "pyyaml>=6.0" "jsonschema>=4.0"

COPY src ./src

EXPOSE 8080

CMD ["gunicorn", "-b", "0.0.0.0:8080", "-w", "1", "--threads", "8", "stage0_launch.wsgi:application"]
