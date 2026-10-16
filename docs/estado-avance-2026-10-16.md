# Estado de avance — 2026-10-16

**Fase activa:** Consolidación del conocimiento operativo de Hermes y transferencia del método de trabajo a producción (Hermes intake → Paperclip ejecución).

## Contexto

El tap `reevolutiva/hermes-skills` evolucionó de 3 skills iniciales a un pipeline completo de habilitación de repositorios (12 skills, 36 archivos), con reglas de PR, branch protection y CI. En paralelo, los agentes de Hermes aprendieron en producción (imac27 y vm-services) conocimientos que nunca migraron al tap. Esta fase cierra esa brecha y documenta el siguiente estado objetivo.

## Hallazgos del inventario de skills (agent-skill-research)

Se inspeccionaron los árboles Hermes de los hosts `imac27` y `vm-services` en modo solo-lectura entre el 15 y 16 de octubre de 2026. Los artefactos completos están en `~/.hermes/cache/scratch/agent-skill-research/`.

### Resumen cuantitativo

| Métrica | imac27 | vm-services |
|---|---|---|
| Skills activas en el árbol común | 230 | 73 |
| Skills de perfil adicionales | — | 129 (abogado) |
| Skills corporativas (tap) | 12 | 9 |
| Skills corporativas con divergencia de contenido | 3 | 0 |
| Skills aprendidas no-tap | 97 | 6 |
| Skills enlazadas a proyecto (`reevolutiva-di`) | 63 | 0 |
| Skills archivadas | 5 | 0 |
| Eventos en curator ledger | 572 | 172 |
| Informes de curator disponibles | 7 | 2 |

### Principales divergencias con el tap

- `reevolutiva-infra-gitops`: divergente en contenido en imac27 (93 KB vs 74 KB en el tap). Aporta conocimiento sobre placement, gates, HelmRelease, Longhorn y más. En vm-services está en `.hub/quarantine`, no activa.
- `wordpress-bedrock-migration`: divergente en imac27 (549 líneas vs 476 en el tap).
- `wordpress-performance-diagnosis`: divergente en imac27 (295 líneas vs 281 en el tap).

Los skills `ree-repo` y subskills, `ree-producto` y `ree-learn` son idénticos por SHA-256 entre el tap y ambos hosts.

Además existen 4 archivos nuevos de vm-services y 3 de imac27 que no están en el tap actual (ver `rescate/2026-10-15/MANIFEST.md`).

### Perfil de aprendizaje

- **imac27**: 36 skills creadas por agentes (`created_by=agent`), 19 por proceso `learn`. Mayor actividad en `reevolutiva-infra-gitops` (293 usos, 123 patches), `ree-kanban-ops` (113), y `wordpress-bedrock-migration` (71).
- **vm-services**: `paperclip-opencode-litellm` lidera con 70 usos y 52 patches. Contiene reglas de delegación, objetivos de Company, estructura de workspaces y cierre de tareas. `reevolutiva-infra-gitops` también tiene alta actividad (99 usos).

### Estado del curator

Los 9 informes disponibles indican `consolidation off`: cero tool calls de consolidación y cero skills nuevas generadas automáticamente. El conocimiento hay que adjudicarlo explícitamente.

### Seguridad y datos sensibles

- Todos los archivos transferidos desde los hosts fueron redactados antes de copiarse (patrones de API keys, tokens, secrets).
- Los volcados de sesión (`*-linked-sessions-redacted.json`) son temporales y no deben compartirse sin nueva revisión.
- `.usage.json` solo exporta contadores y fechas; MEMORY/USER.md fueron inventariados por tamaño, no copiados.

## Gaps pendientes

1. **Divergencias del tap sin adjudicar** (3 skills de infraestructura con diferencias de contenido sustantivas).
2. **Método Paperclip no documentado formalmente**: el flujo Hermes→Paperclip se practica en vm-services pero no existe una skill metodológica genérica en el tap.
3. **Curator no está operando como herramienta de consolidación** — hay que decidir si se activa, se reemplaza, o se integra con el flujo de aprendizaje manual.
4. **No hay pruebas sobre la salud del runtime Hermes en vm-services** — el árbol refleja skills installadas, no confirmación de que el gateway responda.
5. **No hay hook CI→Teams post-push** (issues #9 y #10 abiertos).
6. **imac27 está saliendo de servicio como runtime de producción**: el conocimiento que reside ahí debe transferirse antes de que el host se retire.

## Plan de consolidación (próximo slice)

### Meta

Activar el flujo **Hermes intake → Paperclip ejecución → verificación → aprendizaje** como método estándar y versionado, con conocimiento verificado para cada dominio.

### Hitos del slice

| # | Hito | Criterio de éxito |
|---|---|---|
| H1 | Crear intake en Paperclip para definir la metodología | Company/proyecto/agentes Paperclip creados; spec metodológica aprobada por el usuario |
| H2 | Fusionar divergencias del tap con juicio de conservación | PR mergeado con contenidos adjudicados, sin regresiones; `rescate/` marcado como aplicado |
| H3 | Crear skill `hermes-paperclip-method` o equivalente | Skill instalada y operativa con flujo intake→handoff→review→transferencia documentado |
| H4 | Validar extremo a extremo | Prueba real: intake de un requerimiento → delegación a Paperclip → ejecución → verificación → captura de aprendizaje |
| H5 | Publicar en el tap y activar en vm-services | PR mergeado en el tap, `hermes skills update` ejecutado en vm-services, skill activa verificada |

### Reglas de trabajo (ya vigentes)

- Todo cambio al repo en rama + PR; nunca push directo a `main`.
- Una skill = una responsabilidad. Si hereda métodos distintos, dividir.
- Inventario atómico: `AGENTS.md`, `README.md`, `skills.sh.json` y CI siempre en el mismo PR.
- Validación pre-commit: `python3 scripts/validate-skills-catalog.py`.
- Sin secretos en Git: claves solo por AKV o variables de entorno.

## Artefactos

- `docs/estado-avance-2026-10-16.md` — este documento.
- `rescate/2026-10-15/MANIFEST.md` — divergencias de archivos entre las tres copias.
- `~/.hermes/cache/scratch/agent-skill-research/` — inventarios CSV/JSON, curator y sesiones redactadas.
- `INFORME.md` en el mismo directorio — reporte metodológico completo de la investigación.