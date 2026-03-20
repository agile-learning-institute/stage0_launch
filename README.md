# Stage0 Launch

Containerized Stage0 Launch tool. Creates an umbrella repo from the stage0 template, merges your specifications, runs **`make launch-all`** inside the generated umbrella (service repos, merges, Docker builds, and registry pushes), then prints where to go next. You only need Docker and a GitHub token on the host—the image carries the rest of the toolchain.

## Prerequisites

Complete these before using Stage0 Launch:

1. **Conversation with the Stage0 Architect**  
   Have a conversation with the [Stage0 Architect](https://chatgpt.com/g/g-69a8f1731e448191a023fb6740ff46fd-stage0-architect) and obtain your specification files: `product.yaml`, `architecture.yaml`, and `catalog.yaml`.

2. **Docker Desktop**  
   Install and run [Docker Desktop](https://www.docker.com/products/docker-desktop/) so you can run the launch container. The container uses the **host** Docker engine (socket mount) to run merge images and build/push service images.

3. **GitHub token**  
   We use GitHub to publish packages and containers. Create a **GitHub classic access token** with `repo`, `workflow`, and `write:packages` privileges.  

   To create it: sign in to GitHub and the click your user icon and choose → Profile → Settings → Developer settings → Personal access tokens → Tokens (classic) → Generate new Classic token → check **repo**, **workflow**, **write:packages**

### What’s inside the launch image

So you don’t install them on your laptop for Quickstart: **git**, **gh**, **make**, **jq**, **yq**, **curl**, **openssh-client**, **Docker CLI** + **buildx** + **compose** plugin (driver is still the host), **Node.js 22** + **npm**, global **Vite**, **Python 3.12**, **pipenv** (via **pipx**), **build-essential** (node-gyp / native deps), and a default **git** `user.name` / `user.email` for commits. Export **`GITHUB_TOKEN`** on the host; the entrypoint also sets **`GH_TOKEN`** for `gh`.

Umbrella **`make validate`** includes a **Git SSH** clone/push probe; the launch flow does **not** run that. If you run `validate` inside the container, mount your keys, e.g. add under `volumes` in `docker-compose.yaml`: `- ~/.ssh:/root/.ssh:ro` (and ensure `github.com` is in `known_hosts` or use `ssh-keyscan`).

---

## Quickstart

```bash
git clone https://github.com/agile-learning-institute/stage0_launch.git
cd stage0_launch

# Copy your yaml into the Specifications folder (replace the example files with product.yaml, architecture.yaml, catalog.yaml from your Stage0 Architect conversation)

export GITHUB_TOKEN=ghp_your_token_here
make run
```

The container runs once, prints progress, and exits. It has already run **`make launch-all`** in the umbrella (creating service repos, merging specs, building and pushing images as defined in your architecture). Follow the final output box: open the umbrella on disk, install the **developer CLI** from that repo (see umbrella `DeveloperEdition` / root `Makefile` help), then run **`<developer_cli> up all`** to bring stacks up locally.

If you prefer to run launch steps on the host instead of inside this image, use the same tools listed under [Developer prerequisites](#developer-prerequisites) and run `make validate` / `make launch-all` from `DeveloperEdition/stage0` yourself.

---

## Contributing

### launch.sh

`launch.sh` is the container entrypoint (or runs locally via `make dev`). It requires `SPECIFICATIONS` (folder with your YAML) and `LAUNCHPAD_DIR` (must exist and sit **outside** any `.git` tree; the umbrella is cloned to `LAUNCHPAD_DIR/<slug>`). With Compose, those map to `/specifications` and `/launchpad`; `make run` sets `HOST_SPECIFICATIONS` to `./Specifications` and `HOST_LAUNCHPAD` to the repo parent (`../`) so those mounts resolve on the host. It uses `GITHUB_TOKEN` for HTTPS (`gh`, `git`, publishing) and sets `GH_TOKEN` for the GitHub CLI. The spec folder must contain `product.yaml`, `architecture.yaml`, and `catalog.yaml`; `product.yaml` supplies `organization.git_org`, `info.slug`, and `info.base_port`. In the **container image**, the tools needed through `make launch-all` are pre-installed (see [What’s inside the launch image](#whats-inside-the-launch-image)); for `make dev` on the host, install them yourself. Flow: `gh repo create` from `agile-learning-institute/stage0_template_umbrella`, short wait, clone, `make merge` with your spec path, copy every `*.yaml` / `*.yml` from the spec folder into the umbrella `Specifications/`, `make build-package` and `make publish-package`, one `git` commit and push if anything changed, then `make launch-all` in `DeveloperEdition/stage0`. The umbrella keeps launch/delete automation there (including `validate`).

### Developer prerequisites

To run `make dev` on the **host** without the container, install the same toolchain the image provides (not an exhaustive lockstep list—match what your specs’ services need):

| Tool | Purpose | Install |
|------|---------|--------|
| **git** | Clone and push | [git-scm.com](https://git-scm.com/downloads) — often pre-installed |
| **make** | Run targets | macOS: Xcode Command Line Tools (`xcode-select --install`). Linux: `apt install build-essential` |
| **gh** | GitHub CLI (create repo, auth) | [cli.github.com](https://cli.github.com/) — macOS: `brew install gh`; Linux: see official install |
| **docker** | Run merge container | [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker CLI and daemon) |
| **yq** | Read YAML (e.g. product.yaml) | [mikefarah/yq](https://github.com/mikefarah/yq) — macOS: `brew install yq`; Linux: download from releases |
| **jq** | JSON (optional, used in image) | [jqlang.github.io/jq](https://jqlang.github.io/jq/download/) — macOS: `brew install jq` |
| **node / npm / vite** | SPA merges and `npm run build-package` | e.g. Node 22 LTS; `npm install -g vite` if you want a global `vite` for `make validate` |
| **Python 3.12 / pipenv** | API merges and `pipenv run build-package` | Match umbrella `verify` / `DeveloperEdition/stage0` `validate` expectations |
| **docker buildx** | Image builds in launch-services | Docker Desktop usually includes buildx |
| **ssh** (optional) | Umbrella `make validate` Git SSH probe | Only if you run `validate` |
| **GITHUB_TOKEN** | Auth for gh and git | Export in your shell; same token as in Prerequisites above |

From the repo root, set `GITHUB_TOKEN` and run:

```bash
export GITHUB_TOKEN=ghp_your_token_here
make dev SPECIFICATIONS=<path> 
```

### Developer make commands

| Command | Description |
|--------|-------------|
| `make help` | List available commands |
| `make run` | Run the launch container (`./Specifications` and parent directory `../` as launchpad via `docker compose up`) |
| `make dev SPECIFICATIONS=<path>` | Run `launch.sh` in dev mode (launchpad is `/tmp/stage0_launchpad_<pid>`) |
| `make container` | Build the launch container image (`stage0_launch:latest` by default) |
