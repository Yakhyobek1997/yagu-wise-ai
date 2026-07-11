#!/usr/bin/env bash
# Build the Auralynq container images (api, web, caddy) with version + OCI labels
# and a full tag set (X.Y.Z, X.Y, <git-sha>, latest), under both the local name
# and the registry path. Podman-first; works with docker too. See ADR-0017.
#
#   ./scripts/build_images.sh                 # build all, tag local + registry
#   AURALYNQ_VERSION=0.2.0 ./scripts/build_images.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=scripts/image_env.sh
source scripts/image_env.sh

ENGINE="${AURALYNQ_CONTAINER_ENGINE:-podman}"
command -v "$ENGINE" >/dev/null 2>&1 || ENGINE=docker

SOURCE_URL="https://github.com/${AURALYNQ_IMAGE_NAMESPACE}/auralynq"
BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo unknown)"

echo "→ engine=${ENGINE} version=${AURALYNQ_VERSION} sha=${AURALYNQ_GIT_SHA}"
echo "→ registry=${AURALYNQ_REGISTRY}/${AURALYNQ_IMAGE_NAMESPACE}"

for spec in "${AURALYNQ_IMAGES[@]}"; do
  name="${spec%%:*}"; rest="${spec#*:}"
  dockerfile="${rest%%:*}"; context="${rest#*:}"

  # First tag arg + OCI labels; web needs its proxy build-arg.
  args=(build -f "$dockerfile"
        --label "org.opencontainers.image.title=${name}"
        --label "org.opencontainers.image.version=${AURALYNQ_VERSION}"
        --label "org.opencontainers.image.revision=${AURALYNQ_GIT_SHA}"
        --label "org.opencontainers.image.source=${SOURCE_URL}"
        --label "org.opencontainers.image.created=${BUILD_DATE}"
        --label "org.opencontainers.image.licenses=Apache-2.0")
  [ "$name" = "auralynq-web" ] && args+=(--build-arg "NEXT_PUBLIC_API_BASE=${NEXT_PUBLIC_API_BASE:-/api}")
  [ "$name" = "auralynq-caddy" ] && args+=(--build-arg "AURALYNQ_CERT_HOST=${AURALYNQ_CERT_HOST:-localhost}")

  # Apply every tag (local name + registry ref).
  for t in $(image_tags); do
    args+=(-t "${name}:${t}" -t "$(registry_ref "$name" "$t")")
  done

  echo "→ building ${name} (${dockerfile}) …"
  "$ENGINE" "${args[@]}" "$context"
done

echo "✓ built + tagged:"
for spec in "${AURALYNQ_IMAGES[@]}"; do
  name="${spec%%:*}"
  echo "    $(registry_ref "$name" "$AURALYNQ_VERSION")  (+ ${AURALYNQ_VERSION_MINOR}, ${AURALYNQ_GIT_SHA}, latest)"
done
