---
name: ree-repo-scaffold
description: "Crea repo GitHub con CI/CD y apps/ K3s"
version: 1.0.0
author: Hermes
license: MIT
category: productivity
tags: [ree-repo, scaffold, github, gitops, cicd, branch-protection]
---

# ree-repo-scaffold — F3: Scaffolding del Repositorio

Crea el repositorio GitHub con estructura completa de proyecto siguiendo el modelo GitOps de `reevolutiva-infra`: `apps/<proyecto>/`, `src/`, `skills/`, `integrations/`, `docs/`, `scripts/`, CI/CD con branch protection y workflow anti-push a main.

## When to Use

- Desde `/ree-repo` orquestadora (F3), después de F2 Architect.
- "crear repo del proyecto", "hacer scaffolding", "configurar CI/CD".
- Trigger: el usuario quiere materializar la estructura del proyecto en GitHub.

## Procedure

### 1. Verificar prerequisitos

```bash
gh auth status  # debe retornar exitoso
```
Si falla, ejecutar skill `github-auth` antes de continuar.

### 2. Crear repo en GitHub

```bash
gh repo create reevolutiva/<repo> --private --clone
cd <repo>
```

### 3. Configurar branch protection ANTES del primer push

```bash
gh api /repos/reevolutiva/<repo>/branches/main/protection \
  -X PUT \
  -F required_pull_request_reviews=null \
  -F allow_force_pushes=false \
  -F allow_deletions=false \
  -F block_creations=false
```

### 4. Generar workflow block-push-main.yml

Crear `.github/workflows/block-push-main.yml`:

```yaml
name: Block Push to Main
on:
  push:
    branches: [main]
jobs:
  block:
    runs-on: ubuntu-latest
    if: ${{ !startsWith(github.event.head_commit.message, 'Merge pull request') }}
    steps:
      - name: Reject direct push
        run: |
          echo "❌ Push directo a main no permitido."
          echo "   Todo cambio debe entrar por PR desde una rama feat/ o fix/."
          echo "   Ver AGENTS.md → Flujo de trabajo."
          exit 1
```

El `if` evita que el workflow falle cuando el push es un merge de PR.

### 5. Generar CI/CD workflows

`.github/workflows/ci.yml`:
- Triggers: push a cualquier rama, PR a main
- Jobs: lint, typecheck, test
- Matrix de Node.js si aplica

`.github/workflows/deploy.yml`:
- Trigger: push a main (solo vía PR merge)
- Jobs: build Docker → push a ghcr.io/reevolutiva

### 6. Crear estructura de directorios

```
<repo>/
├── .github/workflows/   (ci.yml, deploy.yml, block-push-main.yml)
├── src/
│   ├── agents/
│   ├── pipeline/
│   ├── intake/
│   ├── api/
│   └── providers/
├── apps/<proyecto>/
│   ├── kustomization.yaml
│   ├── deployment.yaml     # o helmrelease.yaml
│   ├── service.yaml
│   ├── ingress.yaml        # ingressClassName: tailscale
│   └── externalsecret.yaml # secretStoreRef: azure-keyvault
├── skills/
├── integrations/
│   ├── hermes/
│   └── paperclip/
├── config/
├── docs/architecture/
├── scripts/
├── tests/
├── .env.example
├── .gitignore
├── .sops.yaml
├── package.json
├── tsconfig.json
├── docker-compose.yml
├── Dockerfile
├── AGENTS.md
└── README.md
```

### 7. Generar apps/<proyecto>/kustomization.yaml

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - deployment.yaml
  - service.yaml
  - ingress.yaml
  - externalsecret.yaml
```

### 8. Generar apps/<proyecto>/deployment.yaml

Con recursos, readinessProbe, nodeSelector (si aplica). La imagen debe referenciar `ghcr.io/reevolutiva/<proyecto>`.

### 9. Generar apps/<proyecto>/service.yaml

Con puerto del contenedor.

### 10. Generar apps/<proyecto>/ingress.yaml

```yaml
spec:
  ingressClassName: tailscale
```

### 11. Generar apps/<proyecto>/externalsecret.yaml

```yaml
spec:
  secretStoreRef:
    name: azure-keyvault
    kind: ClusterSecretStore
```

### 12. Generar package.json

Con dependencias inferidas de Fase 6 (`06-tech/arquitectura-tecnica.md`).

### 13. Generar .env.example

Solo nombres de variables con comentarios descriptivos. Nunca valores reales.

### 14. Gate F3

Jev Score: `incompleto`, `minimo`, `completo`, `sobreconstruido`.
Debe ser ≥ `completo`.

### 15. Commit inicial y push

```bash
git add -A
git commit -m "chore: scaffold inicial del proyecto"
git push origin main
```

## Jev Integration Points

| Punto | Primitivo | Pregunta |
|---|---|---|
| Cobertura CI/CD | noul | "Do the CI workflows cover linting, type checking, testing, and deployment?" |
| Conformidad GitOps | noul | "Does the scaffold follow the reevolutiva-infra GitOps model?" |
| Branch protection | noul | "Does the repo have branch protection AND block-push-main workflow?" |
| Gate F3 | score | Levels: `incompleto`, `minimo`, `completo`, `sobreconstruido`. State: lista de archivos generados. |

## Pitfalls

- **Branch protection antes del primer push**: aplicar `gh api` ANTES de `git push`. Si se pushea antes, main queda desprotegido.
- **block-push-main.yml con `if` correcto**: el `if: ${{ !startsWith(github.event.head_commit.message, 'Merge pull request') }}` es OBLIGATORIO. Sin él, los merges de PR también fallan.
- **Imagen en deployment.yaml**: usar `ghcr.io/reevolutiva/<proyecto>:latest` como placeholder hasta que CI genere la imagen real.
- **.env.example sin valores**: nunca incluir credenciales reales. Solo nombres de variables.
- **GitHub auth previo**: si `gh auth status` falla, ejecutar `github-auth` primero.
- **apps/ es source of truth**: los manifiestos viven en `apps/<proyecto>/` del repo del proyecto, no en `infrastructure/kubernetes/`.

## Verification

1. `gh api /repos/reevolutiva/<repo>/branches/main/protection` → `allow_force_pushes: false`, `allow_deletions: false`.
2. `.github/workflows/block-push-main.yml` existe con `if: ${{ !startsWith(...) }}`.
3. Estructura de directorios completa (src/, apps/<proyecto>/, integrations/, etc.).
4. `apps/<proyecto>/kustomization.yaml` referencia deployment, service, ingress, externalsecret.
5. `apps/<proyecto>/ingress.yaml` tiene `ingressClassName: tailscale`.
6. `apps/<proyecto>/externalsecret.yaml` referencia `ClusterSecretStore: azure-keyvault`.
7. CI/CD workflows existen (ci.yml + deploy.yml).
8. Commit inicial en main existe (creado vía PR o como commit inicial único).
9. `skills_list` muestra `ree-repo-scaffold` en categoría `productivity`.