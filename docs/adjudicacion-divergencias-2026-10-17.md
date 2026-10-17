# Matriz de adjudicación — Slice 4 (2026-10-17)

**Estado: investigación corregida; adjudicación pendiente de integrar.** El primer borrador de esta matriz afirmó erróneamente que el contenido del rescate ya estaba integrado en la rama canónica del PR #17. La comparación real de esa rama identificó contenido exclusivo todavía pendiente. No usar las decisiones provisionales anteriores como resultado final.

Fuente: `rescate/2026-10-15/MANIFEST.md`. Comparación de las fuentes del rescate contra las skills de la rama `feat/ree-paperclip-adapter-diagnosis`.

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

## Divergencias: hallazgos línea por línea

| # | Archivo | Hallazgo comprobado en la rama del PR #17 | Disposición provisional |
|---|---------|--------------------------------------------|-------------------------|
| 1 | `reevolutiva-infra-gitops/SKILL.md` (×3 copias) | La copia vm-services aporta bloques sustantivos ausentes, incluidos limpieza segura de jobs efímeros, repos de servicio separados de Flux, diagnóstico de UI LiteLLM con mediciones cliente/pod, capacidad Longhorn, ownership SSA de CRs de runtime, backend Paperclip, diferencias DNS por nodo, preservación de usuarios/roles Paperclip y handoff entre sesiones. imac27 también tiene secciones exclusivas; parte parece histórica/topología sensible y exige cotejo actual antes de aceptar. | **Pendiente:** adjudicar cada bloque con evidencia actual; aceptar/fusionar contenido generalizable, descartar solo lo obsoleto o duplicado con razón, redactar datos sensibles. No asumir que todo el snapshot es vigente. |
| 2 | `references/ghcr-imagenes.md` | La rama tiene el documento `main` de 183 líneas; la fuente vm-services de 105 líneas es un documento distinto con jerarquía de registros, publicación multi-arch y ownership GitOps. | **Pendiente:** renombrar la fuente multi-arch a una referencia independiente (p. ej. `publicacion-imagenes-multiarch.md`) o fusionarla tras validar que sus detalles no contradicen la política actual del registry. |
| 3 | `references/cloudflare-tunnel.md` | El snapshot imac27 tiene ocho líneas diferentes; incluye identificadores de cuenta/túnel, nombres de secretos y detalle de credenciales. | **Pendiente:** comparar semanticamente; conservar solo correcciones técnicas verificadas, usar placeholders y eliminar nombres/datos de credenciales del artefacto. |
| 4 | `references/tailscale-acl.md` | Dos líneas del snapshot imac27 difieren; el resto coincide. Contiene nombres de secretos/credenciales en el rescate. | **Pendiente:** comparar semanticamente; preservar la regla corregida solo tras verificarla, y sustituir cualquier nombre sensible por el canal autorizado genérico. |
| 5 | `wordpress-bedrock-migration/SKILL.md` | La copia imac27 aporta contenido ausente: cotejo fila por fila de `wp_blogs` contra hosts, diagnóstico local para separar 404 de WP/ruteo, auditoría de navegador CDP, restauración de adjuntos/metadata/cache, transferencia alternativa de uploads para origen con poco espacio temporal y consulta SQL PDO sin WP-CLI. También incluye ruta local de script CDP y comandos de limpieza destructivos que requieren revisión/redacción. | **Pendiente:** aceptar/fusionar lo portable y útil; eliminar ruta machine-local, evitar instrucciones de borrado amplio, revisar y generalizar comandos de transferencia/credenciales. |
| 6 | `wordpress-performance-diagnosis/SKILL.md` | La copia imac27 aporta auditoría CDP en navegador y diagnóstico/purga de 404 stale de LiteSpeed Cache tras restaurar archivos. | **Pendiente:** fusionar la cobertura duplicada una sola vez y hacer la herramienta CDP portable; conservar el procedimiento de caché con gate funcional. |

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
