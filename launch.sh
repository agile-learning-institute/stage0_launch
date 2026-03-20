#!/usr/bin/env bash
# Stage0 Launch — bootstrap new umbrellas and umbrella automation subcommands.
#
# Bootstrap: SPECIFICATIONS + LAUNCHPAD_DIR
# Automation: UMBRELLA_DIR + SERVICE_SOURCE_DIR (see umbrella_automation.sh)
#
# Usage:
#   launch.sh bootstrap
#   launch.sh launch-all | launch-services | clone-all | delete-all | delete-services | validate
#   launch.sh help

set -e

export GH_TOKEN="${GITHUB_TOKEN:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./umbrella_automation.sh
source "${SCRIPT_DIR}/umbrella_automation.sh"

usage() {
  echo "Usage: launch.sh <subcommand>"
  echo ""
  echo "Subcommands:"
  echo "  bootstrap          Create umbrella from spec, merge, publish, launch-all (needs SPECIFICATIONS, LAUNCHPAD_DIR)"
  echo "  launch-all         Umbrella build-package + publish + all service repos (needs UMBRELLA_DIR, SERVICE_SOURCE_DIR)"
  echo "  launch-services    Same for SERVICES=\"domain ...\""
  echo "  clone-all          Clone all service repos beside umbrella and build (no publish)"
  echo "  delete-services    Destructive: SERVICES=... ; optional I_CONFIRM_DELETE_SERVICES=yes I_CONFIRM_SLUG="
  echo "  delete-all         Destructive: all services + umbrella repo/package ; optional I_CONFIRM_DELETE_ALL=yes"
  echo "  validate           Tooling checks for this image (launch-repo CI); mount ~/.ssh for Git SSH probe"
  echo "  help               This text"
}

check_prereqs_bootstrap() {
  local fail=0
  echo "=== Checking prerequisites ==="
  command -v yq    >/dev/null 2>&1 || { echo "  FAIL: yq"; fail=1; }
  command -v gh    >/dev/null 2>&1 || { echo "  FAIL: gh"; fail=1; }
  command -v git   >/dev/null 2>&1 || { echo "  FAIL: git"; fail=1; }
  command -v make  >/dev/null 2>&1 || { echo "  FAIL: make"; fail=1; }
  command -v docker >/dev/null 2>&1 || { echo "  FAIL: docker (needed for merge)"; fail=1; }
  [ -n "${GITHUB_TOKEN:-}" ] || { echo "  FAIL: GITHUB_TOKEN not set"; fail=1; }
  if [ "$fail" -eq 1 ]; then
    echo "Install missing tools. See stage0_launch README."
    exit 1
  fi
  echo "  Prerequisites OK"
}

preflight_bootstrap() {
  echo "=== Pre-flight checks ==="
  SPECIFICATIONS="${SPECIFICATIONS:?SPECIFICATIONS must be set}"
  LAUNCHPAD_DIR="${LAUNCHPAD_DIR:?LAUNCHPAD_DIR must be set}"
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

  [ -d "$LAUNCHPAD_DIR" ] || { echo "Error: LAUNCHPAD_DIR is not a directory: $LAUNCHPAD_DIR"; exit 1; }
  if (cd "$LAUNCHPAD_DIR" && git rev-parse 2>/dev/null); then
    echo "Error: LAUNCHPAD_DIR must be outside any .git repo: $LAUNCHPAD_DIR"
    exit 1
  fi

  echo "  ORG=$ORG SLUG=$SLUG BASE_PORT=$BASE_PORT"
  echo "  Pre-flight OK"
}

git_url_bootstrap() {
  echo "https://x-access-token:${GITHUB_TOKEN}@github.com/${ORG}/${SLUG}.git"
}

