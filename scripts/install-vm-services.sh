#!/usr/bin/env bash
# install-vm-services.sh — Instalacion en vm-services
set -euo pipefail

HERMES_HOME="/home/giolapietra/.hermes"
SKILLS_DIR="${HERMES_HOME}/skills"

echo "==> Verificando Hermes Agent en vm-services..."
systemctl is-active hermes-gateway-atlas.service hermes.service 2>/dev/null || {
    echo "ERR: Hermes no esta corriendo. Levantalo primero."
    exit 1
}

echo "==> Agregando tap reevolutiva/hermes-skills..."
hermes skills tap add reevolutiva/hermes-skills 2>/dev/null || echo "   (tap ya existe)"

echo "==> Instalando skills..."
for skill in ree-producto ree-learn reevolutiva-infra-gitops wordpress-bedrock-migration wordpress-performance-diagnosis; do
    echo "   ${skill}..."
    hermes skills install "reevolutiva/hermes-skills/skills/${skill}" 2>/dev/null || echo "   (ya instalada)"
done

echo "==> Recargando..."
hermes skills reload

echo "==> Verificando..."
hermes skills list --tap reevolutiva/hermes-skills

echo "==> Done. Skills corporativas instaladas en vm-services."
