---
name: ree-learn
description: Corrige errores y construye skills. Modos: error, aprender.
version: 1.0.0
author: Hermes
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [learning, alignment, error-correction, skill-building, jev, gitops]
    related_skills:
      - ree-aprender
      - typesafe-ai
      - ree-kanban-ops
      - reevolutiva-infra-gitops
required_environment_variables:
  - name: TYPESAFE_API_KEY
    prompt: "TypeSafe API key para gates Jev de validación"
    help: "Obtén una en https://console.typesafe.ai — la skill funciona en modo fallback sin ella"
    required_for: "gates de validación automatizados (noul/choice/score)"
---

# /ree-learn — Orquestador de Aprendizaje y Alineamiento

Skill orquestadora con dos modos:
- **`ree-learn error`** — detecta, diagnostica y corrige la fuente raíz de un error
  usando herramientas nativas de Hermes (memory, skill_manage, approvals.deny, /refine)
  con Jev como validador de cada paso.
- **`ree-learn aprender`** — construye una nueva skill orquestada siguiendo la
  metodología de 4 fases (Investigar → Diseñar → Implementar → Revisar) del
  patrón `ree-aprender`, con Jev como motor de gates de calidad.

Cubre los tres niveles de persistencia de Hermes:
1. **Procedural** → `skill_manage` (SKILL.md)
2. **Memoria** → `memory` (MEMORY.md / USER.md)
3. **Política de ejecución** → `approvals.deny` (config.yaml), staging con `/skills pending`

## When to Use

- `ree-learn error` — el agente cometió un error y necesitas eliminar la fuente
  de forma definitiva para que no se repita.
- `ree-learn error` con contexto — después de un incidente de Flux/kubectl,
  un drift de política, o una discrepancia con USER.md.
- `ree-learn aprender` — necesitas construir una nueva capacidad como skill
  orquestada con validación Jev.
- Frases gatillo: "corrige esto para siempre", "elimina la fuente del error",
  "aprende de esto", "construye una skill para...", "empaqueta este flujo".

## Quick Reference

| Modo | Fases | Motor de validación | Escribe en |
|------|-------|---------------------|------------|
| `error` | Capturar → Diagnosticar → Corregir → Validar → Registrar | Jev (choice + noul + score) | memory + skill_manage + approvals.deny staging |
| `aprender` | Investigar → Diseñar → Implementar → Revisar | Jev (noul + score por fase) | skill_manage + referencias + templates |

## Modo 1: `ree-learn error`

### Procedure

#### Fase 1 — Capturar el error
1. Si el usuario solo dice `ree-learn error`, pedir que describa el error o
   que indique el último mensaje donde ocurrió.
2. Extraer del contexto de sesión:
   - Mensaje exacto donde se detectó la discrepancia.
   - Acción que el agente tomó (o iba a tomar).
   - Regla o política que se violó (si es conocida).
3. Si hay un mensaje del usuario corrigiendo al agente, usarlo como fuente primaria.

#### Fase 2 — Diagnosticar la fuente raíz (Jev Choice)
1. Construir el state con: descripción del error, política violada, skills cargadas
   relevantes, entradas de memory actuales, reglas approvals.deny activas.
2. Ejecutar Jev para clasificar la fuente:

| Punto | Qué evalúa | Primitivo | Pregunta / Opciones |
|-------|-----------|-----------|---------------------|
| **Fuente raíz** | ¿De dónde viene la discrepancia? | `choice` | Opciones: `skill_desactualizada`, `memoria_faltante`, `regla_config_ausente`, `discrepancia_user_policy`, `error_contexto_sesion` |

3. Si `TYPESAFE_API_KEY` no está disponible, usar `[hermes-judgment]` con
   nivel de confianza explícito.

#### Fase 3 — Corregir (aplicar la herramienta correcta)
Según la fuente raíz detectada:

**Caso A: `skill_desactualizada`**
- Cargar la skill relevante con `skill_view(name="...")`.
- Identificar exactamente qué sección o instrucción está mal.
- `skill_manage(action="patch", ...)` para corregir el contenido.
- Si la skill no existe, `skill_manage(action="create", ...)`.

**Caso B: `memoria_faltante`**
- `memory(operations=[{action: "add", target: "memory", content: "..."}])`
  para MEMORY.md, o target `user` para USER.md.
- Si hay entrada existente que contradice, usar `replace` o `remove` + `add`.

**Caso C: `regla_config_ausente`**
- Proponer entrada en `approvals.deny` de `~/.hermes/config.yaml`.
- Stagear la propuesta (no aplicar directamente sin confirmación si
  `write_approval` está activo).
- Si el error es de tipo "usar kubectl apply en vez de GitOps", añadir:
  `"*kubectl apply*"`, `"*kubectl patch*"`, `"*kubectl delete*"`.

**Caso D: `discrepancia_user_policy`**
- Comparar la acción tomada contra `USER.md` y las skills relevantes.
- Si el agente ignoró una instrucción de USER.md, reforzarla en la skill
  que aplica al dominio (no duplicar en memory si ya existe en skill).
