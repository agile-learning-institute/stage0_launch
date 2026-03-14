# Stage0 Launch

Containerized Stage0 Launch tool. Creates an umbrella repo from the stage0 template, merges your specifications, and launches all of your services. 

## Prerequisites

Complete these before using Stage0 Launch:

1. **Conversation with the Stage0 Architect**  
   Have a conversation with the [Stage0 Architect](https://chatgpt.com/g/g-69a8f1731e448191a023fb6740ff46fd-stage0-architect) and obtain your specification files: `product.yaml`, `architecture.yaml`, and `catalog.yaml`.

2. **Docker Desktop**  
   Install and run [Docker Desktop](https://www.docker.com/products/docker-desktop/) so you can run the launch container.

3. **GitHub token**  
   We use GitHub to publish packages and containers. Create a **GitHub classic access token** with `repo`, `workflow`, and `write:packages` privileges.  

   To create it: sign in to GitHub and the click your user icon and choose → Profile → Settings → Developer settings → Personal access tokens → Tokens (classic) → Generate new Classic token → check **repo**, **workflow**, **write:packages**

---

## Quickstart

```bash
git clone https://github.com/agile-learning-institute/stage0_launch.git
cd stage0_launch

# Copy your yaml into the Specifications folder (replace the example files with product.yaml, architecture.yaml, catalog.yaml from your Stage0 Architect conversation)

export GITHUB_TOKEN=ghp_your_token_here
make run
```

The container runs once, prints progress, and exits. Follow the instructions in the final output box: go to the generated folder, wait for CI, then run `docker compose --profile all up -d` and open the URL it gives you.

---

## Contributing

### launch.sh

`launch.sh` runs inside the container. It uses `SPECIFICATIONS` (default `/specifications`) as the mounted input/output folder and `GITHUB_TOKEN` for GitHub over HTTPS. Specs are read from the root of the mounted folder (`product.yaml`, `architecture.yaml`, `catalog.yaml`). It checks for `yq`, `gh`, `git`, `make`, and `docker`, then: creates the umbrella repo from the template, clones it, runs the merge container with your specs, commits and pushes, copies arch/catalog into the repo, pushes again, and writes `DeveloperEdition/docker-compose.yaml` to `Specifications/<slug>_local/docker-compose.yaml`. When running via Docker, `HOST_SPECIFICATIONS` must be the host path to that folder; `make run` sets it for you.

### Developer prerequisites

To run `make dev` locally (same tools as in the Docker image), install:

| Tool | Purpose | Install |
|------|---------|--------|
| **git** | Clone and push | [git-scm.com](https://git-scm.com/downloads) — often pre-installed |
| **make** | Run targets | macOS: Xcode Command Line Tools (`xcode-select --install`). Linux: `apt install build-essential` |
| **gh** | GitHub CLI (create repo, auth) | [cli.github.com](https://cli.github.com/) — macOS: `brew install gh`; Linux: see official install |
| **docker** | Run merge container | [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker CLI and daemon) |
| **yq** | Read YAML (e.g. product.yaml) | [mikefarah/yq](https://github.com/mikefarah/yq) — macOS: `brew install yq`; Linux: download from releases |
| **jq** | JSON (optional, used in image) | [jqlang.github.io/jq](https://jqlang.github.io/jq/download/) — macOS: `brew install jq` |
| **GITHUB_TOKEN** | Auth for gh and git | Export in your shell; same token as in Prerequisites above |

From the repo root, set `GITHUB_TOKEN` and run:

```bash
export GITHUB_TOKEN=ghp_your_token_here
make dev
```

### Developer make commands

| Command | Description |
|--------|-------------|
| `make help` | List available commands |
| `make container` | Build the launch container image |
| `make run` | Run the launch container (mounts `./Specifications`) |
| `make dev` | Run `launch.sh` in dev mode using `./Specifications` (requires prerequisites above) |
| `make push` | Push the container image to the registry |
