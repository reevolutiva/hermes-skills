#!/usr/bin/env bash
# update.sh — Actualizacion del tap y skills
set -euo pipefail
echo "==> Actualizando skills via tap reevolutiva/hermes-skills..."
hermes skills update

echo "==> Skills disponibles:"
hermes skills list
echo "==> Done."
