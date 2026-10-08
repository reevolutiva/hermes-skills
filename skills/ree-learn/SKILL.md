---
name: ree-learn
description: "Corrige errores y construye skills. Modos: error, aprender."
version: 1.2.0
author: Hermes
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [learning, alignment, error-correction, skill-building, jev, gitops]
    related_skills:
      - ree-aprender (absorbida por ree-learn; no se invoca)
      - typesafe-ai
      - ree-kanban-ops
      - reevolutiva-infra-gitops
required_environment_variables:
  - name: TYPESAFE_API_KEY
    prompt: "TypeSafe API key para gates Jev de validacion"
    help: "Obten una en https://console.typesafe.ai — la skill funciona en modo fallback sin ella"
    required_for: "gates de validacion automatizados (noul/choice/score)"
---

# /ree-learn — Orquestador de Aprendizaje y Alineamiento

Skill orquestadora con dos modos:
- **`ree-learn error`** — detecta, diagnostica y corrige la fuente raiz de un error
  usando herramientas nativas de Hermes (memory, skill_manage, approvals.deny, /refine)
  con Jev como validador de cada paso.
- **`ree-learn aprender`** — construye una nueva skill orquestada siguiendo la
  metodologia de 4 fases (Investigar → Diseniar → Implementar → Revisar) del
  patron `ree-aprender`, con Jev como motor de gates de calidad.

## When to Use

- `ree-learn error` — el agente cometio un error y necesitas eliminar la fuente
  de forma definitiva para que no se repita.
- `ree-learn aprender` — necesitas construir una nueva capacidad como skill
  orquestada con validacion Jev.

## Quick Reference

| Modo | Fases | Motor de validacion | Escribe en |
|------|-------|---------------------|------------|
| `error` | Capturar → Diagnosticar → Corregir → Validar → Registrar | Jev (choice + noul + score) | memory + skill_manage + approvals.deny staging |
| `aprender` | Investigar → Diseniar → Implementar → Revisar | Jev (noul + score por fase) | skill_manage + referencias + templates |

## Modo 1: `ree-learn error`

### Procedure

#### Fase 1 — Capturar el error
1. Si el usuario solo dice `ree-learn error`, pedir que describa el error o
   que indique el ultimo mensaje donde ocurrio.
2. Extraer del contexto de sesion: mensaje exacto, accion del agente, regla violada.
3. Si hay un mensaje del usuario corrigiendo al agente, usarlo como fuente primaria.

#### Fase 2 — Diagnosticar la fuente raiz (Jev Choice)
1. Construir el state con: descripcion del error, politica violada, skills cargadas.
2. Ejecutar Jev para clasificar la fuente:
   - Opciones: `skill_desactualizada`, `memoria_faltante`, `regla_config_ausente`,
     `discrepancia_user_policy`, `error_contexto_sesion`

#### Fase 3 — Corregir (aplicar la herramienta correcta)
Segun la fuente raiz detectada, aplicar skill_manage, memory, approvals.deny o skill_view.

#### Fase 4 — Validar la correccion (Jev Noul)
"Does the correction fully eliminate the error source?" — ≥ 0.8 = suficiente.

#### Fase 5 — Registrar
Bitacora con session-log.md + kanban_comment si es grave.

## Modo 2: `ree-learn aprender`

### Procedure

Metodologia de 4 fases: Investigar → Diseniar → Implementar → Revisar.

