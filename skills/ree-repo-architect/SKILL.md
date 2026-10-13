---
name: ree-repo-architect
description: "Genera diagramas C4 + ADRs desde F6 de /ree-producto."
version: 1.0.0
author: Hermes
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [repository, architecture, c4, excalidraw, adr]
    related_skills:
      - ree-repo
      - ree-producto
      - excalidraw
      - typesafe-ai
required_environment_variables:
  - name: TYPESAFE_API_KEY
    prompt: "TypeSafe API key para gates Jev de validacion"
    help: "Obten una en https://console.typesafe.ai — la skill funciona en modo fallback sin ella"
    required_for: "gates de validacion automatizados (noul/score)"
---

# /ree-repo-architect — Diagramas de Arquitectura

Traduce la arquitectura de Fase 6 del `/ree-producto` a diagramas C4 formales
(contexto, contenedor, componente) y ADRs. Es la segunda fase del pipeline
`/ree-repo`.

## When to Use

- `/ree-repo` Fase 2 — llamado por la orquestadora
- "generar diagramas de arquitectura desde los docs de producto"
- "crear ADRs para las decisiones tecnicas del proyecto"

## Procedure

### Paso 0 — Verificar entorno

1. Verificar que existe `validation-report.md` desde F1 o el `base_dir` de
   `/ree-producto`.
2. Verificar que `excalidraw` esta disponible como skill:
   - `skills_list` → buscar `excalidraw`
   - Si no esta instalada: detener esta fase y pedir al usuario que la instale desde su origen. No usar herramientas de catálogo no verificadas ni sustituirla por un diagrama estático.
3. Si `TYPESAFE_API_KEY` no esta configurada, informar modo fallback.

### Paso 1 — Leer arquitectura tecnica

1. Leer `06-tech/arquitectura-tecnica.md` del output de `/ree-producto`.
2. Extraer:
   - **Stack tecnologico**: lenguajes, frameworks, librerias
   - **Componentes**: modulos, servicios, bases de datos, colas
   - **Interfaces**: APIs, eventos, schemas de datos
   - **Dependencias externas**: servicios third-party, proveedores
   - **Costos estimados**: por servicio, por componente
   - **Decisiones tecnicas**: por que se eligio cada tecnologia
3. Si el documento no existe o es insuficiente, reportar error y detener.

### Paso 2 — Generar diagramas C4

Cargar `excalidraw` y generar 3 diagramas:

#### C4-Contexto — Sistema en su ecosistema

- **Actores**: usuarios finales, administradores, sistemas externos
- **Sistemas externos**: APIs de terceros, servicios cloud, bases de datos externas
- **Sistema**: el proyecto como una caja negra
- **Relaciones**: flechas con etiquetas ("usa", "consume", "autentica")
- Nombre del archivo: `docs/architecture/C4-contexto.excalidraw`

#### C4-Contenedor — Contenedores del sistema

- **Web App**: frontend, SPA, SSR
- **API Gateway**: backend, REST, GraphQL
- **Workers**: colas, background jobs
- **Base de datos**: PostgreSQL, Redis, vector store
- **AI**: modelos LLM, embeddings
- **Almacenamiento**: S3/MinIO, PV persistente
- Nombre del archivo: `docs/architecture/C4-contenedor.excalidraw`

#### C4-Componente — Componentes internos del pipeline principal

- Enfocarse en el pipeline mas critico (ej. intake → procesamiento → respuesta)
- Cada contenedor se expande en sus componentes internos
- Nombre del archivo: `docs/architecture/C4-componente.excalidraw`

### Paso 3 — Generar ADRs

Para cada decision tecnica explicita en Fase 6, crear un Architecture Decision
Record usando el formato estandar:

```markdown
# ADR-000<N>: <Titulo de la decision>

## Contexto
[Problema que motiva la decision]

## Opciones consideradas
- [Opcion A]: [descripcion]
- [Opcion B]: [descripcion]

## Decision
[Opcion elegida con justificacion]

## Consecuencias
[Impacto positivo y negativo]

## Estado
Aceptada
```

Guardar en `docs/architecture/ADRs/ADR-0001.md`, `ADR-0002.md`, etc.
Al menos 1 ADR por decision tecnica. Como minimo 3 ADRs por proyecto.

### Paso 4 — Validar fidelidad (Jev Noul)

Ejecutar Jev noul: "Do the C4 diagrams accurately represent the technical
decisions in Fase 6?"
- State: lista de decisiones de Fase 6 + nombres de diagramas generados
- Umbral: ≥ 0.7
- Si falla: corregir diagramas basandose en el feedback de Jev

### Paso 5 — Gate F2 (Jev Score)

| Level | Descripcion |
|-------|-------------|
| `inaccurate` | Diagramas no reflejan las decisiones de Fase 6, faltan ADRs |
| `partial` | Algunos diagramas correctos, faltan ADRs o hay imprecisiones |
| `accurate` | Diagramas correctos, ADRs cubren decisiones principales |
| `comprehensive` | Diagramas detallados, ADRs completos, cobertura total |

State: resultados de noul, lista de diagramas generados, cantidad de ADRs.

### Paso 6 — Bitacora

1. Actualizar `.ree-repo-session-<timestamp>.md`:
   - Diagramas generados (paths)
   - ADRs creados (paths)
   - Gate F2 score
   - Decision: continuar / corregir

## Jev Integration Points

| Punto | Que evalua | Primitivo | Pregunta / Opciones |
|-------|-----------|-----------|---------------------|
| Fidelidad C4 | ¿Los diagramas reflejan Fase 6? | `noul` | "Do the C4 diagrams accurately represent the technical decisions in Fase 6?" |
| Gate F2 | Calidad de diagramas | `score` | `inaccurate`, `partial`, `accurate`, `comprehensive` |

## Artefactos

| Archivo | Descripcion |
|---------|-------------|
| `docs/architecture/C4-contexto.excalidraw` | Diagrama C4 nivel contexto |
| `docs/architecture/C4-contenedor.excalidraw` | Diagrama C4 nivel contenedor |
| `docs/architecture/C4-componente.excalidraw` | Diagrama C4 nivel componente |
| `docs/architecture/ADRs/ADR-0001.md` (y siguientes) | Architecture Decision Records |

## Pitfalls

- **Diagramas sin actores externos:** C4-contexto debe mostrar usuarios y sistemas externos. No dibujar solo el sistema aislado.
- **ADRs sin opciones consideradas:** un ADR que solo dice "elegimos X" sin mostrar que alternativas se evaluaron no es documentacion de arquitectura, es propaganda.
- **ADRs sin estado:** cada ADR debe tener `## Estado` (Aceptada, Propuesta, Rechazada, Deprecada). Las decisiones que cambiaron deben tener ADRs que las deprecen.
- **Cobertura incompleta de ADRs:** crear un ADR por cada decision tecnica con trade-offs; el minimo de tres por proyecto solo aplica cuando existen menos de tres decisiones documentadas.
- **Diagramas sin Fase 6:** si el documento de arquitectura no existe o es demasiado generico, detener en Paso 1 y pedir al usuario completarlo en /ree-producto.

## Verification

1. `skills_list` muestra `ree-repo-architect` en `productivity`.
2. Ejecutar sobre proyecto con Fase 6 completa → 3 diagramas .excalidraw generados.
3. Ejecutar sobre proyecto sin Fase 6 → error en Paso 1.
4. Gate F2 ≥ `accurate` pasa con diagramas correctos y ≥ 3 ADRs.
5. Sin TYPESAFE_API_KEY → gates con `[hermes-judgment]`.
6. Bitacora actualizada con paths de los artefactos.