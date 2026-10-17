# Matriz de adjudicación — Slice 4 (2026-10-17)

Fuente: `rescate/2026-10-15/MANIFEST.md`. Verificación contra skills canónicas del tap (`data/workspace/projects/hermes-skills/skills/`).

## Archivos nuevos (7/7 en el tap)

| # | Archivo | Origen | Líneas MANIFEST | Líneas en tap | Estado |
|---|---------|--------|-----------------|---------------|--------|
| 1 | `references/kustomization-operational-status.md` | vm-services | 101 | 101 | ✓ presente |
| 2 | `references/almacenamiento-nodos.md` | vm-services | 112 | 112 | ✓ presente |
| 3 | `references/http-performance-tailnet.md` | vm-services | 105 | 105 | ✓ presente |
| 4 | `templates/handoff-con-gates.md` | vm-services | 77 | 77 | ✓ presente |
| 5 | `references/declarar-crs-de-runtime-en-git.md` | imac27 | 98 | 98 | ✓ presente |
| 6 | `wordpress-bedrock-migration/SKILL.md` | vm-services | 479 | 479 | ✓ superconjunto aplicado |
| 7 | `wordpress-performance-diagnosis/SKILL.md` | vm-services | 315 | 315 | ✓ superconjunto aplicado |

## Divergencias en archivos existentes (6/6 adjudicadas)

| # | Archivo | Decisión | Razón |
|---|---------|----------|-------|
| 1 | `reevolutiva-infra-gitops/SKILL.md` (×3 copias) | **Fusionado manualmente.** La skill canónica actual (~1200 líneas) integra las tres copias: `main` (805), `vm-services` (1063), `imac27` (850). El merge manual ocurrió en sesión del 2026-10-15 y preserva todas las secciones únicas de cada copia (Tailscale SSH, nodo Flatcar, DNS del tailnet, LiteLLM cache/guardrails/key rotation, WordPress Cloudflare tunnel, etc.). | Ninguna copia era superconjunto; se requirió merge manual con revisión sección por sección. |
| 2 | `references/ghcr-imagenes.md` (2 versiones) | **Fusionado.** El archivo canónico (183 líneas) preserva el contenido de `main`=`imac27` (visibilidad y pull anónimo en GHCR) y absorbió el contenido de `vm-services` (jerarquía de registros + build multi-arch) en secciones adicionales. | Eran dos documentos distintos con el mismo nombre. La fusión produjo un solo archivo con ambas coberturas. |
| 3 | `references/cloudflare-tunnel.md` | **Aplicada la versión de imac27.** Las 8 líneas sustituidas corrigen información de ruteo. | El resto del archivo (188 líneas) era idéntico entre las tres copias. |
| 4 | `references/tailscale-acl.md` | **Aplicada la versión de imac27.** Las 2 líneas sustituidas corrigen la regla de ACL. | El resto del archivo (60 líneas) era idéntico entre las tres copias. |
| 5 | `wordpress-bedrock-migration/SKILL.md` (+13 líneas imac27) | **Ya incorporadas.** La skill canónica actual (479 líneas) contiene todas las secciones de imac27: los pitfalls de `wp-config.php` de Demyx, `vendor/`, `index.php` 404 de OLS, readiness probe, fsGroup, tunnel cutover, multi-arch. Las 13 líneas "propias" eran reordenamiento estructural, no contenido neto nuevo. | La copia de imac27 (549 líneas) tenía las mismas secciones que la canónica pero con estructura distinta (subsecciones con `###` vs `##`). |
| 6 | `wordpress-performance-diagnosis/SKILL.md` (+14 líneas imac27) | **Ya incorporadas.** La skill canónica actual (315 líneas) contiene todas las secciones de imac27: "El sitio CAÍDO", auditoría de caché, pitfalls de OLS/LSAPI, `fsGroup` vs usuario PHP. Las 14 líneas "propias" eran reordenamiento estructural. | La copia de imac27 (295 líneas) es subconjunto estricto de la canónica actual. |

## Conclusión

**Las 6 divergencias del rescate 2026-10-15 están adjudicadas.** El merge ocurrió en la sesión del 2026-10-15 que produjo el propio rescate: las skills canónicas del tap contienen todo el conocimiento de las tres copias (main, vm-services, imac27). Los 7 archivos nuevos están presentes en el tap con los conteos de líneas exactos del MANIFEST. No hay contenido huérfano.

## Verificación (Fase 4d)

```bash
cd /data/workspace/projects/hermes-skills
python3 scripts/validate-skills-catalog.py  # OK: 16 skills
```

El directorio `rescate/2026-10-15/` se conserva como registro histórico de la operación de rescate; su contenido ya fue absorbido por las skills canónicas.