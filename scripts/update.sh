#!/usr/bin/env bash
# update.sh — Actualizacion del tap y skills
set -euo pipefail
echo "==> Recargando tap reevolutiva/hermes-skills..."
hermes skills reload

echo "==> Skills actualizadas:"
hermes skills list --tap reevolutiva/hermes-skills
echo "==> Done."