- `memory(action="replace", target="user", ...)` si la entrada es ambigua.

**Caso E: `error_contexto_sesion`**
- El error fue por no cargar una skill relevante a tiempo.
- Añadir `skill_view` obligatorio en el procedimiento de la skill que falló.
- Si el dominio es amplio, agregar `related_skills` en metadata.

**Acción complementaria (todos los casos):**
- Ejecutar `/refine` con foco en el error corregido para que el background
  review procese la corrección.

#### Fase 4 — Validar la corrección (Jev Noul)
1. Construir state con: skill/memory/regla ANTES y DESPUÉS del cambio.
2. Pregunta Jev noul: "¿La corrección elimina completamente la fuente del error?"
   - ≥ 0.8: corrección suficiente.
   - 0.5-0.8: corrección parcial, documentar gap restante.
   - < 0.5: volver a Fase 2 y re-diagnosticar.

#### Fase 5 — Registrar
1. Crear entrada en bitácora usando `templates/session-log.md`.
2. Si el error es grave (impactó producción o datos), crear `kanban_comment`
   en la carta activa con el resumen de la corrección.
3. Informar al usuario: qué se corrigió, en qué capa, y si queda algún gap.

### Jev Integration Points (modo error)

| Punto | Qué evalúa | Primitivo | Pregunta / Opciones |
|-------|-----------|-----------|---------------------|
| Fuente raíz | Clasificación del origen de la discrepancia | `choice` | `skill_desactualizada`, `memoria_faltante`, `regla_config_ausente`, `discrepancia_user_policy`, `error_contexto_sesion` |
| Validación | ¿La corrección elimina la fuente? | `noul` | "Does the correction fully eliminate the error source?" |
| Coherencia final | ¿La corrección no introduce nuevas contradicciones? | `noul` | "Does the fix introduce any contradiction with existing policies?" |

### Verification

- [ ] La skill/memoria/regla corregida se lee con `skill_view` o `cat` y refleja el cambio.
- [ ] Jev (o Hermes fallback) da noul ≥ 0.8 para "elimina la fuente del error".
- [ ] Si se stageó un cambio en config.yaml, aparece en `/skills pending` o `/memory pending`.
- [ ] La bitácora registra: error original, fuente raíz, acción tomada, validación.

---

## Modo 2: `ree-learn aprender`

### Procedure

Sigue la metodología de 4 fases de `ree-aprender` con los gates Jev de `ree-producto`.

#### Fase 1 — Investigar
**Objetivo:** mapear skills existentes y gaps.

1. **Leer el requerimiento del usuario.** Identificar qué skill(s) necesita construir
   y para qué dominio.
2. **Inventariar skills internas:**
   - `skills_list` por categoría.
   - `skill_view` de toda skill candidata.
3. **Inventariar Skills Hub:**
   - `web_extract` de `https://hermes-agent.nousresearch.com/docs/skills` filtrando
     por el dominio.
   - Anotar IDs de skills instalables.
4. **Clasificar cada skill** en: reutilizable tal cual, adaptable, obsoleta.
   - **Jev choice** para clasificar skills dudosas.
5. **Identificar gaps:** lo que ninguna skill existente cubre.
   - **Jev noul:** "Does the requirement ask for something no existing skill covers?"
6. **Proponer alternativa de orquestación:**
   - Lista de skills a reutilizar + skills a crear.
   - Árbol de dependencias (hojas → intermedias → orquestadora).
   - Categoría propuesta.

**Criterio de salida:** el usuario aprueba la propuesta de orquestación.

#### Fase 2 — Diseñar
**Objetivo:** crear Design Spec completo antes de escribir una línea.

Seguir `ree-aprender` Fase 2 paso a paso. Entregables obligatorios:

1. **Metodología:** cómo funciona la skill objetivo.
2. **Proceso paso a paso:** numerado, con inputs/outputs/herramientas por paso.
3. **Modelo de datos:** campos del intake, estructura de entregables, formato de
   archivos de salida.
4. **Gates Jev:** mapeo completo de integration points (pre-gates noul por fase,
   post-gates score por entregable, gate final de coherencia).
5. **Gestión de contexto:** qué se carga en cada paso (progressive disclosure),
   qué NO se carga, cómo se propaga entre fases.
6. **Artefactos y entregables:** lista completa con paths y secciones obligatorias.

Gate de diseño (Jev score): "¿El diseño es completo y viable?"
- Levels: `incompleto`, `minimo_viable`, `completo`, `sobreconstruido`.
- Si score < `completo`, iterar hasta cubrir gaps.

Escribir el Design Spec como `00_design_spec.md` en el directorio de la skill.
**No pasar a Fase 3 sin aprobación explícita del usuario.**

#### Fase 3 — Implementar
**Objetivo:** crear skills en orden de dependencia (hojas → intermedias → orquestadora).

1. **Crear primero skills sin dependencias** (hojas).
2. **Crear skills intermedias** que dependen de las hojas.
3. **Crear orquestadora al final.**
4. **Crear referencias y templates** según el Design Spec.

