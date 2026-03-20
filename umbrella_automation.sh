#!/usr/bin/env bash
# Umbrella automation: launch-all, launch-services, clone-all, delete-services, delete-all.
# Expects UMBRELLA_DIR (repo root) and SERVICE_SOURCE_DIR (parent directory; sibling repos live here).

umbrella_automation_load_env() {
  UMBRELLA_DIR="${UMBRELLA_DIR:?UMBRELLA_DIR is required}"
  SERVICE_SOURCE_DIR="${SERVICE_SOURCE_DIR:?SERVICE_SOURCE_DIR is required (launchpad parent)}"
  [ -d "$UMBRELLA_DIR" ] || { echo "Error: UMBRELLA_DIR is not a directory: $UMBRELLA_DIR"; exit 1; }
  [ -d "$SERVICE_SOURCE_DIR" ] || { echo "Error: SERVICE_SOURCE_DIR is not a directory: $SERVICE_SOURCE_DIR"; exit 1; }

  ROOT="$UMBRELLA_DIR"
  SPECS_DIR="${ROOT}/Specifications"
  ARCH_FILE="${SPECS_DIR}/architecture.yaml"
  PRODUCT_FILE="${SPECS_DIR}/product.yaml"

  [ -f "$PRODUCT_FILE" ] || { echo "Error: missing $PRODUCT_FILE"; exit 1; }
  [ -f "$ARCH_FILE" ] || { echo "Error: missing $ARCH_FILE"; exit 1; }

  SLUG=$(yq -r '.info.slug' "$PRODUCT_FILE")
  ORG=$(yq -r '.organization.git_org' "$PRODUCT_FILE")
  DOCKER_HOST=$(yq -r '.organization.docker_host' "$PRODUCT_FILE")

  [ -n "$SLUG" ] && [ "$SLUG" != "null" ] || { echo "Error: info.slug in product.yaml"; exit 1; }
  [ -n "$ORG" ] && [ "$ORG" != "null" ] || { echo "Error: organization.git_org in product.yaml"; exit 1; }
  [ -n "$DOCKER_HOST" ] && [ "$DOCKER_HOST" != "null" ] || { echo "Error: organization.docker_host in product.yaml"; exit 1; }

  SOURCE="$SERVICE_SOURCE_DIR"
  ALL_SERVICES=$(yq -r '.architecture.domains[].name' "$ARCH_FILE" | paste -sd' ' -)
}

umbrella_git_https_setup() {
  git config --global --unset-all url."https://@github.com/".insteadOf 2>/dev/null || true
  git config --global url."https://x-access-token:${GITHUB_TOKEN}@github.com/".insteadOf "https://github.com/"
}

umbrella_docker_login() {
  echo "$GITHUB_TOKEN" | docker login "$DOCKER_HOST" -u "$ORG" --password-stdin
}

# --- Interactive / CI confirmation ---
umbrella_confirm_delete_services() {
  if [ "${I_CONFIRM_DELETE_SERVICES:-}" = "yes" ] || [ "${I_CONFIRM_DELETE_SERVICES:-}" = "YES" ]; then
    [ "${I_CONFIRM_SLUG:-}" = "$SLUG" ] || { echo "Error: I_CONFIRM_SLUG must match product slug ($SLUG)"; exit 1; }
    return 0
  fi
  echo "WARNING: This will DELETE GitHub repos and packages for the selected services. Not reversible."
  read -r -p "Type the product slug ($SLUG) to confirm: " line
  [ "$line" = "$SLUG" ] || { echo "Aborted."; exit 1; }
}

umbrella_confirm_delete_all() {
  if [ "${I_CONFIRM_DELETE_ALL:-}" = "yes" ] || [ "${I_CONFIRM_DELETE_ALL:-}" = "YES" ]; then
    [ "${I_CONFIRM_SLUG:-}" = "$SLUG" ] || { echo "Error: I_CONFIRM_SLUG must match product slug ($SLUG)"; exit 1; }
    return 0
  fi
  echo "WARNING: This will DELETE the umbrella repo ($ORG/$SLUG), its package, and ALL service repos and packages. Not reversible."
  read -r -p "Type DELETE ALL $SLUG to confirm: " line
  [ "$line" = "DELETE ALL $SLUG" ] || { echo "Aborted."; exit 1; }
}

