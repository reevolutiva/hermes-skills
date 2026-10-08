#!/usr/bin/env bash
# setup.sh — Instalacion del tap reevolutiva/hermes-skills
set -euo pipefail
REPO="reevolutiva/hermes-skills"
echo "==> Agregando tap ${REPO}..."
hermes skills tap add "${REPO}" 2>/dev/null || echo "   (tap ya existe, continuando)"

echo "==> Instalando skills del catalogo..."
for skill in ree-producto ree-learn reevolutiva-infra-gitops wordpress-bedrock-migration wordpress-performance-diagnosis; do
    echo "   ${skill}..."
    hermes skills install "reevolutiva/skills/${skill}" 2>/dev/null || echo "   (${skill} ya instalada)"
done

echo "==> Recargando skills..."
hermes skills reload
echo "==> Done. Skills disponibles:"
hermes skills list --tap reevolutiva/hermes-skills
