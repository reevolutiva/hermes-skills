---
name: ree-learn
description: "Corrige errores y construye skills. Modos: error, aprender."
version: 1.1.0
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

Cubre los tres niveles de persistencia de Hermes:
1. **Procedural** → `skill_manage` (SKILL.md)
2. **Memoria** → `memory` (MEMORY.md / USER.md)
3. **Politica de ejecucion** → `approvals.deny` (config.yaml), staging con `/skills pending`

## When to Use

- `ree-learn error` — el agente cometio un error y necesitas eliminar la fuente
  de forma definitiva para que no se repita.
- `ree-learn error` con contexto — despues de un incidente de Flux/kubectl,
  un drift de politica, o una discrepancia con USER.md.
- `ree-learn aprender` — necesitas construir una nueva capacidad como skill
  orquestada con validacion Jev.
- Frases gatillo: "corrige esto para siempre", "elimina la fuente del error",
  "aprende de esto", "construye una skill para...", "empaqueta este flujo".

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
2. Extraer del contexto de sesion:
   - Mensaje exacto donde se detecto la discrepancia.
   - Accion que el agente tomo (o iba a tomar).
   - Regla o politica que se violo (si es conocida).
3. Si hay un mensaje del usuario corrigiendo al agente, usarlo como fuente primaria.

#### Fase 2 — Diagnosticar la fuente raiz (Jev Choice)
1. Construir el state con: descripcion del error, politica violada, skills cargadas
   relevantes, entradas de memory actuales, reglas approvals.deny activas.
2. Ejecutar Jev para clasificar la fuente:

| Punto | Que evalua | Primitivo | Pregunta / Opciones |
|-------|-----------|-----------|---------------------|
| **Fuente raiz** | ¿De donde viene la discrepancia? | `choice` | Opciones: `skill_desactualizada`, `memoria_faltante`, `regla_config_ausente`, `discrepancia_user_policy`, `error_contexto_sesion` |

3. Si `TYPESAFE_API_KEY` no esta disponible, usar `[hermes-judgment]` con
   nivel de confianza explicito.

#### Fase 3 — Corregir (aplicar la herramienta correcta)
Segun la fuente raiz detectada:

**Caso A: `skill_desactualizada`**
- Cargar la skill relevante con `skill_view(name="...")`.
- Identificar exactamente que seccion o instruccion esta mal.
- `skill_manage(action="patch", ...)` para corregir el contenido.
- Si la skill no existe, `skill_manage(action="create", ...)`.

**Caso B: `memoria_faltante`**
- `memory(operations=[{action: "add", target: "memory", content: "..."}])`
  para MEMORY.md, o target `user` para USER.md.
- Si hay entrada existente que contradice, usar `replace` o `remove` + `add`.

**Caso C: `regla_config_ausente`**
- Proponer entrada en `approvals.deny` de `~/.hermes/config.yaml`.
- Stagear la propuesta (no aplicar directamente sin confirmacion si
  `write_approval` esta activo).
- Si el error es de tipo "usar kubectl apply en vez de GitOps", aniadir:
  `"*kubectl apply*"`, `"*kubectl patch*"`, `"*kubectl delete*"`.

**Caso D: `discrepancia_user_policy`**
- Comparar la accion tomada contra `USER.md` y las skills relevantes.
- Si el agente ignoro una instruccion de USER.md, reforzarla en la skill
  que aplica al dominio (no duplicar en memory si ya existe en skill).
- `memory(action="replace", target="user", ...)` si la entrada es ambigua.

**Caso E: `error_contexto_sesion`**
- El error fue por no cargar una skill relevante a tiempo.
- Aniadir `skill_view` obligatorio en el procedimiento de la skill que fallo.
- Si el dominio es amplio, agregar `related_skills` en metadata.

**Accion complementaria (todos los casos):**
- Ejecutar `/refine` con foco en el error corregido para que el background
  review procese la correccion.

#### Fase 4 — Validar la correccion (Jev Noul)
1. Construir state con: skill/memory/regla ANTES y DESPUES del cambio.
2. Pregunta Jev noul: "¿La correccion elimina completamente la fuente del error?"
   - ≥ 0.8: correccion suficiente.
   - 0.5-0.8: correccion parcial, documentar gap restante.
   - < 0.5: volver a Fase 2 y re-diagnosticar.