# $1 = space-separated domain names
umbrella_launch_services() {
  local services_list="$1"
  [ -n "${GITHUB_TOKEN:-}" ] || { echo "Error: GITHUB_TOKEN required"; exit 1; }

  echo "Configuring git and docker for push..."
  umbrella_docker_login
  umbrella_git_https_setup

  local svc
  for svc in $services_list; do
    [ -z "$svc" ] && continue
    local REPO_LINES
    REPO_LINES=$(yq -r '.architecture.domains[] | select(.name == "'"$svc"'") | .repos[] | select(.type == "api" or .type == "spa") | (.name + "|" + .template + "|" + (.publish // ""))' "$ARCH_FILE" 2>/dev/null) || true
    [ -z "$REPO_LINES" ] && continue
    echo "--- Domain: $svc ---"
    while IFS='|' read -r repo_name template publish; do
      [ -z "$repo_name" ] && continue
      local REPO_FULL="${SLUG}_${repo_name}"
      local REPO="${ORG}/${REPO_FULL}"
      echo ""
      echo "##############################################################################"
      echo "###   Starting Repo $REPO_FULL"
      echo "##############################################################################"
      echo "  Creating $REPO from template $template"
      rm -rf "${SOURCE:?}/${REPO_FULL}"
      (cd "$SOURCE" && gh repo create "$REPO" --template "$template" --public) || { echo "Failed: $REPO"; exit 1; }
      echo "  Waiting for repo to be ready..."; sleep 5
      echo "  Cloning $REPO"
      (cd "$SOURCE" && git clone "https://x-access-token:${GITHUB_TOKEN}@github.com/${REPO}.git" "$REPO_FULL") || { echo "Failed clone: $REPO"; exit 1; }
      echo "  Merging $REPO_FULL"
      (cd "${SOURCE}/${REPO_FULL}" && SERVICE_NAME="$svc" make merge "$SPECS_DIR") || { echo "Failed merge: $REPO_FULL"; exit 1; }
      if [ -n "$publish" ]; then
        echo "  Build-package & publish-package $REPO_FULL ($publish)"
        (cd "${SOURCE}/${REPO_FULL}" &&
          case "$publish" in
            make)   make build-package && make publish-package ;;
            npm)    npm run build-package && npm run publish-package ;;
            pipenv) pipenv run build-package && pipenv run publish-package ;;
            *)      echo "Unknown publish: $publish"; exit 1 ;;
          esac
        ) || { echo "Failed build: $REPO_FULL"; exit 1; }
      fi
      echo "  Commit & push $REPO_FULL"
      (cd "${SOURCE}/${REPO_FULL}" &&
        git add -A && git commit -m "Template Merge Processing Complete" && git push origin main) || { echo "Failed push: $REPO_FULL"; exit 1; }
      echo ""
      echo "##############################################################################"
      echo "###   Repo $REPO_FULL Shipped"
      echo "##############################################################################"
    done <<< "$REPO_LINES"
  done
  echo "Launch complete."
}

# $1 = space-separated domain names — clone existing repos and build (no publish)
umbrella_clone_all_services() {
  local services_list="$1"
  umbrella_git_https_setup

  local svc
  for svc in $services_list; do
    [ -z "$svc" ] && continue
    local REPO_LINES
    REPO_LINES=$(yq -r '.architecture.domains[] | select(.name == "'"$svc"'") | .repos[] | select(.type == "api" or .type == "spa") | (.name + "|" + (.publish // ""))' "$ARCH_FILE" 2>/dev/null) || true
    [ -z "$REPO_LINES" ] && continue
    echo "--- Domain: $svc ---"
    while IFS='|' read -r repo_name publish; do
      [ -z "$repo_name" ] && continue
      local REPO_FULL="${SLUG}_${repo_name}"
      local REPO="${ORG}/${REPO_FULL}"
      echo "  Clean local $REPO_FULL"
      rm -rf "${SOURCE:?}/${REPO_FULL}"
      echo "  Clone $REPO"
      (cd "$SOURCE" && git clone "https://github.com/${REPO}.git" "$REPO_FULL") || { echo "Failed clone: $REPO"; exit 1; }
      echo "  Build $REPO_FULL ($publish)"
      (cd "${SOURCE}/${REPO_FULL}" && (
        case "$publish" in
          make)   make build-package ;;
          npm)    npm run build-package ;;
          pipenv) pipenv run build-package ;;
          *)      echo "Skipped (no publish recipe): $REPO_FULL" ;;
        esac
      ) || true)
    done <<< "$REPO_LINES"
  done
  echo "clone-all complete."
}

