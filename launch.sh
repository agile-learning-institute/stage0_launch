#!/usr/bin/env bash
# Stage0 Launch - Creates umbrella repo from template, merges specs, builds/publishes, launches all services.
# Usage: SPECIFICATIONS=<path> LAUNCHPAD_DIR=<path> [GITHUB_TOKEN=...] ./launch.sh
#   SPECIFICATIONS  - path to folder containing product.yaml, architecture.yaml, catalog.yaml (and other yaml specs)
#   LAUNCHPAD_DIR  - path to a directory *outside* any .git repo where the umbrella will be cloned

set -e

# --- Configuration from env ---
SPECIFICATIONS="${SPECIFICATIONS:?Error: SPECIFICATIONS must be set (path to specifications folder)}"
LAUNCHPAD_DIR="${LAUNCHPAD_DIR:?Error: LAUNCHPAD_DIR must be set (path outside any .git repo)}"

# --- Pre-reqs (from README.md + Makefile.template verify) ---
check_prereqs() {
  local fail=0
  echo "=== Checking prerequisites ==="
  command -v yq    >/dev/null 2>&1 || { echo "  FAIL: yq"; fail=1; }
  command -v gh    >/dev/null 2>&1 || { echo "  FAIL: gh"; fail=1; }
  command -v git   >/dev/null 2>&1 || { echo "  FAIL: git"; fail=1; }
  command -v make  >/dev/null 2>&1 || { echo "  FAIL: make"; fail=1; }
  command -v docker >/dev/null 2>&1 || { echo "  FAIL: docker (needed for merge)"; fail=1; }
  [ -n "${GITHUB_TOKEN:-}" ] || { echo "  FAIL: GITHUB_TOKEN not set"; fail=1; }
  if [ "$fail" -eq 1 ]; then
    echo "Install missing tools. See CONTRIBUTING.md and Makefile.template verify target."
    exit 1
  fi
  echo "  Prerequisites OK"
}

# --- Pre-flight: spec folder, product.yaml, and LAUNCHPAD_DIR outside .git ---
preflight() {
  echo "=== Pre-flight checks ==="
  [ -d "$SPECIFICATIONS" ] || { echo "Error: Spec folder not found: $SPECIFICATIONS"; exit 1; }
  [ -f "$SPECIFICATIONS/product.yaml" ] || { echo "Error: $SPECIFICATIONS/product.yaml not found"; exit 1; }
  [ -f "$SPECIFICATIONS/architecture.yaml" ] || { echo "Error: $SPECIFICATIONS/architecture.yaml not found"; exit 1; }
  [ -f "$SPECIFICATIONS/catalog.yaml" ] || { echo "Error: $SPECIFICATIONS/catalog.yaml not found"; exit 1; }

  ORG=$(yq -r '.organization.git_org' "$SPECIFICATIONS/product.yaml")
  SLUG=$(yq -r '.info.slug' "$SPECIFICATIONS/product.yaml")
  BASE_PORT=$(yq -r '.info.base_port' "$SPECIFICATIONS/product.yaml")

  [ -n "$ORG" ] && [ "$ORG" != "null" ] || { echo "Error: organization.git_org not found in product.yaml"; exit 1; }
  [ -n "$SLUG" ] && [ "$SLUG" != "null" ] || { echo "Error: info.slug not found in product.yaml"; exit 1; }
  [ -n "$BASE_PORT" ] && [ "$BASE_PORT" != "null" ] || { echo "Error: info.base_port not found in product.yaml"; exit 1; }

  # LAUNCHPAD_DIR must exist and be outside any .git repo
  [ -d "$LAUNCHPAD_DIR" ] || { echo "Error: LAUNCHPAD_DIR is not a directory: $LAUNCHPAD_DIR"; exit 1; }
  if (cd "$LAUNCHPAD_DIR" && git rev-parse 2>/dev/null); then
    echo "Error: LAUNCHPAD_DIR must be outside any .git repo: $LAUNCHPAD_DIR"
    exit 1
  fi

  echo "  ORG=$ORG SLUG=$SLUG BASE_PORT=$BASE_PORT"
  echo "  SPECIFICATIONS=$SPECIFICATIONS LAUNCHPAD_DIR=$LAUNCHPAD_DIR"
  echo "  Pre-flight OK"
}

# --- Git URL with token (HTTPS, no SSH) ---
git_url() {
  echo "https://x-access-token:${GITHUB_TOKEN}@github.com/${ORG}/${SLUG}.git"
}

# --- Main ---
main() {
  check_prereqs
  preflight

  UMBRELLA_DIR="$LAUNCHPAD_DIR/$SLUG"

  echo ""
  echo "=== 1. Creating umbrella repo ==="
  gh repo create "$ORG/$SLUG" --template "agile-learning-institute/stage0_template_umbrella" --public || exit 1
  echo "  Waiting 5s for GitHub..."
  sleep 5

  echo ""
  echo "=== 2. Cloning umbrella to launchpad ==="
  (cd "$LAUNCHPAD_DIR" && git clone "$(git_url)" "$SLUG") || exit 1

  echo ""
  echo "=== 3. Merge specifications ==="
  (cd "$UMBRELLA_DIR" && make merge "$SPECIFICATIONS") || exit 1

  echo ""
  echo "=== 4. Copy specifications into umbrella ==="
  mkdir -p "$UMBRELLA_DIR/Specifications"
  for f in "$SPECIFICATIONS"/*.yaml "$SPECIFICATIONS"/*.yml; do
    [ -f "$f" ] && cp "$f" "$UMBRELLA_DIR/Specifications/"
  done

  echo ""
  echo "=== 5. Build and publish umbrella package ==="
  (cd "$UMBRELLA_DIR" && make build-package && make publish-package) || exit 1

  echo ""
  echo "=== 6. Commit and push ==="
  (cd "$UMBRELLA_DIR" && \
   git config --global url."https://x-access-token:${GITHUB_TOKEN}@github.com/".insteadOf "https://github.com/" && \
   git config user.email "stage0-launch@localhost" 2>/dev/null || true && \
   git config user.name "Stage0 Launch" 2>/dev/null || true && \
   git add -A && (git diff --cached --quiet || (git commit -m "Merge and specifications; build and publish complete" && git push))) || exit 1

  echo ""
  echo "=== 7. Launch all services ==="
  (cd "$UMBRELLA_DIR/DeveloperEdition/stage0" && make launch-all) || exit 1

  # --- Next Steps (box) ---
  echo ""
  printf '\033[1;36m'
  echo "##############################################################################"
  echo "###                                                                        ###"
  echo "###   LAUNCH COMPLETE                                                      ###"
  echo "###                                                                        ###"
  echo "###   Next Steps:                                                          ###"
  echo "###   1.  cd $UMBRELLA_DIR/DeveloperEdition/stage0                        ###"
  echo "###   2.  make up all                                                     ###"
  echo "###   3.  Open: http://localhost:${BASE_PORT}                              ###"
  echo "###                                                                        ###"
  echo "##############################################################################"
  printf '\033[0m'
}

main "$@"
