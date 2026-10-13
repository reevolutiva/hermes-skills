---
name: ree-repo
description: "Habilita repo listo desarrollo desde docs de /ree-producto."
version: 1.0.0
author: Hermes
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [repository, scaffolding, paperclip, harness, development, orchestration]
    related_skills:
      - ree-producto
      - ree-repo-validate
      - ree-repo-architect
      - ree-repo-scaffold
      - ree-repo-deploy
      - ree-repo-harness
      - ree-repo-verify
      - typesafe-ai
      - plan
      - github-repo-management
      - github-pr-workflow
      - github-auth
      - setup-wizard-generator
      - reevolutiva-infra-gitops
required_environment_variables:
  - name: TYPESAFE_API_KEY
    prompt: "TypeSafe API key para gates Jev de validacion"
    help: "Obten una en https://console.typesafe.ai — la skill funciona en modo fallback sin ella"
    required_for: "gates de validacion automatizados (noul/choice/score)"
---

# /ree-repo — Habilitacion de Repositorio

Skill orquestadora que transforma los entregables de `/ree-producto` en una base
de desarrollo reproducible: valida documentos, genera diagramas, crea el repo de
codigo y coordina harness, workspace y verificacion. El repo del proyecto contiene
codigo, pruebas y CI; los manifiestos K3s viven en `reevolutiva-infra`. Paperclip
es opcional y preparar un workspace no equivale a desplegar el servicio.

## When to Use

- `/ree-repo` — inicia el flujo completo con intake desde `/ree-producto`
- "habilitar repo", "configurar proyecto para desarrollo", "preparar harness de agentes", "scaffolding del proyecto"

## Arquitectura

```
/ree-producto (documentos fuente)
        │
        ▼
/ree-repo (orquestadora)
        │
        ├── F1: ree-repo-validate — Jev gates sobre docs fuente
        ├── F2: ree-repo-architect — diagramas C4 + ADRs
        ├── F3: ree-repo-scaffold — repo de codigo, setup, pruebas, CI e imagen si aplica
        ├── F4: ree-repo-deploy — manifiestos en reevolutiva-infra/apps/<proyecto>/ + registro Flux
        ├── F5: ree-repo-harness — AGENTS.md, integrations/, setup.sh, Paperclip
        └── F6: ree-repo-verify — checklist DoD + make health + gate final
```

### Dependencias entre fases

- F2 consume F1 — no se diagrama si los docs fuente no pasan gates
- F3 consume F2 — la estructura del repo refleja las decisiones de arquitectura
- F4, F5 son independientes entre si pero ambas consumen F2+F3
- F6 consume todas las anteriores

## Procedure

### Paso 0 — Verificacion de entorno

1. Verificar `gh auth status`.
2. Detectar `output.base_dir` de `/ree-producto` desde el contexto.
3. Si TYPESAFE_API_KEY no esta configurada, informar modo fallback.

### Paso 1 — Intake

1. Leer `.intake-autopoblado.yml` del proyecto.
2. Inventariar las 8 fases de `/ree-producto`.
3. Preguntar al usuario:
   - Nombre del repo (default: slug del product.name)
   - Organizacion GitHub (default: reevolutiva)
   - Stack (default inferido de Fase 6)
   - Destino de ejecucion: solo repo/CI, servicio del sistema en vm-services o workload K3s via Flux
   - Si aplica K3s, tipo de workload a determinar desde los manifiestos vigentes
   - Si se usara Paperclip: Company y workspace en vm-services:/data/workspace/projects/<repo>
4. Gate de intake (Jev Choice): `ready_all_phases`, `missing_critical_phase`, `insufficient_detail`.

### Paso 2 — Seleccion de fases

1. Presentar menu de 6 fases. Por defecto: todas las requeridas por el destino; F4 solo si se eligio despliegue K3s.
2. Si el usuario salta F1, advertir que no se validaran los docs fuente.

### Paso 3 — Loop de ejecucion

Para cada fase en orden:

1. **Pre-gate**: ¿el contexto actual es suficiente?
2. **Cargar subskill**: `skill_view("ree-repo-<fase>")`
3. **Ejecutar subskill**: seguir su procedimiento
4. **Post-gate**: evaluar calidad del entregable
5. **Bitacora**: actualizar `.ree-repo-session-<timestamp>.md`

Si una fase falla, preguntar si re-ejecutar o continuar.

