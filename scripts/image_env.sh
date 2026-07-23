#!/usr/bin/env bash
# Shared image/registry configuration sourced by build_images.sh / push_images.sh.
# Single source of truth for the version is yaguwiseai.__version__.
set -euo pipefail

# Registry + namespace. Defaults to GHCR under the GitHub owner (lowercased, as
# GHCR requires). Override YAGUWISEAI_REGISTRY / YAGUWISEAI_IMAGE_NAMESPACE for a
# different registry (Docker Hub, a private registry, etc.).
YAGUWISEAI_REGISTRY="${YAGUWISEAI_REGISTRY:-ghcr.io}"
YAGUWISEAI_IMAGE_NAMESPACE="${YAGUWISEAI_IMAGE_NAMESPACE:-mhhamdan}"

# Version from the package (the one true source); allow override for CI tags.
_pkg_version() {
  python3 - <<'PY' 2>/dev/null || echo "0.0.0"
try:
    import yaguwiseai; print(yaguwiseai.__version__)
except Exception:
    print("0.0.0")
PY
}
YAGUWISEAI_VERSION="${YAGUWISEAI_VERSION:-$(_pkg_version)}"

# Short git sha for an immutable, traceable tag (falls back to 'nogit').
YAGUWISEAI_GIT_SHA="${YAGUWISEAI_GIT_SHA:-$(git rev-parse --short HEAD 2>/dev/null || echo nogit)}"

# Minor series tag (X.Y) for "track the latest patch of a minor".
_minor() { echo "$1" | awk -F. '{print $1"."$2}'; }
YAGUWISEAI_VERSION_MINOR="$(_minor "$YAGUWISEAI_VERSION")"

# The three first-party images: <local-name>:<dockerfile>:<context>
# (context is relative to repo root).
YAGUWISEAI_IMAGES=(
  "yaguwiseai-api:containers/api.Dockerfile:."
  "yaguwiseai-web:containers/web.Dockerfile:web"
  "yaguwiseai-caddy:containers/caddy.Dockerfile:."
)

# Full registry path for an image's component name, e.g. api -> ghcr.io/ns/yaguwiseai-api
registry_ref() {  # $1 = local image name (yaguwiseai-api), $2 = tag
  echo "${YAGUWISEAI_REGISTRY}/${YAGUWISEAI_IMAGE_NAMESPACE}/${1}:${2}"
}

# The tag set every image gets: exact version, minor series, git sha, and latest.
image_tags() {
  echo "$YAGUWISEAI_VERSION" "$YAGUWISEAI_VERSION_MINOR" "$YAGUWISEAI_GIT_SHA" "latest"
}

export YAGUWISEAI_REGISTRY YAGUWISEAI_IMAGE_NAMESPACE YAGUWISEAI_VERSION \
  YAGUWISEAI_VERSION_MINOR YAGUWISEAI_GIT_SHA
