# Matriz de adjudicación — Slice 4 (2026-10-17)

**Estado: investigación corregida; adjudicación pendiente de integrar.** El primer borrador de esta matriz afirmó erróneamente que el contenido del rescate ya estaba integrado en la rama canónica del PR #17. La comparación real de esa rama identificó contenido exclusivo todavía pendiente. No usar las decisiones provisionales anteriores como resultado final.

Fuente: `rescate/2026-10-15/MANIFEST.md`. Comparación de las fuentes del rescate contra las skills de la rama `feat/ree-paperclip-adapter-diagnosis`.

Fuente adicional rescatada antes de retirar un clon histórico (`/home/giolapietra/reevolutiva-skills.retirado-2026-10-15`):
- Respaldo completo en `/data/workspace/projects/_rescate-git/2026-10-17/retirado-reevolutiva-skills/`
- Incluye `working-tree.diff`, `untracked-files.tgz`, `comparativa-con-main.csv` y `ELIMINACION-MANIFEST.txt`
- El clon retirado no tenía commits locales (`local_only_commits=0`), pero sí 8 cambios de working tree y 3 archivos untracked capturados para adjudicación del Slice 4

## Archivos nuevos

Los siguientes cinco artefactos listados como nuevos en el MANIFEST existen en el workspace del tap `/data/workspace/projects/hermes-skills` con el conteo de líneas esperado, pero ese workspace tiene cambios no commiteados y está en la rama `wip/paperclip-preexisting-20261016`; su contenido aún no se ha verificado en `origin/main` ni integrado en PR #17:

| # | Archivo | Origen | Líneas MANIFEST | Estado observado |
|---|---------|--------|-----------------|------------------|
| 1 | `references/kustomization-operational-status.md` | vm-services | 101 | Existe en workspace tap; confirmar commit y contenido |
| 2 | `references/almacenamiento-nodos.md` | vm-services | 112 | Existe en workspace tap; confirmar commit y contenido |
| 3 | `references/http-performance-tailnet.md` | vm-services | 105 | Existe en workspace tap; confirmar commit y contenido |
| 4 | `templates/handoff-con-gates.md` | vm-services | 77 | Existe en workspace tap; confirmar commit y contenido |
| 5 | `references/declarar-crs-de-runtime-en-git.md` | imac27 | 98 | Existe en workspace tap; confirmar commit y contenido |

Las dos entradas del MANIFEST para las versiones vm-services de `wordpress-bedrock-migration/SKILL.md` (479 líneas) y `wordpress-performance-diagnosis/SKILL.md` (315 líneas) **ya están en la rama del PR #17** con esos conteos; se comparan con las copias imac27 más abajo.

## Divergencias adjudicadas (Slice 4 infra)

**Cada bloque tiene decisión explícita y razón verificable. Solo los aprobados se integran en la rama `feat/reevolutiva-infra-gitops-rescue-slice4`.**

