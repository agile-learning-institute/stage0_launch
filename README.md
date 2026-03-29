# Stage0 Launch

Flask web UI and API to **bootstrap** a new umbrella (from pasted specifications) and run **Launch** / **Clone** / **Delete** on **selected** service domains.

## Quick start

Use this [CustomGPT](https://chatgpt.com/g/g-69a8f1731e448191a023fb6740ff46fd-stage0-architect) to help you describe your idea using launch specifications, and then... 

From an empty directory you want as the **launchpad**

```bash
export GITHUB_TOKEN='<your-personal-access-token>'
export GITHUB_USERNAME='<your-github-login>'

docker run -d --rm --name stage0_launch \
  -p 8080:8080 \
  -v "$(pwd):/Launchpad" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e GITHUB_TOKEN \
  -e GITHUB_USERNAME \
  -e STAGE0_LAUNCH_CONTAINER_NAME=stage0_launch \
  ghcr.io/agile-learning-institute/stage0_launch:latest
```

Open **http://localhost:8080**.

### GitHub token and username

Use [this link](https://github.com/settings/tokens) to create a new GitHub **Classic** Token, with `repo`, `workflow`, `write:packages` scopes. If you want to use the *Delete* features of Stage0 tooling, also include `delete_repo` and `delete:package` scopes.

If you want more information on Github Tokens, see [Creating a personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens). 

## Developer quick start (Docker Compose)

Use this when **contributing** or when you prefer Compose over a plain **`docker run`**.

```bash
export GITHUB_TOKEN='<your-personal-access-token>'
export GITHUB_USERNAME='<your-github-login>'
pipenv install --dev   # optional; or use pip install -r / a local venv
pipenv run compose-up    # runs: docker compose down && docker compose up --build -d
```

Open **http://localhost:8080** (or **`LAUNCH_HOST_PORT`**).

The container uses **`/Launchpad`** as the launchpad root (the image creates it; Compose mounts your host folder there). Set **`LAUNCHPAD_HOST`** to the host directory to mount (default **`..`** relative to the compose file). You do **not** need **`LAUNCHPAD_DIR`** inside the container.

**`docker-compose.yaml`** maps host credentials into the container the same way: host **`GITHUB_TOKEN`**, and **`GITHUB_USERNAME`**. The image entrypoint then syncs **`GITHUB_*`** and **`GH_*`** inside the container.

## Launchpad layout

- **`.stage0-launch.yaml`** (at the root of the launchpad) is written when bootstrap **finishes successfully**. It records which child folder is the umbrella, for example:

  ```yaml
  umbrella: my-product-slug
  ```

- **Bootstrap mode** (paste UI): this file is **missing**.
- **Interactive mode** (service checkboxes): stub exists and points at `<launchpad>/<umbrella>/Specifications` with the three YAML files; `info.slug` must match the umbrella folder name.
- If the stub exists but is invalid or the tree is broken, the UI stays in **operations** layout and shows a **discovery error** (not bootstrap).

Pasted specs are still saved under **`.stage0-bootstrap/specs/`** until bootstrap runs.

## Web UI

- **Bootstrap**: title, optional non-empty warning, three text areas, **Launch** (validates against the bundled JSON Schema, saves, then starts the bootstrap job).
- **Interactive**: checkbox list of domains, **All**, **Launch** / **Clone** / **Delete**. Job log opens in a modal (SSE).

## API (selected)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/status` | Launchpad path, `bootstrap_mode`, `interactive_mode`, `discovery_*`, `services`, `launchpad_dir_warning` |
| POST | `/api/specs/validate` | JSON `product_yaml`, `architecture_yaml`, `catalog_yaml` → `{ ok, errors[] }` |
| POST | `/api/specs/paste` | Validates then saves YAML under `.stage0-bootstrap/specs/` |
| POST | `/api/jobs/bootstrap` | Full bootstrap (requires pasted specs); writes `.stage0-launch.yaml` when the job completes successfully |
| POST | `/api/jobs/launch-services` | JSON `services`: list of domain names or space-separated string |
| POST | `/api/jobs/clone-services` | Same body |
| POST | `/api/jobs/delete-services` | `services`, `i_confirm_delete_services`: `"yes"`, `i_confirm_slug` |
| GET | `/api/jobs/<id>` | Job status + full log |
| GET | `/api/jobs/<id>/stream` | SSE log |

## Environment

| Variable | Meaning |
|----------|---------|
| `LAUNCHPAD_DIR` | Optional override for the launchpad path (tests, nonstandard layouts). If unset: use **`/Launchpad`** when that directory exists, else the process current directory. |
| `LAUNCHPAD_HOST` | **Compose only**: host path mounted at **`/Launchpad`** in the container (default **`..`**). |
| `GITHUB_TOKEN` | **Primary.** PAT for `git`, API, and GHCR. |
| `GH_TOKEN` | Legacy name read by **`gh`**. In the **container image**, the entrypoint sets it from **`GITHUB_TOKEN`** when unset (and the reverse). |
| `NODE_AUTH_TOKEN` | Optional. **Launch** maps **`GITHUB_TOKEN`** / **`GH_TOKEN`** into npm (via **`NODE_AUTH_TOKEN`** and **`NPM_CONFIG_USERCONFIG`**) for **`publish: npm`** on repos such as **`spa_utils`** (optional **GitHub Packages** publish). Default **SPA** templates install **`spa_utils`** from **git** in Docker/CI, not from **`npm.pkg.github.com`**, so consumer CI does not depend on per-package **Manage Actions access**. |
| `GITHUB_USERNAME` | **Primary.** GitHub login for `docker login ghcr.io` when publishing images. |
| `GH_USERNAME` | Legacy alias; in the **container image**, the entrypoint mirrors **`GITHUB_USERNAME`** when unset. On the host, Compose can still map **`GH_USERNAME`** → **`GITHUB_USERNAME`**. |
| `STAGE0_LAUNCH_CONTAINER_NAME` | Should match the Docker **`--name`** of this container so `docker inspect` can resolve launchpad bind mounts for nested `docker run`. |

## Testing

Use **`pipenv run compose-up`** (see **Developer quick start**) so the app runs in the same image as production, with Docker socket and launchpad mounts. For fast feedback without the full stack, run **`pipenv run test`**.

## Validate

`pipenv run validate` runs a minimal host check stub; extend `validate_host.py` for full CI checks if needed.
