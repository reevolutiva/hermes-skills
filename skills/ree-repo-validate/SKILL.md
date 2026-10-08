---
name: ree-repo-validate
description: "Valida documentos /ree-producto con Jev gates"
version: 1.0.0
author: Hermes
license: MIT
category: productivity
tags: [ree-repo, validation, jev, intake, product-docs]
---

# ree-repo-validate — F1: Validación de Documentos Fuente

Valida los 8 archivos de fase generados por `/ree-producto` para determinar si tienen sustento suficiente para pasar a implementación. Usa Jev gates para evaluar cada documento y genera `docs/validation-report.md`.

## When to Use

- Desde `/ree-repo` orquestadora (F1).
- "validar docs de producto", "revisar si los docs están listos para implementar".
- Trigger: el usuario quiere verificar la calidad de los entregables de `/ree-producto` antes de scaffold.

## Procedure

### 1. Cargar documentos fuente

Leer los 8 archivos de fase desde `<output.base_dir>/`:
- `01-discovery/` — descubrimiento y análisis de dominio
- `02-personas/` — personas y segmentos
- `03-strategy/` — estrategia y features con prioridades
- `04-prd/` — PRD con requerimientos y criterios de aceptación
- `05-design/` — diseño visual y UX
- `06-tech/` — arquitectura técnica (stack, interfaces, costos)
- `07-gtm/` — estrategia de go-to-market
- `08-metrics/` — métricas de éxito y KPIs

### 2. Evaluar cada documento con Jev

Para cada documento, usar `[hermes-judgment]` como fallback si `TYPESAFE_API_KEY` no está configurada.

| Documento | Pregunta Jev (noul) |
|---|---|
| 01-discovery | ¿El descubrimiento contiene decisiones concretas sobre el dominio o solo descripciones genéricas? |
| 02-personas | ¿Las personas están definidas con necesidades y comportamientos específicos? |
| 03-strategy | ¿La estrategia define features concretas con prioridades? |
| 04-prd | ¿El PRD tiene requerimientos con criterios de aceptación medibles? |
| 05-design | ¿El diseño incluye decisiones visuales y flujos de usuario concretos? |
| 06-tech | ¿La arquitectura técnica define stack, interfaces y costos concretos? |
| 07-gtm | ¿El GTM tiene canales, timeline y presupuesto definidos? |
| 08-metrics | ¿Las métricas tienen KPIs medibles con línea base? |

### 3. Gate F1

Evaluar globalmente con Jev Score:
- `insuficiente` — requiere volver a `/ree-producto`; detener.
- `minimo` — se puede avanzar con advertencias; listar gaps.
- `solido` — listo para implementar.
- `excelente` — sobresaliente.

### 4. Generar reporte

Escribir `docs/validation-report.md` con:
- Resultado de cada documento (pass/warn/fail)
- Gate final y nivel
- Gaps detectados con recomendaciones
- Decisión: continuar o derivar a `/ree-producto`

## Jev Integration Points

| Punto | Primitivo | Pregunta |
|---|---|---|
| Calidad 01-discovery | noul | "Does the discovery contain concrete domain decisions?" |
| Calidad 02-personas | noul | "Are personas defined with specific needs and behaviors?" |
| Calidad 03-strategy | noul | "Does the strategy define concrete features with priorities?" |
| Calidad 04-prd | noul | "Does the PRD contain measurable acceptance criteria for each requirement?" |
| Calidad 05-design | noul | "Does the design include concrete visual decisions and user flows?" |
| Calidad 06-tech | noul | "Does the technical architecture specify a concrete stack, interfaces, and costs?" |
| Calidad 07-gtm | noul | "Does the GTM define channels, timeline, and budget?" |
| Calidad 08-metrics | noul | "Are metrics defined with measurable KPIs and baseline?" |
| Gate F1 | score | Levels: `insuficiente`, `minimo`, `solido`, `excelente`. Evalúa el sustento global. |

## Pitfalls

- **No duplicar /ree-producto**: si un documento no existe o es insuficiente, reportar y detener. No generar contenido de producto acá.
- **No avanzar con `insuficiente`**: si el gate da `insuficiente`, detener inmediatamente. No seguir a F2.
- **Carga progresiva de contexto**: leer los docs on-demand según la fase, no todos al inicio.
- **Jev fallback**: si `TYPESAFE_API_KEY` no está disponible, usar `[hermes-judgment]` con la misma estructura de preguntas.
- **Sin docs no hay validación**: si `<output.base_dir>` no es accesible, preguntar al usuario la ruta.

## Verification

1. `docs/validation-report.md` existe y contiene resultado de los 8 documentos.
2. El gate F1 está registrado con nivel y justificación.
3. Si nivel ≥ `minimo`, el flujo puede continuar a F2.
4. `skills_list` muestra `ree-repo-validate` en categoría `productivity`.