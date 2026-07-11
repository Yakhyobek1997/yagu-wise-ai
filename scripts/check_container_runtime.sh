#!/usr/bin/env bash
# Detect the available Podman Compose command and print it on stdout.
# Auralynq is Podman-first and does NOT require Docker.
set -euo pipefail

if podman compose version >/dev/null 2>&1; then
  echo "podman compose"
elif command -v podman-compose >/dev/null 2>&1; then
  echo "podman-compose"
else
  echo "Podman Compose is required. Install either 'podman compose' (podman >= 4.x) or 'podman-compose'." >&2
  echo "  Fedora/RHEL:  sudo dnf install podman-compose" >&2
  echo "  Debian/Ubuntu: sudo apt install podman-compose" >&2
  echo "  pip:           pipx install podman-compose" >&2
  exit 1
fi
