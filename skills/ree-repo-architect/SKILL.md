---
name: ree-repo-architect
description: "Genera diagramas C4 + ADRs desde F6"
version: 1.0.0
author: Hermes
license: MIT
category: productivity
tags: [ree-repo, architecture, c4, excalidraw, adr]
---

# ree-repo-architect — F2: Diagramas de Arquitectura

Traduce la arquitectura técnica de Fase 6 (`06-tech/arquitectura-tecnica.md`) a diagramas C4 formales y Architecture Decision Records (ADRs). Consume la validación de F1: no se diagrama si los docs fuente no pasaron el gate.

## When to Use

- Desde `/ree-repo` orquestadora (F2), después de F1 Validate.
- "generar diagramas de arquitectura", "crear C4 del proyecto", "documentar decisiones técnicas".
- Trigger: el usuario quiere visualizar la arquitectura desde los docs de producto.

## Procedure

### 1. Cargar arquitectura técnica

Leer `06-tech/arquitectura-tecnica.md` desde `<output.base_dir>/`.
Extraer:
- Stack tecnológico (lenguajes, frameworks, bases de datos)
- Interfaces y APIs (REST, gRPC, GraphQL, message queues)
- Componentes del sistema (servicios, workers, pipelines)
- Sistemas externos (APIs de terceros, servicios cloud)
- Usuarios y roles del sistema
- Decisiones de infraestructura (K3s, Tailscale, AKV)

### 2. Generar diagramas C4

Usar skill `excalidraw` para generar tres niveles:

#### Nivel 1: Contexto
`docs/architecture/C4-contexto.excalidraw`
- Sistema en su ecosistema
- Usuarios (tipos de usuario, roles)
- Sistemas externos (APIs, servicios cloud, herramientas)
- Flujos principales de interacción

#### Nivel 2: Contenedor
`docs/architecture/C4-contenedor.excalidraw`
- Contenedores: Web App, API Gateway, Workers, PostgreSQL, AI services
- Conexiones entre contenedores (HTTP, gRPC, message queues)
- Responsabilidades de cada contenedor

#### Nivel 3: Componente
`docs/architecture/C4-componente.excalidraw`
- Componentes internos del pipeline principal
- Estructura de agentes si el proyecto usa agentes AI
- Flujo de datos entre componentes

### 3. Generar ADRs

Para cada decisión técnica identificada en Fase 6, crear un ADR en `docs/architecture/ADRs/`:
- `001-stack-principal.md` — stack tecnológico elegido
- `002-modelo-despliegue.md` — modelo GitOps/K3s elegido
- `003-exposicion.md` — Tailscale vs Cloudflare Tunnel
- `004-secretos.md` — AKV vs SOPS
- ADRs adicionales según decisiones particulares del proyecto

Formato canónico de ADR:
```markdown
# ADR-NNN: Título

**Status**: proposed | accepted | deprecated | superseded
**Date**: YYYY-MM-DD
**Deciders**: [lista]

## Context
[Problema y contexto]

## Decision
[Qué se decidió y por qué]

## Consequences
[Lo que se vuelve más fácil y más difícil]
```

### 4. Gate F2

Evaluar con Jev Score:
- `inaccurate` — diagramas no reflejan Fase 6; corregir.
- `partial` — cubre parcialmente; completar gaps.
- `accurate` — refleja fielmente las decisiones.
- `comprehensive` — cubre todo con detalle adicional.

## Jev Integration Points

| Punto | Primitivo | Pregunta |
|---|---|---|
| Fidelidad C4 | noul | "Do the C4 diagrams accurately represent the technical decisions in Fase 6?" |
| Gate F2 | score | Levels: `inaccurate`, `partial`, `accurate`, `comprehensive`. State: lista de decisiones de Fase 6 + nombres de diagramas generados. |

## Pitfalls

- **No diagramar sin F1 aprobado**: si el gate de F1 fue `insuficiente`, no ejecutar F2.
- **Diagrams must be .excalidraw**: usar el formato nativo de Excalidraw, no PNG/SVG estáticos.
- **ADRs deben ser decisiones reales**: no crear ADRs para obviedades. Solo decisiones con trade-offs.
- **C4, no UML**: mantener el modelo C4 (Contexto → Contenedor → Componente). No mezclar con UML clásico.
- **Excalidraw requiere skill `excalidraw`**: cargarla antes de generar diagramas.

## Verification

1. `docs/architecture/C4-contexto.excalidraw` existe.
2. `docs/architecture/C4-contenedor.excalidraw` existe.
3. `docs/architecture/C4-componente.excalidraw` existe.
4. `docs/architecture/ADRs/` contiene al menos 4 ADRs.
5. Gate F2 ≥ `accurate`.
6. `skills_list` muestra `ree-repo-architect` en categoría `productivity`.