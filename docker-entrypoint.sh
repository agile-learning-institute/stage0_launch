#!/bin/sh
set -e
# Inside the image, keep GITHUB_* and GH_* in sync so callers only pass one pair.
[ -z "$GITHUB_TOKEN" ] && [ -n "$GH_TOKEN" ] && export GITHUB_TOKEN="$GH_TOKEN"
[ -z "$GH_TOKEN" ] && [ -n "$GITHUB_TOKEN" ] && export GH_TOKEN="$GITHUB_TOKEN"
[ -z "$GITHUB_USERNAME" ] && [ -n "$GH_USERNAME" ] && export GITHUB_USERNAME="$GH_USERNAME"
[ -z "$GH_USERNAME" ] && [ -n "$GITHUB_USERNAME" ] && export GH_USERNAME="$GITHUB_USERNAME"
exec "$@"
