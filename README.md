# Skills de Reevolutiva

Skills de infraestructura, aprendizaje, habilitación de repositorios, alineamiento y documentación de producto para Hermes Agent.

## Estructura

```
skills/
├── ree-learn/                        # Aprendizaje: error, aprender, actualizar
├── ree-producto/                     # Documentación de producto en 8 fases
├── ree-repo/                         # Orquestador F1-F6 de habilitación de repos
├── ree-repo-architect/               # Diagramas C4 y ADRs
├── ree-repo-deploy/                  # Manifiestos GitOps y registro Flux
├── ree-repo-harness/                 # AGENTS.md, integrations y setup
├── ree-repo-scaffold/                # Repo de código, entorno reproducible y CI
├── ree-repo-validate/                # Validación de documentos fuente
├── ree-repo-verify/                  # Coherencia y Definition of Done
├── ree-hermes-paperclip-method/      # Método Hermes intake→Paperclip
├── ree-paperclip-board-ops/          # Gestión diaria del board Paperclip
├── reevolutiva-infra-gitops/         # Operación de Flux + K3s + AKV
├── wordpress-bedrock-migration/      # Migración WordPress Bedrock a K3s
└── wordpress-performance-diagnosis/  # Diagnóstico de WordPress en K8s

scripts/
├── setup.sh
├── update.sh
├── install-vm-services.sh
└── validate-skills-catalog.py

.github/workflows/
├── block-push-main.yml
└── validate-skills.yml

skills.sh.json
AGENTS.md
README.md
docs/
├── arquitectura-repositorios.md
└── infrastructure-README.md
```

Cada skill puede incluir su propio `references/` y `templates/` para separar el procedimiento principal del detalle.

## Skills disponibles

### Aprendizaje y producto

`ree-learn` — tres modos: diagnosticar errores, crear skills y actualizar skills existentes.

`ree-producto` — flujo de 8 fases para documentar productos con intake y gates Jev.

`ree-hermes-paperclip-method` — contrato de intake, delegación Paperclip, review independiente y captura de aprendizaje.

`ree-paperclip-board-ops` — gestión diaria del board: chequeos, steering de issues, revisión de PRs de agentes y diagnóstico de runs.

`ree-paperclip-adapter-diagnosis` — diagnóstico de adapters y gateways: OpenCode, LiteLLM y Hermes gateway.

### Habilitación de repositorios

`ree-repo` — orquesta el pipeline F1-F6 desde documentos de producto hasta verificación.

- `ree-repo-validate` — evalúa los documentos fuente antes de implementar.
- `ree-repo-architect` — genera diagramas C4 y ADRs desde Fase 6.
- `ree-repo-scaffold` — prepara el repo de código, setup, pruebas y CI; no aloja manifiestos K3s.
- `ree-repo-deploy` — declara los manifiestos y el placement en `reevolutiva-infra` mediante Flux.
- `ree-repo-harness` — configura AGENTS.md, integrations, setup y workspace si aplica.
- `ree-repo-verify` — comprueba coherencia y Definition of Done para el destino elegido.

### Infraestructura

`reevolutiva-infra-gitops` — operación del repo GitOps: Flux, K3s, AKV y runbooks operativos.

`wordpress-bedrock-migration` — migración de WordPress Bedrock single-site o multisite a K3s.

`wordpress-performance-diagnosis` — diagnóstico de latencia, caídas y caché de WordPress en Kubernetes.

## Instalación

```bash
# Como GitHub Tap (compartido con el equipo)
hermes skills tap add reevolutiva/hermes-skills

# Aprendizaje, producto y coordinación Hermes→Paperclip
hermes skills install reevolutiva/hermes-skills/skills/ree-learn
hermes skills install reevolutiva/hermes-skills/skills/ree-producto
hermes skills install reevolutiva/hermes-skills/skills/ree-hermes-paperclip-method
hermes skills install reevolutiva/hermes-skills/skills/ree-paperclip-board-ops

# Habilitación de repositorios (orquestador y seis fases)
hermes skills install reevolutiva/hermes-skills/skills/ree-repo
hermes skills install reevolutiva/hermes-skills/skills/ree-repo-validate
hermes skills install reevolutiva/hermes-skills/skills/ree-repo-architect
hermes skills install reevolutiva/hermes-skills/skills/ree-repo-scaffold
hermes skills install reevolutiva/hermes-skills/skills/ree-repo-deploy
hermes skills install reevolutiva/hermes-skills/skills/ree-repo-harness
hermes skills install reevolutiva/hermes-skills/skills/ree-repo-verify

# Infraestructura y WordPress
hermes skills install reevolutiva/hermes-skills/skills/reevolutiva-infra-gitops
hermes skills install reevolutiva/hermes-skills/skills/wordpress-bedrock-migration
hermes skills install reevolutiva/hermes-skills/skills/wordpress-performance-diagnosis

# Actualizar todas
hermes skills update
```

## Reglas

- La skill principal tiene una description de ≤60 caracteres (límite de Hermes)
- Los archivos de referencia usan el formato progressive disclosure
- Cada skill debe incluir When to Use, Procedure, Pitfalls y Verification
- Toda skill orquestada incluye sección `## Jev Integration Points`
- Usar `TYPESAFE_API_KEY` cuando esté disponible; fallback con razonamiento Hermes si no
- **Nunca push directo a `main`** — solo PR mergeados. El workflow `block-push-main.yml` rechaza cualquier push que no sea un merge de PR (commit message empieza con "Merge pull request" o contiene "(#N)" de squash merge).

## Estado del proyecto

**Fase activa:** consolidación del conocimiento operativo y diseño del método Hermes→Paperclip.

- [Estado de avance 2026-10-16](docs/estado-avance-2026-10-16.md) — inventario de skills, divergencias, hallazgos de curator y plan de consolidación.
- [Planificación del siguiente slice](docs/siguiente-slice-hermes-paperclip.md) — diseño e implementación del flujo Hermes intake → Paperclip ejecución con piloto end-to-end.

Los artefactos de investigación están en `~/.hermes/cache/scratch/agent-skill-research/`; los volcados de sesión no se versionan.