#### Fase 5 — Registrar
1. Crear entrada en bitacora usando `templates/session-log.md`.
2. Si el error es grave (impacto produccion o datos), crear `kanban_comment`
   en la carta activa con el resumen de la correccion.
3. Informar al usuario: que se corrigio, en que capa, y si queda algun gap.

### Jev Integration Points (modo error)

| Punto | Que evalua | Primitivo | Pregunta / Opciones |
|-------|-----------|-----------|---------------------|
| Fuente raiz | Clasificacion del origen de la discrepancia | `choice` | `skill_desactualizada`, `memoria_faltante`, `regla_config_ausente`, `discrepancia_user_policy`, `error_contexto_sesion` |
| Validacion | ¿La correccion elimina la fuente? | `noul` | "Does the correction fully eliminate the error source?" |
| Coherencia final | ¿La correccion no introduce nuevas contradicciones? | `noul` | "Does the fix introduce any contradiction with existing policies?" |

### Verification

- [ ] La skill/memoria/regla corregida se lee con `skill_view` o `cat` y refleja el cambio.
- [ ] Jev (o Hermes fallback) da noul ≥ 0.8 para "elimina la fuente del error".
- [ ] Si se stageo un cambio en config.yaml, aparece en `/skills pending` o `/memory pending`.
- [ ] La bitacora registra: error original, fuente raiz, accion tomada, validacion.

---

## Modo 2: `ree-learn aprender`

### Procedure

Sigue la metodologia de 4 fases de `ree-aprender` con los gates Jev de `ree-producto`.

#### Fase 1 — Investigar
**Objetivo:** mapear skills existentes y gaps.

1. **Leer el requerimiento del usuario.** Identificar que skill(s) necesita construir
   y para que dominio.
2. **Inventariar skills internas:**
   - `skills_list` por categoria.
   - `skill_view` de toda skill candidata.
3. **Inventariar Skills Hub:**
   - `web_extract` de `https://hermes-agent.nousresearch.com/docs/skills` filtrando
     por el dominio.
   - Anotar IDs de skills instalables.
4. **Clasificar cada skill** en: reutilizable tal cual, adaptable, obsoleta.
   - **Jev choice** para clasificar skills dudosas.
5. **Identificar gaps:** lo que ninguna skill existente cubre.
   - **Jev noul:** "Does the requirement ask for something no existing skill covers?"
6. **Proponer alternativa de orquestacion:**
   - Lista de skills a reutilizar + skills a crear.
   - Arbol de dependencias (hojas → intermedias → orquestadora).
   - Categoria propuesta.

**Criterio de salida:** el usuario aprueba la propuesta de orquestacion.

#### Fase 2 — Diseniar
**Objetivo:** crear Design Spec completo antes de escribir una linea.

Seguir `ree-aprender` Fase 2 paso a paso. Entregables obligatorios:

1. **Metodologia:** como funciona la skill objetivo.
2. **Proceso paso a paso:** numerado, con inputs/outputs/herramientas por paso.
3. **Modelo de datos:** campos del intake, estructura de entregables, formato de
   archivos de salida.
4. **Gates Jev:** mapeo completo de integration points (pre-gates noul por fase,
   post-gates score por entregable, gate final de coherencia).
5. **Gestion de contexto:** que se carga en cada paso (progressive disclosure),
   que NO se carga, como se propaga entre fases.
6. **Artefactos y entregables:** lista completa con paths y secciones obligatorias.

Gate de disenio (Jev score): "¿El disenio es completo y viable?"
- Levels: `incompleto`, `minimo_viable`, `completo`, `sobreconstruido`.
- Si score < `completo`, iterar hasta cubrir gaps.

**Validar contra infraestructura real:** antes de presentar el Design Spec al usuario,
revisar los repos de infraestructura del proyecto (`reevolutiva-infra`, configs de
Paperclip, clusteres K3s) y verificar que el disenio refleja la arquitectura real:
estructura `apps/<proyecto>/`, modelo HelmRelease vs Deployment, ExternalSecret → AKV,
exposicion Tailscale-only. Si el Design Spec asume una arquitectura distinta a la real,
la implementacion sera rechazada en revision.

