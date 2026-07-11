#!/usr/bin/env bash
# Shared image/registry configuration sourced by build_images.sh / push_images.sh.
# Single source of truth for the version is auralynq.__version__.
set -euo pipefail

# Registry + namespace. Defaults to GHCR under the GitHub owner (lowercased, as
# GHCR requires). Override AURALYNQ_REGISTRY / AURALYNQ_IMAGE_NAMESPACE for a
# different registry (Docker Hub, a private registry, etc.).
AURALYNQ_REGISTRY="${AURALYNQ_REGISTRY:-ghcr.io}"
AURALYNQ_IMAGE_NAMESPACE="${AURALYNQ_IMAGE_NAMESPACE:-mhhamdan}"

# Version from the package (the one true source); allow override for CI tags.
_pkg_version() {
  python3 - <<'PY' 2>/dev/null || echo "0.0.0"
try:
    import auralynq; print(auralynq.__version__)
except Exception:
    print("0.0.0")
PY
}
AURALYNQ_VERSION="${AURALYNQ_VERSION:-$(_pkg_version)}"

# Short git sha for an immutable, traceable tag (falls back to 'nogit').
AURALYNQ_GIT_SHA="${AURALYNQ_GIT_SHA:-$(git rev-parse --short HEAD 2>/dev/null || echo nogit)}"

# Minor series tag (X.Y) for "track the latest patch of a minor".
_minor() { echo "$1" | awk -F. '{print $1"."$2}'; }
AURALYNQ_VERSION_MINOR="$(_minor "$AURALYNQ_VERSION")"

# The three first-party images: <local-name>:<dockerfile>:<context>
# (context is relative to repo root).
AURALYNQ_IMAGES=(
  "auralynq-api:containers/api.Dockerfile:."
  "auralynq-web:containers/web.Dockerfile:web"
  "auralynq-caddy:containers/caddy.Dockerfile:."
)

# Full registry path for an image's component name, e.g. api -> ghcr.io/ns/auralynq-api
registry_ref() {  # $1 = local image name (auralynq-api), $2 = tag
  echo "${AURALYNQ_REGISTRY}/${AURALYNQ_IMAGE_NAMESPACE}/${1}:${2}"
}

# The tag set every image gets: exact version, minor series, git sha, and latest.
image_tags() {
  echo "$AURALYNQ_VERSION" "$AURALYNQ_VERSION_MINOR" "$AURALYNQ_GIT_SHA" "latest"
}

export AURALYNQ_REGISTRY AURALYNQ_IMAGE_NAMESPACE AURALYNQ_VERSION \
  AURALYNQ_VERSION_MINOR AURALYNQ_GIT_SHA
