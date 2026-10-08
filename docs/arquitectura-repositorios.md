# Arquitectura de repositorios y empaquetamiento — Hermes/Paperclip en vm-services

## Diagnóstico

Actualmente existen **3 repositorios GitHub** con responsabilidades no completamente delimitadas:

| Repo | Responsabilidad actual | Solapamiento |
|---|---|---|
| `reevolutiva/hermes-skills` | Skills corporativas (tap) | `integrations/hermes/config.yaml` y `scripts/backup-agentes.sh` viven en `reevolutiva-infra`, no acá |
| `reevolutiva/reevolutiva-infra` | GitOps Flux + config de agentes + scripts de infra | Contiene `integrations/hermes/`, `integrations/paperclip/`, `scripts/backup-agentes.sh` — eso es harness de agentes, no infraestructura |
| `<proyecto>` (repo destino de /ree-repo) | Código del proyecto + harness | Recibe `integrations/`, `apps/<proyecto>/`, `scripts/setup.sh` desde /ree-repo |

**Problema:** `reevolutiva-infra` mezcla infraestructura (Flux, K3s, AKV) con harness de agentes (config hermes, skills, backup). Eso genera acoplamiento: cambiar la config de un agente requiere tocar el repo de infraestructura.

## Arquitectura propuesta

### Principios

1. **Separación de responsabilidades:** infraestructura ≠ harness de agentes ≠ código de proyecto
2. **Source of truth único por artefacto:** cada archivo vive en exactamente un repo
3. **El tap es el catálogo, no el runtime:** `hermes-skills` distribuye skills; la config de runtime (modelos, providers, API keys) va en el proyecto o en infra
4. **Restore-path comprobable:** `scripts/setup.sh` de cada proyecto debe poder recrear el ambiente desde cero usando solo su repo + AKV + backup

### Repositorios y sus responsabilidades

```
reevolutiva/hermes-skills (TAP — catálogo corporativo)
├── skills/                     # Skills reutilizables (profile_or_tap)
│   ├── ree-learn/
│   ├── ree-producto/
│   ├── ree-repo/               # (próximamente)
│   └── ...
├── .github/workflows/
│   ├── block-push-main.yml     # Anti push directo a main
│   └── validate-skills.yml     # CI: formato, description≤60, secretos
├── scripts/
│   ├── setup.sh                # Instalación del tap en una máquina nueva
│   └── install-vm-services.sh  # Instalación específica en vm-services
├── AGENTS.md                   # Reglas de desarrollo del tap
└── README.md                   # Catálogo de skills disponibles

reevolutiva/reevolutiva-infra (GITOPS — infraestructura compartida)
├── clusters/                   # Entrypoints Flux por clúster
│   └── <cluster>/
│       └── apps.yaml           # Registro Kustomization por proyecto
├── infrastructure/             # Controllers, storage, namespaces
│   └── configs/
│       ├── helm-repositories.yaml
│       ├── namespaces.yaml
│       └── cluster-secret-store.yaml  # AKV
├── apps/                       # Workloads compartidos (no de un proyecto)
│   ├── ai-services/            # Ollama
│   ├── litellm/                # LiteLLM
│   ├── databases/              # PostgreSQL, Redis
│   ├── monitoring/             # Prometheus, Grafana
│   └── ...
├── Makefile                    # make health, make nodo-verificar
├── AGENTS.md                   # Contexto operativo del clúster
└── README.md

reevolutiva/<proyecto> (PROYECTO — código + harness específico)
├── src/                        # Código fuente
├── apps/<proyecto>/            # Manifiestos K3s (HelmRelease o Deployment)
│   ├── kustomization.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml            # Tailscale
│   └── externalsecret.yaml     # → AKV
├── integrations/               # Harness de agentes (PROYECTO, no infra)
│   ├── hermes/
│   │   ├── config.yaml         # Modelos y providers del proyecto
│   │   ├── env.template        # Variables → AKV
│   │   └── skills/             # Project-local skills
│   └── paperclip/
│       ├── config.yaml         # Paperclip context del proyecto
│       └── skills/             # Skills de Paperclip
├── scripts/
│   └── setup.sh                # Restore path: clone → AKV → backup → systemd
├── AGENTS.md                   # Stack, convenciones, flujo de trabajo
├── README.md
├── CHECKLIST.md                # DoD verification
└── package.json / tsconfig.json
```

### Lo que se MUEVE de reevolutiva-infra a su lugar correcto

| Archivo actual | Responsabilidad real | Destino |
|---|---|---|
| `integrations/hermes/config.yaml` | Config de Hermes para TODOS los proyectos (modelos, providers) | **Se queda en reevolutiva-infra** como config base compartida. Cada proyecto puede sobrescribir en su `integrations/hermes/config.yaml` |
| `integrations/hermes/skills/` | Project-local skills | **Se mueve a cada `<proyecto>/integrations/hermes/skills/`** |
| `integrations/paperclip/` | Config Paperclip compartida | **Se queda en reevolutiva-infra** como config base. Proyectos heredan/sobrescriben |
| `scripts/backup-agentes.sh` | Backup de estado de agentes | **Se queda en reevolutiva-infra** (es infra compartida). Los proyectos lo referencian en su `setup.sh` |
| `scripts/setup.sh` en cada proyecto | Restore path específico | **Vive en `<proyecto>/scripts/setup.sh`** (generado por /ree-repo F5) |