maybe_remove_stage0_launch_clone() {
  if [ "${STAGE0_LAUNCH_KEEP_REPO:-}" = "1" ] || [ "${STAGE0_LAUNCH_KEEP_REPO:-}" = "yes" ]; then
    echo "  STAGE0_LAUNCH_KEEP_REPO set — not removing stage0_launch clone."
    return 0
  fi
  if [ "${REMOVE_STAGE0_LAUNCH_CLONE:-}" != "1" ] && [ "${REMOVE_STAGE0_LAUNCH_CLONE:-}" != "yes" ]; then
    return 0
  fi
  local dir="${STAGE0_LAUNCH_REPO_DIR:-}"
  [ -n "$dir" ] || { echo "  REMOVE_STAGE0_LAUNCH_CLONE set but STAGE0_LAUNCH_REPO_DIR empty — skip."; return 0; }
  [ -d "$dir" ] || return 0
  if [ "$(basename "$dir")" != "stage0_launch" ]; then
    echo "  Refusing to remove $dir (basename is not stage0_launch)."
    return 0
  fi
  echo "  Removing stage0_launch clone at $dir (REMOVE_STAGE0_LAUNCH_CLONE=1)..."
  rm -rf "${dir:?}"
}

cmd_bootstrap() {
  check_prereqs_bootstrap
  preflight_bootstrap

  UMBRELLA_DIR="${LAUNCHPAD_DIR}/${SLUG}"
  export SERVICE_SOURCE_DIR="$LAUNCHPAD_DIR"

  echo ""
  echo "=== 1. Creating umbrella repo ==="
  gh repo create "${ORG}/${SLUG}" --template "agile-learning-institute/stage0_template_umbrella" --public || exit 1
  echo "  Waiting 5s for GitHub..."
  sleep 5

  echo ""
  echo "=== 2. Cloning umbrella to launchpad ==="
  (cd "$LAUNCHPAD_DIR" && git clone "$(git_url_bootstrap)" "$SLUG") || exit 1

  echo ""
  echo "=== 3. Merge specifications ==="
  (cd "$UMBRELLA_DIR" && make merge "$SPECIFICATIONS") || exit 1

  echo ""
  echo "=== 4. Copy specifications into umbrella ==="
  mkdir -p "$UMBRELLA_DIR/Specifications"
  local f
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
  export UMBRELLA_DIR
  umbrella_cmd_launch_all

  maybe_remove_stage0_launch_clone

  echo ""
  printf '\033[1;36m'
  echo "##############################################################################"
  echo "###                                                                        ###"
  echo "###   LAUNCH COMPLETE                                                      ###"
  echo "###                                                                        ###"
  echo "###   Next Steps:                                                          ###"
  echo "###   1.  cd $UMBRELLA_DIR                                                ###"
  echo "###   2.  make install && follow CONTRIBUTING for developer CLI          ###"
  echo "###   3.  <developer_cli> up all                                         ###"
  echo "###   4.  Open: http://localhost:${BASE_PORT}                              ###"
  echo "###                                                                        ###"
  echo "##############################################################################"
  printf '\033[0m'
}

