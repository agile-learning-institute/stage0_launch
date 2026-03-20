# Stage0 Launch

Container image **`ghcr.io/agile-learning-institute/stage0_launch:latest`** bootstraps a new umbrella (create repo from template, merge specs, publish umbrella image, **`launch-all`** for every service in `architecture.yaml`). On the host you only need **Docker** and a **GitHub token**; the image supplies Node, Python 3.12, pipenv, Docker CLI/buildx, `gh`, etc.

Entrypoint is **`/launch.sh`** with subcommands (no legacy default beyond `bootstrap` when you pass no args—same as `launch.sh bootstrap`).

## Subcommands

| Command | Purpose |
|--------|---------|
| **`bootstrap`** | First-time launch: needs **`SPECIFICATIONS`**, **`LAUNCHPAD_DIR`**. Creates `LAUNCHPAD_DIR/<slug>`, merges, copies specs, umbrella `build-package` / `publish-package`, **`launch-all`**. |
| **`launch-all`** | From an existing umbrella clone: needs **`UMBRELLA_DIR`**, **`SERVICE_SOURCE_DIR`** (parent of umbrella). Umbrella publish + all services. |
| **`launch-services`** | Same, but only domains in **`SERVICES`** (space-separated). |
| **`clone-all`** | Clone every service repo next to the umbrella and run local **`build-package`** only (onboarding / fresh clones). |
| **`delete-services`** | Destructive: GitHub repos + packages for **`SERVICES`**. Confirm by typing slug, or set **`I_CONFIRM_DELETE_SERVICES=yes`** and **`I_CONFIRM_SLUG=<slug>`**. |
| **`delete-all`** | All services **plus** umbrella repo and umbrella container package. Confirm with **`DELETE ALL <slug>`**, or **`I_CONFIRM_DELETE_ALL=yes`** and **`I_CONFIRM_SLUG`**. |
| **`validate`** | Image smoke-test (tooling + optional Git SSH probe). For **stage0_launch** CI/dev, not wired from the umbrella Makefile. |
| **`help`** | Short usage. |

### Bootstrap env

| Variable | Meaning |
|----------|---------|
| `SPECIFICATIONS` | Folder with `product.yaml`, `architecture.yaml`, `catalog.yaml` |
| `LAUNCHPAD_DIR` | Directory **outside** any `.git` repo; umbrella clones to `LAUNCHPAD_DIR/<slug>` |
| `GITHUB_TOKEN` / `GH_TOKEN` | GitHub classic token (`repo`, `workflow`, `write:packages`; delete flows need more) |
| `REMOVE_STAGE0_LAUNCH_CLONE` | `1` or `yes`: after success, remove **`STAGE0_LAUNCH_REPO_DIR`** if basename is `stage0_launch` |
| `STAGE0_LAUNCH_REPO_DIR` | e.g. `/stage0_launch_repo` when bind-mounting the launch repo |
| `STAGE0_LAUNCH_KEEP_REPO` | `1` / `yes`: never remove the launch clone |

Umbrella automation always uses **`SERVICE_SOURCE_DIR`** = parent of the umbrella (sibling repos live there), and **`UMBRELLA_DIR`** = umbrella git root.

---

## Prerequisites

1. **Conversation with the Stage0 Architect**  
   [Stage0 Architect](https://chatgpt.com/g/g-69a8f1731e448191a023fb6740ff46fd-stage0-architect) — obtain `product.yaml`, `architecture.yaml`, `catalog.yaml`.

2. **Docker Desktop**  
   Host engine is used via **`/var/run/docker.sock`** (merge containers, image builds).

3. **GitHub token**  
   Classic PAT: **repo**, **workflow**, **write:packages** (and **`delete_repo` / `delete:packages`** if you use delete commands).

---

## Quickstart

```bash
git clone https://github.com/agile-learning-institute/stage0_launch.git
cd stage0_launch
# Place your YAML under ./Specifications

export GITHUB_TOKEN=ghp_your_token_here
make run
```

`make run` runs **`docker compose up --build`** so the local `Dockerfile` can populate `ghcr.io/.../stage0_launch:latest` until the registry image exists. Compose mounts **`./Specifications`**, **`..`** as launchpad, and **`./`** at **`/stage0_launch_repo`** for optional cleanup.

After bootstrap, open the umbrella path printed in the summary, install the developer CLI (`make install` / `CONTRIBUTING.md`), then **`<developer_cli> up all`** (your CLI name comes from merged `product.yaml`).

### Optional: remove the `stage0_launch` clone after bootstrap

```bash
export REMOVE_STAGE0_LAUNCH_CLONE=1
# STAGE0_LAUNCH_REPO_DIR=/stage0_launch_repo is set by compose; do not run from inside that directory.
make run
```

While developing this repo, set **`STAGE0_LAUNCH_KEEP_REPO=1`** or omit **`REMOVE_STAGE0_LAUNCH_CLONE`**.

---

## Umbrella repo (after merge)

From the **umbrella root**, use Makefile wrappers (same **`stage0_launch`** image, pinned in **`DeveloperEdition/launch-docker-compose.yaml`**):

- `make stage0-automation-help`
- `make launch-all`, `make launch-services SERVICES="..."`, `make clone-all`
- `make delete-services` / `make delete-all` with confirmation (or `I_CONFIRM_*` env vars for automation)

---

## Contributing

### Tooling in the image

See earlier sections: **git**, **gh**, **make**, **jq**, **yq**, **curl**, **openssh-client**, **Docker CLI** + **buildx**, **Node 22**, **Vite**, **Python 3.12**, **pipenv**.

### Host `make dev`

```bash
export GITHUB_TOKEN=ghp_...
make dev SPECIFICATIONS=/path/to/specs   # runs launch.sh bootstrap with a temp launchpad
make validate                             # launch.sh validate
```

### Make targets

| Command | Description |
|--------|-------------|
| `make help` | List commands |
| `make run` | `docker compose up --build` (bootstrap) |
| `make dev SPECIFICATIONS=...` | Bootstrap on host with temp launchpad |
| `make validate` | Run `validate` subcommand on host |
| `make container` | Build `stage0_launch:latest` only |

Git SSH in **`validate`** needs **`~/.ssh`** mounted if you run it in a container (not required for **`bootstrap`**).
