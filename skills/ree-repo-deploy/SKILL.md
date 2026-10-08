---
name: ree-repo-deploy
description: "Registra proyecto en Flux clusters/apps.yaml"
version: 1.0.0
author: Hermes
license: MIT
category: productivity
tags: [ree-repo, deploy, flux, gitops, kustomization, akv, k3s]
---

# ree-repo-deploy — F4: Registro Flux en reevolutiva-infra

Registra el proyecto en `clusters/<cluster>/apps.yaml` de `reevolutiva-infra` para que Flux reconcilie automáticamente los manifiestos desde `apps/<proyecto>/`. Esto define en qué máquina corre el proyecto.

## When to Use

- Desde `/ree-repo` orquestadora (F4), después de F3 Scaffold.
- "registrar en Flux", "agregar al cluster", "configurar deploy GitOps".
- Trigger: el proyecto ya tiene scaffold y se necesita que Flux lo reconcilie.

## Procedure

### 1. Determinar cluster destino

- `imac27` — desarrollo (amd64, control-plane)
- `produccion` — producción (arm64, worker con taint `env=prod:NoSchedule`)

Preguntar al usuario o inferir de la fase de desarrollo.

### 2. Generar bloque Kustomization

Agregar al final de `clusters/<cluster>/apps.yaml` en `reevolutiva-infra`:

```yaml
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: apps-<proyecto>
  namespace: flux-system
spec:
  dependsOn:
    - name: infra-configs
  interval: 10m
  sourceRef:
    kind: GitRepository
    name: flux-system
  path: ./apps/<proyecto>
  prune: true
  wait: true
```

### 3. Agregar patches si el proyecto necesita nodeSelector

Solo para cluster `produccion` con taint:

```yaml
  patches:
    - target:
        kind: Deployment
        name: <proyecto>
      patch: |-
        - op: add
          path: /spec/template/spec/nodeSelector
          value:
            reevolutiva.io/clase: produccion
        - op: add
          path: /spec/template/spec/tolerations
          value:
            - key: env
              operator: Equal
              value: prod
              effect: NoSchedule
```

### 4. Generar apps/<proyecto>/ según tipo

| Tipo | Archivos | Referencia |
|---|---|---|
| HelmRelease (chart oficial) | `helmrelease.yaml` + `ingress.yaml` + `externalsecret.yaml` | `apps/litellm/` |
| Deployment plano (custom) | `deployment.yaml` + `service.yaml` + `ingress.yaml` + `externalsecret.yaml` | `apps/ai-services/` |
| HelmRelease + extras | `helmrelease.yaml` + `pvc.yaml` + `ingress.yaml` + `externalsecret.yaml` | `apps/wordpress-reevolutiva/` |
| Ninguno (sin K3s) | sin carpeta `apps/` | `apps/paperclip/` |

### 5. Verificar HelmRepository (si aplica)

Si se usa HelmRelease, verificar que el `HelmRepository` está registrado en `infrastructure/configs/helm-repositories.yaml`. Si no, agregarlo con PR en `reevolutiva-infra`.

### 6. Verificar ExternalSecret

Los `remoteRef.key` deben existir en AKV `giorgio` con nombres `<namespace>-<service>-<key>`.

### 7. Gate F4

Jev Noul: ≥ 0.7.

### 8. Abrir PR en reevolutiva-infra

PR separado con el bloque `Kustomization`. No commit directo a main.

## Jev Integration Points

| Punto | Primitivo | Pregunta |
|---|---|---|
| Registro Flux canónico | noul | "Does the Flux Kustomization block follow the canonical reevolutiva-infra pattern with dependsOn, interval, path, prune, and wait?" |
| Secrets correctos | noul | "Do the ExternalSecrets reference the correct ClusterSecretStore and existing AKV keys?" |
| Gate F4 | noul | Threshold ≥ 0.7. Evalúa conformidad del registro Flux y secrets. |

## Pitfalls

- **Apps/ no es el output de F4**: los manifiestos en `apps/<proyecto>/` se generaron en F3. F4 solo modifica `clusters/<cluster>/apps.yaml`.
- **PR, no commit directo**: F4 abre un PR en `reevolutiva-infra`. Nunca commit directo a main.
- **HelmRepository debe existir**: si se usa HelmRelease, el chart repository debe estar registrado en `infrastructure/configs/helm-repositories.yaml`.
- **ExternalSecret keys en AKV**: verificar que los `remoteRef.key` existen en AKV `giorgio` antes del deploy.
- **nodeSelector solo en produccion**: el taint `env=prod:NoSchedule` requiere tolerations explícitas.
- **Tailscale, no público**: la exposición es Tailscale-only por defecto. Solo Cloudflare Tunnel si se requiere webhook público.

## Verification

1. `clusters/<cluster>/apps.yaml` contiene bloque `apps-<proyecto>`.
2. Bloque incluye `dependsOn: infra-configs`, `interval: 10m`, `prune: true`, `wait: true`.
3. Si es cluster `produccion`, incluye patches con `nodeSelector` + `tolerations`.
4. `apps/<proyecto>/` contiene archivos según el tipo elegido.
5. `externalsecret.yaml` referencia `ClusterSecretStore: azure-keyvault`.
6. PR abierto en `reevolutiva-infra` (no commit directo).
7. Gate F4 ≥ 0.7.
8. `skills_list` muestra `ree-repo-deploy` en categoría `productivity`.