### Paso 4 — Cierre

1. Gate final (Jev Score): coherencia global.
2. Mostrar resumen: fases ejecutadas, gates superados, artefactos generados.
3. Guardar bitacora final.

## Jev Integration Points

| Fase | Gate | Primitivo | Opciones / Niveles |
|------|------|-----------|-------------------|
| Intake | Completitud | `choice` | `ready_all_phases`, `missing_critical_phase`, `insufficient_detail` |
| F1 | Validate | `score` | `insuficiente`, `minimo`, `solido`, `excelente` |
| F2 | Architect | `score` | `inaccurate`, `partial`, `accurate`, `comprehensive` |
| F3 | Scaffold | `score` | `incompleto`, `minimo`, `completo`, `sobreconstruido` |
| F4 | Deploy | `noul` | "Does the Kustomization follow the canonical pattern?" |
| F5 | Harness | `noul` | "Does the project harness cover the selected development and recovery path without assuming optional integrations?" |
| F6 | Verify | `score` | `incoherente`, `fragmentado`, `coherente`, `excelente` |

## Modelo de Despliegue

Cuatro capas, cada una con un lugar unico de declaracion:

| Capa | Se declara en | Reconciliado por |
|---|---|---|
| Codigo, pruebas y CI | Repo del proyecto | GitHub Actions / CI |
| Que corre (imagen, env, recursos) | `reevolutiva-infra/apps/<proyecto>/` | Flux Kustomization del cluster |
| En que maquina corre | `reevolutiva-infra/clusters/<activo>/apps.yaml` | K3s scheduler |
| Infra compartida | `reevolutiva-infra/infrastructure/` | Flux Kustomization del cluster |

Regla: el repo de codigo no contiene la fuente de verdad de los manifiestos K3s;
la app no sabe donde corre y la ubicacion es decision del cluster.

Exposicion: Tailscale-only por defecto. Secretos: ExternalSecret → AKV.

## Pitfalls

- **No duplicar /ree-producto:** si un documento no existe o es insuficiente, detener y derivar a /ree-producto.
- **Repo de codigo y GitOps separados:** el codigo, pruebas y CI viven en el repo del proyecto; los manifiestos K3s viven en `reevolutiva-infra/apps/` y el placement en `clusters/<activo>/apps.yaml`.
- **HelmRelease vs Deployment plano:** decidir explicitamente en intake.
- **Tailscale, no publico:** por defecto ingressClassName: tailscale.
- **ExternalSecret → AKV:** los remoteRef.key deben existir en el vault.
- **Credenciales en .env.example:** solo nombres de variables, nunca valores reales.
- **GitHub auth previo:** verificar gh auth status antes de F3.
- **Bitacora obligatoria:** escribir .ree-repo-session-<timestamp>.md despues de cada fase.
- **PR separado en reevolutiva-infra:** F4 abre PR, no commitea directo a main.
- **Proteccion de main segun el estandar de la organizacion:** configurar los controles antes de depender de ellos; nunca eludirlos ni hacer push directo a main.
- **Workspace opcional:** solo crear el workspace de vm-services si se eligio Paperclip o ese entorno de desarrollo; no compartir un `.git` escribible entre agentes.
- **Paperclip condicional:** solo pedir Company y registrar proyecto si Paperclip forma parte del alcance.

## Verification

1. `skills.sh.json` y `README.md` enumeran ree-repo y sus 6 subskills; cada path `skills/<name>/SKILL.md` existe.
2. /ree-repo en proyecto con output de /ree-producto → detecta intake automaticamente.
3. F1 Validate → gate Jev Score ≥ `minimo` → continua.
4. F2 Architect → genera 3 diagramas .excalidraw + ADRs.
5. F3 Scaffold → repo de codigo reproducible, setup, pruebas y CI; no contiene manifiestos K3s.
6. Si se eligio K3s, F4 Deploy → PR en reevolutiva-infra con manifiestos y Kustomization; si no, la fase se omite.
7. F5 Harness → AGENTS.md + integrations/ + setup.sh; Paperclip se registra solo si fue seleccionado.
8. F6 Verify → pruebas funcionales y checklist según el destino; para K3s, `make health` + gate ≥ `coherente` + CHECKLIST.md.
9. Bitacora .ree-repo-session-<timestamp>.md existe y cubre todas las fases.
10. Push directo a main rechazado: branch protection activa.
