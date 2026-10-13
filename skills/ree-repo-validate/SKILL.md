---
name: ree-repo-validate
description: "Valida docs /ree-producto con Jev gates pre-implementacion."
version: 1.0.0
author: Hermes
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [repository, validation, jev, scaffolding, gitops]
    related_skills:
      - ree-repo
      - ree-producto
      - typesafe-ai
required_environment_variables:
  - name: TYPESAFE_API_KEY
    prompt: "TypeSafe API key para gates Jev de validacion"
    help: "Obten una en https://console.typesafe.ai — la skill funciona en modo fallback sin ella"
    required_for: "gates de validacion automatizados (noul/score)"
---

# /ree-repo-validate — Validacion de Documentos Fuente

Determina si los entregables de `/ree-producto` tienen sustento suficiente para
pasar a implementacion. Es la primera fase del pipeline `/ree-repo`.

## When to Use

- `/ree-repo` Fase 1 — llamado por la orquestadora
- "validar documentos de producto antes de implementar"
- "¿estan listos los docs de /ree-producto para desarrollo?"

## Procedure

### Paso 0 — Verificar entorno

1. Verificar que existe `output.base_dir` de `/ree-producto`:
   - Leer `.intake-autopoblado.yml` o `.ree-producto-session-*.md` en el
     directorio actual o rutas conocidas
   - Si no se encuentra, preguntar al usuario la ruta
2. Si `TYPESAFE_API_KEY` no esta configurada, informar modo fallback
   (`[hermes-judgment]`).

### Paso 1 — Inventariar documentos fuente

1. Leer los archivos de fase en `<base_dir>/`:
   - `01-discovery/` — market-profile-builder output
   - `02-personas/` — persona-niche-lab output
   - `03-strategy/` — product-strategy-session output
   - `04-prd/` — prd-master output
   - `05-design/` — design-md output
   - `06-tech/` — arquitectura-tecnica.md (diataxis output)
   - `07-gtm/` — gtm-strategy output
   - `08-metrics/` — product-analytics output
2. Para cada fase presente, extraer un resumen de 2-3 lineas:
   - Decisiones concretas tomadas
   - Artefactos generados
   - Gaps evidentes (secciones vacias, placeholders, "por definir")
3. Registrar fases ausentes (no tienen carpeta ni archivo).

### Paso 2 — Evaluar calidad por fase (Jev Noul)

Para cada fase presente, ejecutar Jev noul con el estado del documento:

| Fase | Pregunta Jev | Umbral |
|------|-------------|--------|
| 1. Discovery | "Does the market profile contain concrete market size, trends, and competitive landscape data?" | ≥ 0.6 |
| 2. Personas | "Are the personas based on research with specific demographics, pain points, and goals?" | ≥ 0.6 |
| 3. Estrategia | "Does the strategy define concrete features with priorities, not just high-level vision?" | ≥ 0.7 |
| 4. PRD | "Does the PRD contain measurable acceptance criteria for each requirement?" | **≥ 0.8** |
| 5. Diseno | "Does the design spec define specific components, layouts, and interaction patterns?" | ≥ 0.6 |
| 6. Tech | "Does the technical architecture specify a concrete stack, interfaces, and costs?" | **≥ 0.8** |
| 7. GTM | "Does the GTM strategy define specific channels, timeline, and success metrics?" | ≥ 0.6 |
| 8. Metrics | "Are the metrics specific, measurable, and aligned with the product goals?" | ≥ 0.6 |

Fases 4 (PRD) y 6 (Tech) tienen umbral mas alto (0.8) porque son las mas
criticas para la implementacion: sin PRD concreto y sin stack definido,
/scaffold no puede generar la estructura del repo.

Si una fase esta ausente, marcarla como `no_evaluada` y registrarla en el
reporte de gaps.

### Paso 3 — Gate F1 (Jev Score)

Evaluar el sustento global de los documentos fuente.

**State a enviar a Jev:**
- Lista de fases presentes/ausentes
- Resultados de los noul por fase
- Resumen de gaps detectados

**Score levels:**
- `insuficiente` — una o mas fases criticas (4, 6) tienen noul < 0.8 o estan
  ausentes. **Recomendacion: detener y volver a /ree-producto.**