Escribir el Design Spec como `00_design_spec.md` en el directorio de la skill.
**No pasar a Fase 3 sin aprobacion explicita del usuario.**

#### Fase 3 — Implementar
**Objetivo:** crear skills en orden de dependencia (hojas → intermedias → orquestadora).

1. **Crear primero skills sin dependencias** (hojas).
2. **Crear skills intermedias** que dependen de las hojas.
3. **Crear orquestadora al final.**
4. **Crear referencias y templates** segun el Design Spec.

Reglas de implementacion:
- **Description ≤ 60 caracteres.** Contar antes de guardar: `echo "description" | wc -c`.
- **Description con `:` debe ir entre comillas dobles** en YAML frontmatter: `description: "texto con dos puntos"`.
- **author: Hermes** — no usar nombre del usuario ni del SO.
- **Una skill = una responsabilidad.**
- **No repetir contenido** entre skills; extraer a transversal.
- **Toda skill incluye seccion `## Jev Integration Points`.**

5. **Si la skill pertenece al tap corporativo, pushear al repo:**
   - El tap `reevolutiva/hermes-skills` usa estructura `skills/<name>/SKILL.md`
   - Desde local: `cd ~/proyectos/reevolutiva-skills`
   - Desde vm-services: `cd /home/giolapietra/reevolutiva-skills`
   - Copiar: `cp -r <origen> skills/<skill>/`
   - Actualizar `skills.sh.json` si el catalogo cambio
   - `git checkout -b feat/<skill-name>`
   - `git add . && git commit -m "feat(<skill-name>): descripcion"`
   - `git push origin feat/<skill-name>`
   - **Solo mergear via PR** — nunca push directo a main (branch protection activo + workflow `block-push-main.yml`)
6. **Despues de pushear, verificar desde otra instancia:**
   - `hermes skills tap add reevolutiva/hermes-skills` (si no esta)
   - `hermes skills install reevolutiva/hermes-skills/skills/<skill-name>`
   - `hermes skills inspect <skill-name>` sin errores
   - Si falla: el path `skills/<name>/SKILL.md` no existe en main del repo

Gates de implementacion (Jev noul por skill):
- "¿La description cumple ≤60 chars y formato gatillo?"
- "¿La skill declara todas sus dependencias en related_skills?"
- "¿No hay contenido duplicado con otra skill del set?"

#### Fase 4 — Revisar
**Objetivo:** verificar coherencia del sistema completo.

1. **Inventariar:** `skills_list` por categoria confirma todas las skills creadas.
2. **Coherencia cruzada:** ¿las skills referencian correctamente sus dependencias?
   ¿los nombres de archivos de entregables son consistentes?
3. **Gate final de validacion (Jev score):**
   - "¿El sistema de skills es completo y coherente?"
   - Levels: `inconsistente`, `coherencia_parcial`, `coherente`, `excelente`.
4. **Gate de comandos:** extraer todos los comandos citados por las skills nuevas
   y validarlos contra CLI real (un verbo inventado invalida la guia).
5. **Corregir lo que falle.** No entregar con errores conocidos.

Gate final de completitud (Jev choice):
- "¿El set de skills cubre todo lo que el usuario pidio?"
- Opciones: `falta_cobertura`, `cubre_parcialmente`, `cubre_completo`.
- Si no es `cubre_completo`, volver a Fase 1 para detectar gaps.

### Jev Integration Points (modo aprender)

| Fase | Punto | Que evalua | Primitivo | Pregunta / Opciones |
|------|-------|-----------|-----------|---------------------|
| 1 | Clasificacion skills | ¿Reutilizable, adaptable u obsoleta? | `choice` | `reuse_as_is`, `adapt`, `obsolete` |
| 1 | Deteccion de gaps | ¿Hay algo que ninguna skill cubre? | `noul` | "Does the requirement ask for something no existing skill covers?" |
| 2 | Validacion disenio | ¿El disenio es completo y viable? | `score` | `incompleto`, `minimo_viable`, `completo`, `sobreconstruido` |
| 3 | Description check | ¿Cumple ≤60 chars y formato? | `noul` | "Does this description meet all criteria?" |
| 3 | Redundancia | ¿Contenido duplicado entre skills? | `noul` | "Is there content overlap that warrants extraction?" |
| 4 | Coherencia final | ¿Sistema completo y coherente? | `score` | `inconsistente`, `coherencia_parcial`, `coherente`, `excelente` |
| 4 | Completitud | ¿Cubre todo lo pedido? | `choice` | `falta_cobertura`, `cubre_parcialmente`, `cubre_completo` |