cmd_validate() {
  local fail=0
  echo "=== Validating stage0_launch image prerequisites ==="
  echo ""
  echo "--- Build tools ---"
  command -v make >/dev/null 2>&1 && printf "make:    " && make --version | head -1 || { echo "  FAIL: make"; fail=1; }
  command -v node >/dev/null 2>&1 && printf "node:    " && node --version || { echo "  FAIL: node"; fail=1; }
  command -v npm >/dev/null 2>&1 && printf "npm:     " && npm --version || { echo "  FAIL: npm"; fail=1; }
  (vite --version 2>/dev/null || npx vite --version 2>/dev/null) >/dev/null && printf "vite:    " && (vite --version 2>/dev/null || npx vite --version 2>/dev/null) || { echo "  FAIL: vite"; fail=1; }
  echo ""
  echo "--- Python tools (3.12) ---"
  command -v pipenv >/dev/null 2>&1 && printf "pipenv:  " && pipenv --version || { echo "  FAIL: pipenv"; fail=1; }
  local PYTEST
  PYTEST=$(mktemp -d)
  if (cd "$PYTEST" && pipenv --python 3.12 install >/dev/null 2>&1 && pipenv run python -c "import sys; exit(0 if sys.version_info[:2] == (3, 12) else 1)" >/dev/null 2>&1); then
    echo "  pipenv+3.12: OK"
  else
    echo "  FAIL: pipenv cannot use Python 3.12"
    fail=1
  fi
  rm -rf "$PYTEST"
  echo ""
  echo "--- Container tools ---"
  command -v docker >/dev/null 2>&1 && printf "docker:  " && docker --version || { echo "  FAIL: docker"; fail=1; }
  docker buildx version >/dev/null 2>&1 && printf "buildx:  " && docker buildx version || { echo "  FAIL: docker buildx"; fail=1; }
  echo ""
  echo "--- GitHub & Git ---"
  [ -n "${GITHUB_TOKEN:-}" ] && printf "GITHUB_TOKEN: set\n" || { echo "  FAIL: GITHUB_TOKEN (set env var)"; fail=1; }
  command -v gh >/dev/null 2>&1 && printf "gh:      " && gh --version | head -1 || { echo "  FAIL: gh"; fail=1; }
  command -v git >/dev/null 2>&1 && printf "git:     " && git --version || { echo "  FAIL: git"; fail=1; }
  git config --global user.name >/dev/null 2>&1 || { echo "  FAIL: git config --global user.name"; fail=1; }
  git config --global user.email >/dev/null 2>&1 || { echo "  FAIL: git config --global user.email"; fail=1; }
  echo ""
  echo "--- Utilities ---"
  command -v jq >/dev/null 2>&1 && printf "jq:      " && jq --version || { echo "  FAIL: jq"; fail=1; }
  command -v yq >/dev/null 2>&1 && printf "yq:      " && yq --version || { echo "  FAIL: yq"; fail=1; }
  command -v curl >/dev/null 2>&1 && printf "curl:    " && curl --version | head -1 || { echo "  FAIL: curl"; fail=1; }
  command -v ssh >/dev/null 2>&1 && printf "ssh:     " && ssh -V 2>&1 || { echo "  FAIL: ssh"; fail=1; }
  echo ""
  echo "--- Git SSH (clone + push) ---"
  local GIT_SSH_TEST
  GIT_SSH_TEST=$(mktemp -d)
  if (git clone git@github.com:agile-learning-institute/testing.git "$GIT_SSH_TEST" >/dev/null 2>&1 && \
      cd "$GIT_SSH_TEST" && \
      echo " " >> README.md && \
      git add README.md && \
      git commit -m "validate: SSH clone/push test" >/dev/null 2>&1 && \
      git push >/dev/null 2>&1); then
    echo "  Git SSH: OK"
  else
    echo "  FAIL: Git SSH clone or push (mount ~/.ssh or skip in CI)"
    fail=1
  fi
  rm -rf "$GIT_SSH_TEST"
  echo ""
  if [ "$fail" -eq 1 ]; then
    echo "Validation failed."
    exit 1
  fi
  echo "=== All prerequisites validated ==="
}

main() {
  local sub="${1:-bootstrap}"
  case "$sub" in
    help|-h|--help)
      usage
      ;;
    bootstrap)
      shift || true
      cmd_bootstrap "$@"
      ;;
    launch-all)
      umbrella_cmd_launch_all
      ;;
    launch-services)
      umbrella_cmd_launch_services
      ;;
    clone-all)
      umbrella_cmd_clone_all
      ;;
    delete-services)
      umbrella_cmd_delete_services
      ;;
    delete-all)
      umbrella_cmd_delete_all
      ;;
    validate)
      cmd_validate
      ;;
    *)
      echo "Unknown subcommand: $sub"
      usage
      exit 1
      ;;
  esac
}

main "$@"