#### Fase 1 — Investigar
1. Leer requerimiento del usuario.
2. **Determinar alcance (obligatorio):** preguntar al usuario si la skill es:
   - `profile_or_tap` — skill global, reutilizable entre proyectos. Se instala en el perfil
     Hermes (`~/.hermes/skills/`) y, si es corporativa, se publica en el tap
     `reevolutiva/hermes-skills` (`skills/<name>/SKILL.md`). Sigue el flujo de Fase 3
     con push al repo del tap.
   - `project_local` — skill especifica de un proyecto/repo. Vive dentro del repo
     destino en `integrations/hermes/skills/<name>/` o `.hermes/skills/` del proyecto.
     **No** se publica en el tap corporativo. Hermes la detecta como project-local skill
     cuando trabaja en ese directorio (precedencia sobre skills del perfil en caso de
     duplicado; puede requerir trust del proyecto para evitar quarantine).
   - Si el usuario no esta seguro, explicar las implicancias de cada opcion:
     - `profile_or_tap`: mantenible centralizadamente, versionado, compartido con el
       equipo, requiere PR + merge en el tap para distribuir.
     - `project_local`: acoplado al ciclo de vida del proyecto, util para skills muy
       especificas que no tienen sentido fuera de ese contexto (ej. reglas de negocio
       de un cliente, configuraciones de un solo despliegue).
   - Registrar la decision en la bitacora de sesion.
3. skills_list + skill_view de candidatas.
4. Clasificar: reutilizable, adaptable, obsoleta.
5. Identificar gaps (Jev noul).
6. Proponer arbol de dependencias y categoria.

**Criterio de salida:** aprobacion del usuario (incluyendo confirmacion del alcance).

#### Fase 2 — Diseniar
Crear Design Spec (00_design_spec.md) con:
- Metodologia, proceso paso a paso, modelo de datos.
- Gates Jev mapeados, gestion de contexto, artefactos.
- Gate de disenio (Jev score): `incompleto` a `sobreconstruido`.

**No pasar a Fase 3 sin aprobacion del usuario.**

**Validar contra infraestructura real:** antes de presentar el Design Spec al usuario, revisar los repos de infraestructura del proyecto (`reevolutiva-infra`, configs de Paperclip, clusteres K3s) y verificar que el disenio refleja la arquitectura real: estructura `apps/<proyecto>/`, modelo HelmRelease vs Deployment, ExternalSecret -> AKV, exposicion Tailscale-only. Si el Design Spec asume una arquitectura distinta a la real, la implementacion sera rechazada en revision.

#### Fase 3 — Implementar
1. Crear skills en orden: hojas → intermedias → orquestadora.
2. **Tras crear cada skill, verificar que description cumple ≤ 60 chars y el YAML frontmatter es valido:** `grep "^description:" <categoria>/<skill>/SKILL.md`. Si tiene dos puntos, envolver en comillas dobles.
3. **Si la skill es `profile_or_tap` y pertenece a un tap corporativo, despues de crearla pushear los cambios al repo del tap:**
   - El tap `reevolutiva/hermes-skills` usa estructura `skills/<name>/SKILL.md` (no `<categoria>/<skill>/SKILL.md`)
   - Desde local (MacBook): `cd ~/proyectos/reevolutiva-skills`
   - Desde vm-services: `cd /home/giolapietra/reevolutiva-skills`
   - Copiar: `cp -r <origen> skills/<skill>/`
   - Actualizar `skills.sh.json` si el catalogo cambio
   - `git checkout -b feat/<skill-name>`
   - `git add . && git commit -m "feat(<skill-name>): descripcion"`
   - `git push origin feat/<skill-name>`
   - Solo mergear via PR, nunca push directo a main
   - **Despues de pushear, verificar desde otra instancia:**
     - `hermes skills install reevolutiva/hermes-skills/skills/<skill-name> --yes`
     - `hermes skills inspect <skill-name>` sin errores
     - Si falla: el path `skills/<name>/SKILL.md` no existe en main del repo
4. **Si la skill es `project_local`, NO pushear al tap.** En su lugar:
   - Crear la skill via `skill_manage` (queda en `~/.hermes/skills/` temporalmente)
   - Moverla al directorio del proyecto: `integrations/hermes/skills/<name>/` o `.hermes/skills/`
   - Documentar en `AGENTS.md` del proyecto que existe una project-local skill y su proposito
   - El usuario debe confiar en el proyecto (`hermes project trust`) para que Hermes cargue
     estas skills sin quarantine
   - Verificar: `hermes skills list` muestra la skill cuando el workdir esta dentro del proyecto
