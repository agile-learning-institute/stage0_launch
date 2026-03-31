# Stage0 Launch

Flask web UI and API to **bootstrap** a new umbrella (from pasted specifications) and run **Launch** / **Clone** / **Build** / **Delete** on **selected** service domains. **Launch** and bootstrap retry **`publish-package`** once if it fails (transient network issues).

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
# Optional: insert before the image line:  -e DELETE_ENABLED=True  \  (exact string; see Environment).
```

Open **http://localhost:8080**.

### GitHub token and username

Use [this link](https://github.com/settings/tokens) to create a new GitHub **Classic** Token, with `repo`, `workflow`, `write:packages` scopes. The interactive **Delete** button and **`/api/jobs/delete-services`** are disabled unless you set **`DELETE_ENABLED=True`** (see **Environment**). If you use delete, also include `delete_repo` and `delete:package` scopes on the token.

If you want more information on Github Tokens, see [Creating a personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens). 

## Developer quick start (Docker Compose)

Use this when **contributing** or when you prefer Compose over a plain **`docker run`**.

```bash
export GITHUB_TOKEN='<your-personal-access-token>'
export GITHUB_USERNAME='<your-github-login>'
# Optional: enable Delete in the UI (literal True; same as plain docker run).
# export DELETE_ENABLED=True
pipenv install --dev   # optional; or use pip install -r / a local venv
pipenv run compose-up    # runs: docker compose down && docker compose up --build -d
```

Open **http://localhost:8080** (or **`LAUNCH_HOST_PORT`**).

The container uses **`/Launchpad`** as the launchpad root (the image creates it; Compose mounts your host folder there). Set **`LAUNCHPAD_HOST`** to the host directory to mount (default **`..`** relative to the compose file). You do **not** need **`LAUNCHPAD_DIR`** inside the container.

**`docker-compose.yaml`** maps host credentials into the container the same way: host **`GITHUB_TOKEN`**, **`GITHUB_USERNAME`**, and optional **`DELETE_ENABLED`** (see **`Environment`**). The image entrypoint then syncs **`GITHUB_*`** and **`GH_*`** inside the container.

**Umbrella `make stage0-launch-ui`:** runs **`docker run`** with the same **`ghcr.io/.../stage0_launch:latest`** ref as **`pipenv run container`** here. Docker uses a **local** image when that tag exists; otherwise it pulls.

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
- **Interactive**: checkbox list of domains, **All**, **Launch** / **Clone** / **Build** / **Delete** (delete is shown only when **`DELETE_ENABLED=True`**). **Build** runs **`build-package`** only for selected domains whose repos already exist locally (typical workflow: **Clone** then **Build**). Job log opens in a modal (SSE).

## API (selected)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/status` | Launchpad path, `bootstrap_mode`, `interactive_mode`, `discovery_*`, `services`, `launchpad_dir_warning`, `delete_enabled` |
| POST | `/api/specs/validate` | JSON `product_yaml`, `architecture_yaml`, `catalog_yaml` → `{ ok, errors[] }` |
| POST | `/api/specs/paste` | Validates then saves YAML under `.stage0-bootstrap/specs/` |
| POST | `/api/jobs/bootstrap` | Full bootstrap (requires pasted specs); writes `.stage0-launch.yaml` when the job completes successfully |
| POST | `/api/jobs/launch-services` | JSON `services`: list of domain names or space-separated string |
| POST | `/api/jobs/clone-services` | Same body |
| POST | `/api/jobs/build-services` | Same body: runs **`build-package`** only for existing service repo directories under the launchpad |
| POST | `/api/jobs/delete-services` | `services`, `i_confirm_delete_services`: `"yes"`, `i_confirm_slug`. Requires **`DELETE_ENABLED=True`**; otherwise **403** |
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
| `DELETE_ENABLED` | Set to the literal string **`True`** to show the Delete control and allow **`/api/jobs/delete-services`**. If unset or any other value, delete is hidden and the API returns **403**. |

## Local template testing (`merge-all` / `launchpad-test`)

Exercise **Docker runbook merge** against **local** `stage0_template_*` checkouts (no GitHub repo create/clone/push). From this repo’s root, **`..`** is the intended `--templates-root` (sibling folders like `stage0_template_flask_mongo` under the same parent as `stage0_launch`).

**Prerequisites:** `docker`, `yq`, and template directories present under `--templates-root`.

On **macOS**, merge uses the same path resolution as the app: if you are not inside the Launch container, `findmnt` is unavailable and is ignored so Docker bind mounts use your normal filesystem paths (`runbook_merge` change).

1. **merge-all** — copy umbrella + each service template into a launchpad (omits `.git` and **dependency lock files** present in your local template checkout so the materialized tree matches “pre-install” template content), merge umbrella using the **source** specifications directory, copy YAML into `<launchpad>/<slug>/Specifications`, then merge **every** service using **only** that umbrella `Specifications` tree:

   **Consumer repos (real Launch / GitHub):** Stage0 **templates** do not ship committed lockfiles, and **template `.gitignore` must not list** those locks—otherwise new repos created from the template could not commit `Pipfile.lock` / `package-lock.json` after `pipenv install` / `npm install`. The merge-all copy step only avoids copying stray locks from your machine; it does **not** change Git policy in generated repos.

   ```bash
   pipenv run merge-all /path/to/merged_launchpad /path/to/Specifications
   ```

   To match a golden tree that includes **`.stage0-launch.yaml`** at the launchpad root (same content the Launch UI writes after bootstrap), add **`--write-stub`**. That file records the umbrella folder name (`info.slug`) for discovery:

   ```bash
   pipenv run merge-all --write-stub /path/to/merged_launchpad /path/to/Specifications
   ```

   Override the templates parent (instead of `..`):  
   `PYTHONPATH=src python -m stage0_launch.cli merge-all --templates-root /other/parent ...`

2. **launchpad-test** — compare two launchpad roots: skips what each tree’s `.gitignore` would skip (any depth), common build noise, and **dependency lock basenames** as a **test convenience** (e.g. golden tree has locks after install, merged tree does not yet). That does **not** mean locks should stay out of git in real repos—only shrinks noise for this diff. Optional `--ignore-file` adds fnmatch lines:

   ```bash
   pipenv run launchpad-test /path/to/working /path/to/merged
   ```

**Workflow:** Keep a **working** launchpad that you trust (do not mutate it while using it as the golden tree); point merge-all at a **read-only** path to its `Specifications` if that is your source of truth. Regenerate a **merged** launchpad (e.g. empty `mentorhub_launchpad`) from the same specs and local `stage0_template_*` copies; **`pipenv run launchpad-test working merged`** until the diff is acceptable. For each template repo, run **`make test`** before treating that template as validated; then re-run merge-all and compare again.

Do **not** treat this as a substitute for a real **Launch** (GitHub template instantiation still matters for end-to-end checks).

## Testing

Use **`pipenv run compose-up`** (see **Developer quick start**) so the app runs in the same image as production, with Docker socket and launchpad mounts. For fast feedback without the full stack, run **`pipenv run test`**.

## Validate

`pipenv run validate` runs a minimal host check stub; extend `validate_host.py` for full CI checks if needed.