# $1 = space-separated domain names
umbrella_delete_services_only() {
  local services_list="$1"
  local svc
  for svc in $services_list; do
    [ -z "$svc" ] && continue
    local REPO_LINES
    REPO_LINES=$(yq -r '.architecture.domains[] | select(.name == "'"$svc"'") | .repos[] | select(.type == "api" or .type == "spa") | (.name + "|" + (.publish // ""))' "$ARCH_FILE" 2>/dev/null) || true
    [ -z "$REPO_LINES" ] && continue
    echo "--- Domain: $svc ---"
    while IFS='|' read -r repo_name publish; do
      [ -z "$repo_name" ] && continue
      local REPO_FULL="${SLUG}_${repo_name}"
      local REPO="${ORG}/${REPO_FULL}"
      if [ -d "${SOURCE}/${REPO_FULL}" ] && [ -n "$publish" ]; then
        echo "  Delete-package $REPO_FULL ($publish)"
        (cd "${SOURCE}/${REPO_FULL}" && (
          case "$publish" in
            make)   make delete-package ;;
            npm)    npm run delete-package ;;
            pipenv) pipenv run delete-package ;;
            *)      ;;
          esac
        ) 2>/dev/null || true)
      fi
      echo "  Delete GitHub repo $REPO"
      gh repo delete "$REPO" --yes 2>/dev/null || echo "  (repo may not exist)"
      echo "  Remove local $REPO_FULL"
      rm -rf "${SOURCE}/${REPO_FULL}"
    done <<< "$REPO_LINES"
  done
  echo "Delete services complete."
}

umbrella_cmd_launch_all() {
  umbrella_automation_load_env
  [ -n "${GITHUB_TOKEN:-}" ] || { echo "Error: GITHUB_TOKEN required"; exit 1; }
  local START END
  START=$(date +%s)
  (cd "$ROOT" && make build-package && make publish-package)
  umbrella_launch_services "$ALL_SERVICES"
  END=$(date +%s)
  echo "Launch Completed - Started at $START To $END Duration: $((END - START)) Seconds"
}

umbrella_cmd_launch_services() {
  umbrella_automation_load_env
  local services_list="${SERVICES:?SERVICES required (space-separated domain names)}"
  umbrella_launch_services "$services_list"
}

umbrella_cmd_clone_all() {
  umbrella_automation_load_env
  umbrella_clone_all_services "$ALL_SERVICES"
}

umbrella_cmd_delete_services() {
  umbrella_automation_load_env
  umbrella_confirm_delete_services
  local services_list="${SERVICES:?SERVICES required (space-separated domain names)}"
  umbrella_delete_services_only "$services_list"
}

umbrella_cmd_delete_all() {
  umbrella_automation_load_env
  umbrella_confirm_delete_all
  local START END
  START=$(date +%s)
  umbrella_delete_services_only "$ALL_SERVICES"
  echo "  Delete umbrella package (Makefile delete-package)"
  (cd "$ROOT" && make delete-package) 2>/dev/null || true
  echo "  Delete GitHub umbrella repo $ORG/$SLUG"
  gh repo delete "$ORG/$SLUG" --yes 2>/dev/null || echo "  (umbrella repo may not exist)"
  END=$(date +%s)
  echo "Delete-all completed - Started at $START To $END Duration: $((END - START)) Seconds"
}