5. **Actualizar AGENTS.md y README.md del repo del tap (o del proyecto, si es project_local):**
   - Tras crear o modificar una skill, actualizar AGENTS.md anadiendo la skill en la seccion
     "Estructura del repositorio"
   - Actualizar README.md con la descripcion de la skill en "Skills disponibles"
   - Si se descubrieron nuevos pitfalls, reglas de desarrollo o comandos durante la implementacion,
     documentarlos en ambos archivos
   - Hacer commit atomico: skill nueva/modificada + docs actualizados en el mismo PR
   - **Nunca dejar los docs desactualizados tras un cambio de skill** — este paso es obligatorio,
     no opcional
6. **Antes del primer push al repo, configurar branch protection en main:**
   - `gh api /repos/<org>/<repo>/branches/main/protection --method PUT --input - <<'JSON'` con `allow_force_pushes: false, allow_deletions: false, block_creations: false`
   - Generar `.github/workflows/block-push-main.yml` con un job que haga `exit 1` en push a main **pero que ignore los commits de merge de PR y squash merges** (si no, el workflow bloquea sus propios merges):
     - `if: ${{ !startsWith(github.event.head_commit.message, 'Merge pull request') && !contains(github.event.head_commit.message, '(#') }}`
     - La segunda condicion es necesaria porque `gh pr merge --squash` produce commits con formato `feat(x): descripcion (#N)`, no `Merge pull request`.
7. Reglas generales: description ≤ 60 chars, author Hermes, una skill = una responsabilidad.

#### Fase 4 — Revisar
1. skills_list por categoria.
2. Coherencia cruzada.
3. Gate final (Jev score): `inconsistente` a `excelente`.
4. Gate de comandos: validar comandos contra CLI real.
5. **Verificar que AGENTS.md y README.md reflejan los cambios de esta implementacion:**
   - ¿La nueva skill aparece en "Estructura del repositorio" (AGENTS.md)?
   - ¿La nueva skill aparece en "Skills disponibles" (README.md)?
   - ¿Los pitfalls/reglas descubiertos durante la implementacion estan documentados en ambos archivos?
   - Si falta algo, volver a Fase 3 y actualizar los docs antes de cerrar.
6. **Verificar que el workflow CI del merge en main paso sin errores** — si el ultimo push a main
   es un squash merge, el job `block-push-main.yml` debe aparecer como `skipped` (el `if` lo salto
   porque detecto `(#N)` en el commit message). Si aparece como `failure`, el workflow rechazo
   su propio merge — hay que revisar el `if` del workflow y el formato del mensaje de commit.
6. **Forzar refresh de la UI de GitHub**: despues de varios pushes directos o merges que no
   refrescan la pagina principal, la UI puede mostrar estructura/cache stale por horas incluso
   cuando la API (`gh api`, `curl`) confirma que el contenido es correcto. Un merge de PR
   (cualquier tipo) fuerza el rebuild de la pagina. Si no hay cambios de codigo pendientes,
   un cambio trivial en README.md mergeado via PR es suficiente para disparar el refresh.

## Jev Integration Points (modo aprender)

| Fase | Punto | Primitivo | Pregunta / Opciones |
|------|-------|-----------|---------------------|
| 1 | Clasificacion skills | `choice` | `reuse_as_is`, `adapt`, `obsolete` |
| 1 | Deteccion de gaps | `noul` | "Does the requirement ask for something no existing skill covers?" |
| 2 | Validacion disenio | `score` | `incompleto`, `minimo_viable`, `completo`, `sobreconstruido` |
| 3 | Description check | `noul` | "Does this description meet all criteria?" |
| 3 | Redundancia | `noul` | "Is there content overlap that warrants extraction?" |
| 4 | Coherencia final | `score` | `inconsistente`, `coherencia_parcial`, `coherente`, `excelente` |
| 4 | Completitud | `choice` | `falta_cobertura`, `cubre_parcialmente`, `cubre_completo` |

