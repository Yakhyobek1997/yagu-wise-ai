#!/usr/bin/env bash
# Push the Auralynq images to the registry (default GHCR). Pushes the full tag set
# per image. Requires a prior `registry login`; prints clear guidance if absent.
# See ADR-0017.
#
#   echo "$GHCR_PAT" | podman login ghcr.io -u <user> --password-stdin
#   ./scripts/push_images.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=scripts/image_env.sh
source scripts/image_env.sh

ENGINE="${AURALYNQ_CONTAINER_ENGINE:-podman}"
command -v "$ENGINE" >/dev/null 2>&1 || ENGINE=docker

# Verify we can authenticate to the registry before attempting pushes.
if ! "$ENGINE" login "$AURALYNQ_REGISTRY" --get-login >/dev/null 2>&1; then
  cat >&2 <<EOF
✗ Not logged in to ${AURALYNQ_REGISTRY}. Log in first, e.g. for GHCR:

    echo "\$GHCR_PAT" | ${ENGINE} login ${AURALYNQ_REGISTRY} -u <github-user> --password-stdin

  (PAT needs the 'write:packages' scope.) CI publishes automatically on git tags
  via .github/workflows/release.yml — no manual login needed there.
EOF
  exit 1
fi

for spec in "${AURALYNQ_IMAGES[@]}"; do
  name="${spec%%:*}"
  for t in $(image_tags); do
    ref="$(registry_ref "$name" "$t")"
    echo "→ pushing ${ref}"
    "$ENGINE" push "$ref"
  done
done

echo "✓ pushed all images to ${AURALYNQ_REGISTRY}/${AURALYNQ_IMAGE_NAMESPACE} (version ${AURALYNQ_VERSION})"
