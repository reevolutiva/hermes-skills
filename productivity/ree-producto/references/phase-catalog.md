# Phase Catalog — /ree-producto

Catálogo completo de fases con subskills, auxiliares y entregables esperados.

---

## Fase 1: Descubrimiento e Investigación de Mercado

- **Subskill principal**: `market-profile-builder`
- **Subskills auxiliares**: `competitor-intelligence`, `opportunity-mapper`
- **Entregables**:
  - `01-discovery/market-overview.md`
  - `01-discovery/competitor-matrix.md`
  - `01-discovery/opportunities.md`
- **Fuentes relevantes**: URLs de mercado, documentos de análisis previo

## Fase 2: Definición de Usuario y Personas

- **Subskill principal**: `persona-niche-lab`
- **Subskills auxiliares**: `ux-researcher-designer` (Hub ⬇️)
- **Entregables**:
  - `02-users/personas.md`
  - `02-users/journey-maps.md`

## Fase 3: Estrategia de Producto

- **Subskill principal**: `product-strategy-session` (Hub ⬇️)
- **Subskills auxiliares**: `roadmap-planning` (Hub ⬇️)
- **Entregables**:
  - `03-strategy/product-strategy.md`
  - `03-strategy/roadmap.md`

## Fase 4: Especificación del Producto (PRD)

- **Subskill principal**: `prd-master` (Hub ⬇️)
- **Subskills auxiliares**: `product-specs-writer` (Hub ⬇️)
- **Entregables**:
  - `04-prd/prd.md`
  - `04-prd/functional-specs.md`

## Fase 5: Diseño Visual y Sistema de Diseño

- **Subskill principal**: `design-md` (local ✅)
- **Subskills auxiliares**: `brand-strategy-writer`, `frontend-design` (Hub ⬇️)
- **Entregables**:
  - `05-design/DESIGN.md`
  - `05-design/brand-guide.md`
  - `05-design/mockups/`

## Fase 6: Documentación Técnica

- **Subskill principal**: `diataxis` (Hub ⬇️)
- **Subskills auxiliares**: `technical-design-doc-creator` (Hub ⬇️), `create-adr` (Hub ⬇️)
- **Entregables**:
  - `06-technical/architecture.md`
  - `06-technical/adrs/`
  - `06-technical/api-docs/`

## Fase 7: Go-to-Market y Lanzamiento

- **Subskill principal**: `gtm-strategy` (Hub ⬇️)
- **Subskills auxiliares**: `launch-strategy` (Hub ⬇️)
- **Entregables**:
  - `07-gtm/gtm-plan.md`
  - `07-gtm/launch-checklist.md`

## Fase 8: Métricas, Analytics y Mejora Continua

- **Subskill principal**: `product-analytics` (Hub ⬇️)
- **Subskills auxiliares**: `lean-analytics` (Hub ⬇️)
- **Entregables**:
  - `08-metrics/metrics-framework.md`
  - `08-metrics/dashboard-spec.md`

---

## Skills transversales

| Skill | Rol | Estado |
|-------|-----|--------|
| `research-writing-harness` | QA de calidad | ✅ Local |
| `grounded-citations` | Verificación de fuentes | ✅ Local |
| `typesafe-ai` | Motor de gates Jev | ✅ Local |
| `plan` | Modo planificación | ✅ Local |

---

## Instalación de subskills del Hub

```bash
# PRD
hermes skills install skills-sh/majiayu000/spellbook/prd-master

# Documentación técnica
hermes skills install skills-sh/joshuadavidthomas/agent-skills/diataxis
hermes skills install skills-sh/tech-leads-club/agent-skills/technical-design-doc-creator
hermes skills install skills-sh/tech-leads-club/agent-skills/create-adr

# Estrategia
hermes skills install skills-sh/deanpeters/product-manager-skills/product-strategy-session
hermes skills install skills-sh/deanpeters/product-manager-skills/roadmap-planning

# UX
hermes skills install skills-sh/ovachiever/droid-tings/ux-researcher-designer

# Diseño
hermes skills install skills-sh/anthropics/skills/frontend-design

# GTM
hermes skills install skills-sh/phuryn/pm-skills/gtm-strategy
hermes skills install skills-sh/coreyhaines31/marketingskills/launch-strategy

# Métricas
hermes skills install skills-sh/alirezarezvani/claude-skills/product-analytics
hermes skills install skills-sh/wondelai/skills/lean-analytics
```