| # | Bloque | Fuente | Decisión | Razón | Estado |
|---|--------|--------|----------|-------|--------|
| 1 | Limpieza de recursos efímeros y jobs históricos | vm-services | **Aceptar** | Aporta procedimiento canónico con gate declarativo y poda backfill; no tiene datos sensibles. | ✅ Integrado en SKILL.md |
| 2 | Repos de servicio separados de la fuente Flux | vm-services | **Aceptar** | Generaliza el patrón multi-repo observado en producción; portable y sin credenciales. | ✅ Integrado en SKILL.md |
| 3 | Almacenamiento y capacidad de un nodo (disco Longhorn en fs raíz) | vm-services | **Aceptar con guardarraíles** | Información crítica de capacidad; delega detalle a `references/almacenamiento-nodos.md`. Incluye aviso explícito de que `mkfs` está prohibido para el agente. | ✅ Integrado en SKILL.md |
| 4 | Longhorn Node CRs + Flux SSA: ownership co-poseído | vm-services | **Aceptar** | Patrón de migración segura de discos con dos PRs y dry-run emulando Flux; remite a referencia. | ✅ Integrado en SKILL.md |
| 5 | Backend fuera de K8s detrás de Service sin selector (Paperclip) | vm-services | **Aceptar** | Diagnóstico genérico de `connection refused` por bind local vs IP de nodo; no tiene identificadores sensibles. | ✅ Integrado en SKILL.md |
| 6 | Handoff entre sesiones (traspaso con gates) | vm-services | **Aceptar** | Procedimiento con plantilla `templates/handoff-con-gates.md`; estandariza traspasos entre sesiones. | ✅ Integrado en SKILL.md |
| 7 | Jerarquía de registros + publicación multi-arch (ghcr-imagenes) | vm-services | **Renombrar e integrar en referencia existente** | La canónica de `main` cubría pull anónimo y visibilidad GHCR; la copia vm-services cubre jerarquía de registros y build multi-arch. Se fusionaron ambas en `references/ghcr-imagenes.md`: sección `## Jerarquía de registros` + `## Publicar una imagen` + `## Higiene: objetos aplicados a mano`. La referencia ahora es la fuente autoritativa de ambos temas. | ✅ Fusionado en ghcr-imagenes.md |
| 8 | Secciones imac27 de `reevolutiva-infra-gitops/SKILL.md` | imac27 | **Descartar** | Contenido topología-sensible (identificadores de cuenta, nombres de secretos, direcciones de host) o ya presente en la canónica actualizada. | ❌ Descartado |

### WordPress (imac27) — pendientes para slice separado

| # | Bloque | Fuente | Decisión | Razón |
|---|--------|--------|----------|-------|
| 9 | `wordpress-bedrock-migration/SKILL.md` (13 líneas propias) | imac27 | **Pendiente: slice WordPress** | Aporta diagnóstico CDP, restauración de adjuntos y transferencia alternativa; requiere revisión de rutas machine-local y comandos destructivos. |
| 10 | `wordpress-performance-diagnosis/SKILL.md` (14 líneas propias) | imac27 | **Pendiente: slice WordPress** | Aporta auditoría CDP y purga de caché stale; requiere generalización. |

### Cloudflare / Tailscale — pendientes para slice separado

| # | Bloque | Fuente | Decisión | Razón |
|---|--------|--------|----------|-------|
| 11 | `references/cloudflare-tunnel.md` (8 líneas dif) | imac27 | **Pendiente: slice Cloudflare** | Incluye identificadores de cuenta/túnel y nombres de secretos; requiere redacción. |
| 12 | `references/tailscale-acl.md` (2 líneas dif) | imac27 | **Pendiente: slice Tailscale** | Incluye nombres de secretos/credenciales en el rescate; requiere sustitución por placeholders. |

## Verificación ejecutada

- La comparación de líneas no vacías halló 246 líneas de vm-services y 120 de imac27 ausentes de la skill GitOps de esta rama.
- Halló 72 líneas de la copia imac27 de Bedrock y 25 de Performance ausentes de las skills de esta rama.
- La comparación semántica de esas diferencias está en curso; los conteos de línea no se usan como prueba de equivalencia.
- Los conteos de archivos del workspace del tap son evidencia de presencia local únicamente, no de que estén commiteados, en `main` o en PR #17.

## Próximos pasos obligatorios para cerrar Slice 4

1. Completar la clasificación de cada bloque exclusivo (aceptar, fusionar, descartar o renombrar) con razón verificable.
2. Implementar únicamente las adjudicaciones aceptadas en las skills de la rama correcta; no copiar snapshots completos a ciegas.
3. Actualizar el MANIFEST solo cuando la adjudicación real esté aplicada y el estado de commit/PR verificado.
4. Ejecutar `git diff --check`, `python3 scripts/validate-skills-catalog.py`, revisión de secretos y comprobar que el diff contiene solo adjudicaciones aprobadas.
5. Mantener PR #17 como trabajo Paperclip independiente si las adjudicaciones de infraestructura pertenecen al tap/worktree `wip/paperclip-preexisting-20261016`; no mezclar ramas sin decisión explícita.