## Modo sin Jev (fallback)

Sin TYPESAFE_API_KEY: marcar `[hermes-judgment]` con nivel de confianza.

## Pitfalls

- **Corregir en la capa equivocada:** skill para procedimientos, memory para preferencias.
- **No validar la correccion:** noul < 0.8 = re-diagnosticar.
- **Crear skills en orden incorrecto:** hojas primero, orquestadora al final.
- **Exceder 60 chars en description:** contar siempre.
- **No leer skills existentes:** skill_view antes de decidir.
- **No preguntar el alcance (project_local vs profile_or_tap):** si el usuario no lo especifica,
  asumir `profile_or_tap` por defecto pero confirmar. Una skill creada como project_local y
  pusheada al tap contamina el catalogo corporativo con reglas especificas de un proyecto.
  Una skill creada como profile_or_tap pero guardada solo en el proyecto queda invisible para
  otros agentes y proyectos que la necesiten.
- **Docs desactualizados tras implementacion:** si AGENTS.md y README.md no se actualizan en el
  mismo PR que la skill, otros desarrolladores no sabran que la skill existe ni como usarla.
  Este paso es obligatorio en Fase 3 y verificable en Fase 4.
- **Description con dos puntos sin comillas rompe el YAML frontmatter.** Si la description contiene `:` (ej. "Modos: error, aprender"), envolverla en comillas dobles: `description: "texto con dos puntos"`. El parser YAML interpreta los dos puntos como separador de mapeo y rechaza la skill completa.
- **Skill creada localmente no se instala automaticamente desde el tap.** `skill_manage` crea la skill en `~/.hermes/skills/` pero el repo del tap (`reevolutiva/hermes-skills`) necesita un commit + push + PR para que otros agentes la reciban. Si la skill se creo para distribucion corporativa, pushear al repo del tap como paso final de Fase 3.
- **Verificar que el tap este configurado como `taps: git`, no `external_dirs`.** `external_dirs` carga skills de un directorio local sin versionado ni distribucion. `taps: git` habilita `hermes skills install` y `hermes skills reload` desde el repo remoto. Es la diferencia entre un prototipo local y un sistema corporativo.
- **El agente debe cargar `ree-learn` (skill_view) al inicio de una sesion de construccion de skills.** Si no la carga, opera sin la metodologia de 4 fases y comete errores de proceso (saltarse gates, no validar infraestructura real, hacer push sin branch protection).
- **`block-push-main.yml` debe aceptar squash merges ademas de merge commits.** El `if` que solo chequea `!startsWith('Merge pull request')` rechaza los squash merges de `gh pr merge --squash`, cuyo commit message tiene formato `feat(x): descripcion (#N)`. Agregar `&& !contains(github.event.head_commit.message, '(#')` para que ambos tipos de merge pasen el workflow.
- **Toda correccion de workflow o regla de desarrollo debe documentarse en AGENTS.md y README.md del repo**, no solo en el commit. Un fix sin documentacion en los archivos de referencia del repo deja a otros desarrolladores sin contexto cuando el workflow se comporta de forma inesperada.

## Verification

1. `ree-learn error` → clasifica fuente, corrige, valida.
2. `ree-learn aprender` → completa 4 fases.
3. Sin TYPESAFE_API_KEY → modo fallback.
4. Skills creadas pasan skills_list y skill_view.
5. Skills creadas para el tap corporativo aparecen en `hermes skills list --tap reevolutiva/hermes-skills`.
6. `gh api /repos/reevolutiva/hermes-skills/branches/main/protection` confirma `allow_force_pushes: false, allow_deletions: false`.
7. `.github/workflows/block-push-main.yml` existe en el repo del tap.