- `minimo` — todas las fases presentes tienen noul ≥ umbral, pero hay gaps
  menores. **Se puede avanzar con advertencias.**
- `solido` — todas las fases criticas ≥ 0.8, gaps menores documentados.
  **Listo para implementar.**
- `excelente` — todas las fases ≥ 0.8, sin gaps, decisiones completas.
  **Sobresaliente.**

### Paso 4 — Generar reporte

1. Crear `docs/validation-report.md` en el directorio del proyecto (si ya
   existe el repo) o en `<base_dir>/validation-report.md` (si aun no hay repo).
2. El reporte incluye:
   - **Resumen ejecutivo**: gate F1 score + recomendacion
   - **Tabla de fases**: nombre, presente/ausente, noul score, gaps
   - **Fases criticas**: detalle de PRD y Tech con citas del documento
   - **Gaps detectados**: lista de items que requieren atencion antes de F3
   - **Recomendacion**: `proceed`, `proceed_with_caveats`, `blocked`
3. Formato: markdown con tablas, sin codigo ni JSON — legible para humanos.

### Paso 5 — Bitacora

1. Actualizar `.ree-repo-session-<timestamp>.md` con el resultado de F1:
   - Fecha, hora
   - Motor del gate (Jev / fallback hermes-judgment)
   - Score obtenido
   - Path del reporte generado
   - Decision: continuar / detener

## Jev Integration Points

| Punto | Que evalua | Primitivo | Pregunta / Opciones |
|-------|-----------|-----------|---------------------|
| Fase 1-8 | Calidad individual | `noul` | Ver tabla Paso 2 |
| Gate F1 | Sustento global | `score` | `insuficiente`, `minimo`, `solido`, `excelente` |

## Modo sin Jev (fallback)

Sin TYPESAFE_API_KEY:
- Reemplazar noul por `[hermes-judgment]` con analisis cualitativo:
  - ¿El documento contiene decisiones concretas o solo descripciones genericas?
  - ¿Hay stack, interfaces y costos definidos en Fase 6?
  - ¿El PRD tiene criterios de aceptacion medibles?
- Reemplazar score por clasificacion manual en los mismos 4 niveles.
- Marcar cada evaluacion con `[hermes-judgment]` y nivel de confianza.

## Artefactos

| Archivo | Descripcion |
|---------|-------------|
| `docs/validation-report.md` | Reporte de validacion con scores, gaps y recomendacion |
| `.ree-repo-session-<timestamp>.md` | Bitacora de la sesion |

## Pitfalls

- **Validar sin leer los documentos:** no se puede evaluar calidad sin leer el
  contenido real. Cada noul debe recibir el texto completo de la fase (o un
  resumen extenso), no solo el nombre del archivo.
- **Umbrales arbitrarios:** 0.6 para fases no criticas, 0.8 para PRD y Tech.
  Si el usuario quiere ajustar umbrales, documentar el cambio en la bitacora.
- **Fase ausente ≠ insuficiente:** si el usuario decidio no ejecutar una fase
  en /ree-producto, marcarla como `no_evaluada`, no como fallo. El gate F1
  decide si eso es bloqueante.
- **No generar el reporte:** si el agente evalua pero no escribe
  `validation-report.md`, el siguiente agente en el pipeline no tiene contexto
  de que se valido y que gaps quedan.
- **Confundir gap de producto con gap de validacion:** si un documento de
  /ree-producto es insuficiente, el reporte debe decir "volver a /ree-producto
  Fase X", no "el validador no pudo evaluar".

## Verification

1. `skills_list` muestra `ree-repo-validate` en categoria `productivity`.
2. Ejecutar sobre un proyecto con output de /ree-producto completo → gate F1 ≥
   `minimo`.
3. Ejecutar sobre un proyecto sin Fase 4 (PRD) → gate F1 = `insuficiente`.
4. Sin TYPESAFE_API_KEY → reporte usa `[hermes-judgment]`.
5. `validation-report.md` generado con tabla de fases, gaps y recomendacion.
6. Bitacora actualizada con resultado de F1.