Reglas de implementación:
- **Description ≤ 60 caracteres.**
- **author: Hermes** — no usar nombre del usuario ni del SO.
- **Una skill = una responsabilidad.**
- **No repetir contenido** entre skills; extraer a transversal.
- **Toda skill incluye sección `## Jev Integration Points`.**
- Usar `skill_manage(action="create", ...)` para cada skill nueva.

Gates de implementación (Jev noul por skill):
- "¿La description cumple ≤60 chars y formato gatillo?"
- "¿La skill declara todas sus dependencias en related_skills?"
- "¿No hay contenido duplicado con otra skill del set?"

#### Fase 4 — Revisar
**Objetivo:** verificar coherencia del sistema completo.

1. **Inventariar:** `skills_list` por categoría confirma todas las skills creadas.
2. **Coherencia cruzada:** ¿las skills referencian correctamente sus dependencias?
   ¿los nombres de archivos de entregables son consistentes?
3. **Gate final de validación (Jev score):**
   - "¿El sistema de skills es completo y coherente?"
   - Levels: `inconsistente`, `coherencia_parcial`, `coherente`, `excelente`.
4. **Gate de comandos:** extraer todos los comandos citados por las skills nuevas
   y validarlos contra CLI real (un verbo inventado invalida la guía).
5. **Corregir lo que falle.** No entregar con errores conocidos.

Gate final de completitud (Jev choice):
- "¿El set de skills cubre todo lo que el usuario pidió?"
- Opciones: `falta_cobertura`, `cubre_parcialmente`, `cubre_completo`.
- Si no es `cubre_completo`, volver a Fase 1 para detectar gaps.

### Jev Integration Points (modo aprender)

| Fase | Punto | Qué evalúa | Primitivo | Pregunta / Opciones |
|------|-------|-----------|-----------|---------------------|
| 1 | Clasificación skills | ¿Reutilizable, adaptable u obsoleta? | `choice` | `reuse_as_is`, `adapt`, `obsolete` |
| 1 | Detección de gaps | ¿Hay algo que ninguna skill cubre? | `noul` | "Does the requirement ask for something no existing skill covers?" |
| 2 | Validación diseño | ¿El diseño es completo y viable? | `score` | `incompleto`, `minimo_viable`, `completo`, `sobreconstruido` |
| 3 | Description check | ¿Cumple ≤60 chars y formato? | `noul` | "Does this description meet all criteria?" |
| 3 | Redundancia | ¿Contenido duplicado entre skills? | `noul` | "Is there content overlap that warrants extraction?" |
| 4 | Coherencia final | ¿Sistema completo y coherente? | `score` | `inconsistente`, `coherencia_parcial`, `coherente`, `excelente` |
| 4 | Completitud | ¿Cubre todo lo pedido? | `choice` | `falta_cobertura`, `cubre_parcialmente`, `cubre_completo` |

### Modo sin Jev (fallback)

Si `TYPESAFE_API_KEY` no está configurada, los mismos puntos se evalúan con
razonamiento de Hermes:
- Marcar decisiones como `[hermes-judgment]` con nivel de confianza.
- Si una decisión es crítica y la confianza es baja, pedir input al usuario.
- La bitácora registra el motor usado en cada gate.

---

## Pitfalls

- **Corregir en la capa equivocada.** Si el error es de procedimiento (el agente
  no sabe cómo hacer algo), la skill es la capa correcta, no memory. Si es una
  preferencia del usuario que aplica a TODO, memory es correcta.
- **No validar la corrección.** Jev noul < 0.8 después de corregir no es "ya fue":
  hay que re-diagnosticar.
- **Aceptar el primer diagnóstico de Jev sin revisar.** Jev clasifica; el operador
  (o el usuario) decide. Si la clasificación es `uncertain` (0.3-0.7), lanzar
  sondas atómicas adicionales.
- **Crear skills en orden incorrecto.** Si una skill referencia a otra que no
  existe, `related_skills` queda huérfano. Implementar siempre de abajo hacia arriba.
- **Exceder 60 chars en description.** Es el error más común. Contar antes de guardar.
- **No leer las skills existentes.** Asumir que "X ya hace Y" sin cargarla con
  `skill_view` lleva a duplicar funcionalidad.
- **Preguntar en negativo en gates Jev.** "¿Estas skills se contradicen?" invierte
  la lectura de la probabilidad. Preguntar siempre en positivo: "¿Son coherentes?"
- **Un gate que nunca falla no verifica.** Probar cada script en positivo y negativo
  antes de declararlo listo.
- **Modo `error` sin evidencia.** Si el usuario solo dice "te equivocaste" sin
  especificar, pedir el contexto. Corregir a ciegas empeora la skill.

## Verification

1. `ree-learn error` con un caso real → clasifica fuente, corrige, valida.
2. `ree-learn aprender` con un requerimiento concreto → completa las 4 fases.
3. Sin `TYPESAFE_API_KEY` → funciona en modo fallback con `[hermes-judgment]`.
4. La bitácora (`session-log.md`) registra cada gate y su resultado.
5. Las skills creadas pasan `skills_list` y `skill_view` sin errores.