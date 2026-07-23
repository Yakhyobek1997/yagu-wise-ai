#!/usr/bin/env bash
# Build the YaguWiseAi container images (api, web, caddy) with version + OCI labels
# and a full tag set (X.Y.Z, X.Y, <git-sha>, latest), under both the local name
# and the registry path. Podman-first; works with docker too. See ADR-0017.
#
#   ./scripts/build_images.sh                 # build all, tag local + registry
#   YAGUWISEAI_VERSION=0.2.0 ./scripts/build_images.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=scripts/image_env.sh
source scripts/image_env.sh

ENGINE="${YAGUWISEAI_CONTAINER_ENGINE:-podman}"
command -v "$ENGINE" >/dev/null 2>&1 || ENGINE=docker

SOURCE_URL="https://github.com/${YAGUWISEAI_IMAGE_NAMESPACE}/yaguwiseai"
BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo unknown)"

echo "→ engine=${ENGINE} version=${YAGUWISEAI_VERSION} sha=${YAGUWISEAI_GIT_SHA}"
echo "→ registry=${YAGUWISEAI_REGISTRY}/${YAGUWISEAI_IMAGE_NAMESPACE}"

for spec in "${YAGUWISEAI_IMAGES[@]}"; do
  name="${spec%%:*}"; rest="${spec#*:}"
  dockerfile="${rest%%:*}"; context="${rest#*:}"

  # First tag arg + OCI labels; web needs its proxy build-arg.
  args=(build -f "$dockerfile"
        --label "org.opencontainers.image.title=${name}"
        --label "org.opencontainers.image.version=${YAGUWISEAI_VERSION}"
        --label "org.opencontainers.image.revision=${YAGUWISEAI_GIT_SHA}"
        --label "org.opencontainers.image.source=${SOURCE_URL}"
        --label "org.opencontainers.image.created=${BUILD_DATE}"
        --label "org.opencontainers.image.licenses=Apache-2.0")
  [ "$name" = "yaguwiseai-web" ] && args+=(--build-arg "NEXT_PUBLIC_API_BASE=${NEXT_PUBLIC_API_BASE:-/api}")
  [ "$name" = "yaguwiseai-caddy" ] && args+=(--build-arg "YAGUWISEAI_CERT_HOST=${YAGUWISEAI_CERT_HOST:-localhost}")

  # Apply every tag (local name + registry ref).
  for t in $(image_tags); do
    args+=(-t "${name}:${t}" -t "$(registry_ref "$name" "$t")")
  done

  echo "→ building ${name} (${dockerfile}) …"
  "$ENGINE" "${args[@]}" "$context"
done

echo "✓ built + tagged:"
for spec in "${YAGUWISEAI_IMAGES[@]}"; do
  name="${spec%%:*}"
  echo "    $(registry_ref "$name" "$YAGUWISEAI_VERSION")  (+ ${YAGUWISEAI_VERSION_MINOR}, ${YAGUWISEAI_GIT_SHA}, latest)"
done