### Flujo de desarrollo

```
┌─────────────────────────────────────────────────────────┐
│                  Ciclo de vida de una skill              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  MacBook (desarrollo local)                              │
│  ├── skill_manage create/patch                           │
│  ├── Validación manual (description ≤60, YAML, formato)  │
│  ├── git checkout -b feat/<skill>                        │
│  ├── git commit + push                                   │
│  └── PR → validate-skills.yml (CI check)                 │
│                                                         │
│  vm-services (validación y despliegue)                   │
│  ├── git clone / pull del tap                            │
│  ├── hermes skills install <tap>/skills/<name> --yes     │
│  ├── hermes skills inspect <name>                        │
│  └── smoke test: skill disponible en skills_list         │
│                                                         │
│  PR merge → main                                         │
│  ├── block-push-main.yml (skipped, es merge)             │
│  └── hermes skills update en todas las instancias        │
│                                                         │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│           Ciclo de habilitación de proyecto (/ree-repo)  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  /ree-producto output (documentos fuente)                │
│       │                                                 │
│       ▼                                                 │
│  /ree-repo (orquestadora — PRÓXIMAMENTE)                 │
│       │                                                 │
│       ├── F1 Validate → docs/validation-report.md        │
│       ├── F2 Architect → docs/architecture/ + ADRs       │
│       ├── F3 Scaffold → repo GitHub + apps/<proyecto>/   │
│       │   └── Clona en vm-services:/data/workspace/      │
│       │       projects/<proyecto>                        │
│       ├── F4 Deploy → PR en reevolutiva-infra            │
│       │   └── clusters/<cluster>/apps.yaml               │
│       ├── F5 Harness → AGENTS.md + integrations/ +       │
│       │   scripts/setup.sh + registro Paperclip          │
│       └── F6 Verify → make health + CHECKLIST.md         │
│                                                         │
│  Output: repo listo para development en vm-services      │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Decisiones de diseño (ADRs implícitos)

1. **El tap (`hermes-skills`) es solo skills.** No contiene config de runtime, integraciones ni scripts de infraestructura. Las skills son el producto; todo lo demás es runtime del proyecto.

2. **`reevolutiva-infra` es solo infraestructura compartida.** Contiene lo que Flux reconcilia (controllers, storage, namespaces, workloads compartidos) + config base de agentes (modelos, providers). No contiene project-local skills ni harness específico de un proyecto.

3. **Cada proyecto es autónomo en su harness.** `integrations/`, `scripts/setup.sh`, project-local skills viven en el repo del proyecto. Si el proyecto desaparece, su harness desaparece con él — no contamina infra compartida.

4. **vm-services es el workspace de desarrollo.** Todos los proyectos se clonan en `/data/workspace/projects/<proyecto>/`. Hermes y Paperclip corren como systemd services (fuera de K3s) y acceden a estos workspaces.

5. **El restore path es verificable por proyecto.** `scripts/setup.sh` de cada proyecto debe poder ejecutarse en una vm-services limpia y restaurar el ambiente completo: `git clone → AKV secrets → backup restore → systemd enable → make health`.

6. **La config de Hermes tiene herencia.** `reevolutiva-infra/integrations/hermes/config.yaml` define la config base (modelos, providers, auth). Cada proyecto puede sobrescribir secciones en su `integrations/hermes/config.yaml`. Si un proyecto no tiene config propia, usa la base.

### Impacto en /ree-repo y ree-learn

- **F3 (Scaffold)**: genera `apps/<proyecto>/` en el repo del proyecto, no en `reevolutiva-infra/apps/`. Los workloads compartidos (Ollama, LiteLLM, DBs) ya están en `reevolutiva-infra/apps/` y no se tocan.

- **F4 (Deploy)**: solo toca `clusters/<cluster>/apps.yaml` en `reevolutiva-infra` (registro Flux). No crea directorios en `reevolutiva-infra/apps/`.

- **F5 (Harness)**: genera `integrations/hermes/` y `integrations/paperclip/` en el repo del proyecto. Opcionalmente referencia la config base de `reevolutiva-infra` para herencia.

- **F6 (Verify)**: `make health` sigue en `reevolutiva-infra` (verifica el clúster completo). El proyecto añade `CHECKLIST.md` con su propia verificación.

- **`ree-learn` (modo actualizar)**: cuando se actualiza una skill del tap, no afecta a `reevolutiva-infra`. Cuando se actualiza una project-local skill, solo afecta al repo del proyecto.