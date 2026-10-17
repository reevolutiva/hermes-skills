# Siguiente slice — S4 Infra adjudicación (2026-10-17)

## Goal

Cerrar Slice 4 de adjudicación de divergencias de infraestructura (`reevolutiva-infra-gitops`) en una PR separada de los slices Paperclip ya mergeados, incorporando solo contenido validado y portable, con trazabilidad por bloque y sin secretos.

## Scope (in)

1. Adjudicar e integrar bloques pendientes de `skills/reevolutiva-infra-gitops/SKILL.md` (fuentes vm-services + imac27).
2. Resolver `references/ghcr-imagenes.md` (fusión o renombre a documento multi-arch) según política vigente del registry.
3. Consolidar los 5 archivos nuevos del MANIFEST en la rama objetivo, con referencias cruzadas válidas.
4. Actualizar estado en:
   - `docs/adjudicacion-divergencias-2026-10-17.md`
   - `docs/estado-avance-2026-10-17.md`
   - `rescate/2026-10-15/MANIFEST.md` (solo cuando haya evidencia de integración real)
5. Validar con gates de catálogo, diff y redacción de secretos.

## Scope (out)

- No tocar slices Paperclip ya mergeados (#16/#17).
- No despliegues de infraestructura ni cambios runtime en hosts.
- No merge directo a `main`.

## Inputs obligatorios

- Matriz actual: `docs/adjudicacion-divergencias-2026-10-17.md`
- Rescate histórico retirado: `/data/workspace/projects/_rescate-git/2026-10-17/retirado-reevolutiva-skills/`
  - `working-tree.diff`
  - `untracked-files.tgz`
  - `comparativa-con-main.csv`
  - `ELIMINACION-MANIFEST.txt`
- Fuentes del MANIFEST bajo `rescate/2026-10-15/`

## Branching

```bash
git checkout -b feat/reevolutiva-infra-gitops-rescue-slice4
```

## Steps

### S4.1 Inventario y clasificación por bloque

- Enumerar bloques exclusivos por tema: jobs efímeros, repos de servicio, SSA/runtime CRs, backend fuera de K8s, persistencia de usuarios/roles, handoff con gates, publicación de imágenes multi-arch.
- Para cada bloque registrar decisión: `aceptar`, `fusionar`, `renombrar`, `descartar` + razón verificable.

**Salida:** tabla cerrada en `docs/adjudicacion-divergencias-2026-10-17.md` sin estados ambiguos.

### S4.2 Integración controlada

- Aplicar solo bloques aprobados a la skill canónica y referencias.
- Generalizar rutas host-locales/IDs/credenciales a placeholders.
- Si `ghcr-imagenes.md` se separa, crear nombre final y actualizar backlinks.

**Salida:** diff mínimo, semánticamente trazable a la matriz.

### S4.3 Validación técnica

Ejecutar y registrar:

```bash
git diff --check
python3 scripts/validate-skills-catalog.py
```

- Revisión manual de secretos (token, password, key, bearer, connection string).
- Verificar que `description <= 60`, `author: Hermes`, y secciones requeridas se mantienen en skills tocadas.

**Salida:** evidencia de comandos + resultado OK.

### S4.4 Cierre documental + PR

- Actualizar `docs/estado-avance-2026-10-17.md` con estado real del slice.
- Actualizar `rescate/2026-10-15/MANIFEST.md` solo para filas efectivamente adjudicadas/integradas.
- Commit en rama y PR a `main` con alcance explícito: **solo Slice 4 infra**.

**Salida:** PR abierta, checks verdes, diff acotado.

## Validation gates

- G1: Cada bloque pendiente tiene decisión explícita y razón.
- G2: No hay secretos ni identificadores sensibles hardcodeados.
- G3: `validate-skills-catalog.py` en verde.
- G4: `git diff --check` limpio.
- G5: PR separada de cambios Paperclip ya mergeados.

## Riesgos y mitigación

- **Riesgo:** meter topología histórica no vigente.
  **Mitigación:** exigir evidencia de portabilidad; descartar detalles host-específicos.
- **Riesgo:** mezclar cambios no relacionados.
  **Mitigación:** rama/PR exclusiva Slice 4 infra.
- **Riesgo:** perder señales del clon retirado.
  **Mitigación:** respaldo completo ya guardado en `_rescate-git/2026-10-17/retirado-reevolutiva-skills/`.

## Definición de Done

- PR de Slice 4 infra abierta a `main` con solo adjudicaciones aprobadas.
- Matriz y estado actualizados coherentemente.
- Validaciones en verde y evidencia adjunta en la PR.