### Modo sin Jev (fallback)

Si `TYPESAFE_API_KEY` no esta configurada, los mismos puntos se evaluan con
razonamiento de Hermes:
- Marcar decisiones como `[hermes-judgment]` con nivel de confianza.
- Si una decision es critica y la confianza es baja, pedir input al usuario.
- La bitacora registra el motor usado en cada gate.

---

## Pitfalls

- **Corregir en la capa equivocada.** Si el error es de procedimiento (el agente
  no sabe como hacer algo), la skill es la capa correcta, no memory. Si es una
  preferencia del usuario que aplica a TODO, memory es correcta.
- **No validar la correccion.** Jev noul < 0.8 despues de corregir no es "ya fue":
  hay que re-diagnosticar.
- **Aceptar el primer diagnostico de Jev sin revisar.** Jev clasifica; el operador
  (o el usuario) decide. Si la clasificacion es `uncertain` (0.3-0.7), lanzar
  sondas atomicas adicionales.
- **Crear skills en orden incorrecto.** Si una skill referencia a otra que no
  existe, `related_skills` queda huerfano. Implementar siempre de abajo hacia arriba.
- **Exceder 60 chars en description.** Es el error mas comun. Contar antes de guardar.
- **No leer las skills existentes.** Asumir que "X ya hace Y" sin cargarla con
  `skill_view` lleva a duplicar funcionalidad.
- **Preguntar en negativo en gates Jev.** "¿Estas skills se contradicen?" invierte
  la lectura de la probabilidad. Preguntar siempre en positivo: "¿Son coherentes?"
- **Un gate que nunca falla no verifica.** Probar cada script en positivo y negativo
  antes de declararlo listo.
- **Modo `error` sin evidencia.** Si el usuario solo dice "te equivocaste" sin
  especificar, pedir el contexto. Corregir a ciegas empeora la skill.
- **Skill creada localmente no se instala automaticamente desde el tap.** `skill_manage`
  crea la skill en `~/.hermes/skills/` pero el repo del tap (`reevolutiva/hermes-skills`)
  necesita un commit + push + PR para que otros agentes la reciban. Si la skill se creo
  para distribucion corporativa, pushear al repo del tap como paso final de Fase 3.
- **Verificar que el tap use `external_dirs` para skills infra o `skills install` para skills core.**
  Las skills de infraestructura (con comandos operativos reales) no pasan el security scanner
  del Hub — se cargan via `external_dirs` apuntando a un clon del repo. Las skills core
  (ree-learn, ree-producto) si pasan el scanner y se instalan via `hermes skills install`.
- **El agente debe cargar `ree-learn` (skill_view) al inicio de una sesion de construccion
  de skills.** Si no la carga, opera sin la metodologia de 4 fases y comete errores de
  proceso (saltarse gates, no validar infraestructura real, hacer push sin branch protection).

## Verification

1. `ree-learn error` con un caso real → clasifica fuente, corrige, valida.
2. `ree-learn aprender` con un requerimiento concreto → completa las 4 fases.
3. Sin `TYPESAFE_API_KEY` → funciona en modo fallback con `[hermes-judgment]`.
4. La bitacora (`session-log.md`) registra cada gate y su resultado.
5. Las skills creadas pasan `skills_list` y `skill_view` sin errores.
6. Las skills core instaladas via tap aparecen en `hermes skills list --source hub`.
7. Las skills infra instaladas via `external_dirs` aparecen en `hermes skills list --source local`.
8. `gh api /repos/reevolutiva/hermes-skills/branches/main/protection` confirma proteccion activa.
9. `.github/workflows/block-push-main.yml` existe en el repo del tap.