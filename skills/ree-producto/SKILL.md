---
name: ree-producto
description: Flujo en 8 etapas para doc de productos con intake y gates.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [product, documentation, orchestration, intake, gates, methodology]
    related_skills:
      - market-profile-builder
      - competitor-intelligence
      - opportunity-mapper
      - persona-niche-lab
      - brand-strategy-writer
      - design-md
      - social-brand-foundations
      - research-writing-harness
      - grounded-citations
      - typesafe-ai
      - plan
required_environment_variables:
  - name: TYPESAFE_API_KEY
    prompt: "TypeSafe API key para gates de validación Jev"
    help: "Obtén una en https://console.typesafe.ai — la skill funciona en modo fallback sin ella"
    required_for: "gates de validación automatizados"
---

# /ree-producto — Documentación de Producto desde Cero

Skill orquestadora que guía la documentación completa de un producto nuevo a
través de 8 fases: descubrimiento, usuarios, estrategia, PRD, diseño,
documentación técnica, go-to-market y métricas. Usa Jev (TypeSafe) como motor
de gates de validación entre fases, con fallback a razonamiento de Hermes.

## When to Use

- `/ree-producto` — inicia el flujo completo con intake interactivo
- `/ree-producto solo-fase 3` — ejecuta una fase específica sin pasar por las demás
- "documentar producto desde cero", "metodología de producto", "PRD completo",
  "product design doc", "quiero documentar mi producto nuevo"

## Quick Reference

| Fase | Subskill principal | Gate pre | Gate post |
|------|-------------------|----------|-----------|
| 1. Descubrimiento | `market-profile-builder` | Noul | Score |
| 2. Usuarios | `persona-niche-lab` | Noul | Score |
| 3. Estrategia | `product-strategy-session` | Noul | Score |
| 4. PRD | `prd-master` | Noul | Score |
| 5. Diseño | `design-md` | Noul | Score |
| 6. Docs Técnicas | `diataxis` | Noul | Score |
| 7. GTM | `gtm-strategy` | Noul | Score |
| 8. Métricas | `product-analytics` | Noul | Score |
| Final | `research-writing-harness` | — | Score (coherencia) |

## Procedure

### Paso 0 — Verificación de entorno

1. Ejecutar `skills_list` y verificar qué subskills requeridas están instaladas.
2. Para las subskills del Hub no instaladas, listar sus IDs y preguntar al
   usuario si desea instalarlas ahora con `manage_catalog`.
3. Si `TYPESAFE_API_KEY` no está configurada, informar que los gates
   funcionarán en modo fallback (razonamiento de Hermes).
4. Cargar `skill_view("ree-producto", "references/intake-schema.md")`.

### Paso 1 — Intake interactivo

1. Presentar el formulario de intake campo por campo, empezando por los
   obligatorios: `product.name`, `product.domain`, `problem.statement`,
   `solution.summary`, `users.primary_segments`, `output.base_dir`.
2. Para campos con opciones predefinidas (`stage`, `business.model`,
   `output.format`), mostrar las opciones disponibles.
3. Preguntar por `sources` (carpetas, documentos, URLs, notas) — si el
   usuario proporciona fuentes, son **vinculantes**: el agente DEBE
   inspeccionarlas durante las fases relevantes.
4. Al completar, mostrar resumen estructurado del intake y pedir confirmación.
5. **Gate de intake (Jev Choice)**: evaluar completitud.
   - Opciones: `proceed_all_phases`, `proceed_with_caveats`,
     `incomplete_needs_more`.
   - Ver `references/gate-definitions.md` para el payload exacto.
6. Si `incomplete_needs_more`: volver a recolectar.
   Si `proceed_with_caveats`: marcar gaps en bitácora y continuar.

### Paso 2 — Selección de fases

1. Presentar el menú de 8 fases con checkboxes conceptuales.
2. El usuario marca las que quiere ejecutar. Por defecto: todas (1→8).
3. Permitir modo `solo-fase N` para ejecutar una única fase.
4. Si el usuario salta una fase de la que otra depende (ej: Fase 4 PRD sin
   Fase 3 Estrategia), advertir en pre-gate.
5. Registrar selección en bitácora.

### Paso 3 — Loop de ejecución de fases

Para cada fase seleccionada, en orden:

1. **Pre-gate (Jev Noul)**: ¿el contexto actual es suficiente para esta fase?
   - Ver `references/gate-definitions.md` para el payload.
   - Si noul < 0.6: advertir y preguntar si continuar.

2. **Cargar subskill**: `skill_view("<subskill>")` para la fase actual.
   - También cargar `references/phase-catalog.md` para ver subskills
     auxiliares si la fase las requiere.

3. **Inspeccionar fuentes**: si `sources` tiene entradas relevantes para
   esta fase, leerlas con `read_file` (documentos), `web_extract` (URLs), o
   `search_files` (carpetas) antes de ejecutar la subskill.

4. **Ejecutar subskill**: seguir su procedimiento, usando el intake como
   input y las fuentes como contexto vinculante.

5. **Post-gate (Jev Score)**: evaluar calidad del entregable.
   - Ver `references/gate-definitions.md` para el payload.
   - Si score = `insuficiente`: preguntar si re-ejecutar o aceptar.

6. **Actualizar bitácora** usando el template `templates/session-log.md`.

7. Si hay más fases: "¿Continuar con Fase N+1: <nombre>?"

### Paso 4 — Cierre y QA final

1. **Gate final (Jev Score)**: coherencia cross-fase de todos los entregables.
   - Ver `references/gate-definitions.md` para el payload.

2. Ejecutar `research-writing-harness` sobre todos los entregables.

3. Mostrar resumen final: tabla de fases ejecutadas, gates superados,
   artefactos generados con paths.

4. Guardar bitácora completa en
   `<output.base_dir>/.ree-producto-session-<timestamp>.md`.

## Pitfalls

- **No cargar subskills al inicio**: la carga progresiva es esencial. Solo
  cargar la subskill de la fase actual.
- **Jev no reemplaza criterio humano**: si el usuario dice "acepto", el gate
  se bypass y se registra en bitácora.
- **Fases dependientes**: advertir (no bloquear) si el usuario salta una fase
  de la que otra depende.
- **Fuentes vinculantes**: si el usuario proporcionó `sources`, el agente no
  puede ignorarlas. Si una URL no carga, registrar el error en bitácora y
  continuar.
- **Bitácora obligatoria**: escribir en ella después de CADA fase. Sin
  bitácora no hay trazabilidad.
- **Intake mínimo**: si el usuario no puede responder `problem.statement`,
  sugerir ejecutar solo Fase 1 (descubrimiento) primero.
- **Subskills del Hub**: si una subskill no está instalada y el usuario no
  quiere instalarla, ofrecer ejecutar la fase con razonamiento directo de
  Hermes (modo degradado, marcar en bitácora).

## Verification

1. `skills_list` muestra `ree-producto` en categoría `productivity`.
2. Invocar `/ree-producto` → presenta intake interactivo.
3. Completar intake mínimo con `sources` → gate de intake pasa.
4. Seleccionar solo Fase 1 → carga `market-profile-builder`, ejecuta,
   post-gate evalúa, bitácora se actualiza.
5. Probar fallback sin `TYPESAFE_API_KEY` → gates funcionan con Hermes.
6. Verificar bitácora en `<base_dir>/.ree-producto-session-*.md`.
