# Rescate 2026-10-15 — divergencia de skills del tap

Origen: levantamiento del 2026-10-15 (Hermes Agent sobre `imac27`).
Motivo: tres copias vivas del mismo material, sólo una versionada, y el host que las
usaba a mano (`imac27`) está en retiro como runtime.

## Las tres copias

| Copia | Ruta | Origen |
|---|---|---|
| `origin/main` del tap | `skills/` | la única versionada |
| clon de `vm-services` | `~/reevolutiva-skills` (raíz del home, fuera de `/data/workspace`) | copia con trabajo sin commitear |
| copias locales de `imac27` | `~/.hermes/skills/infrastructure/*` | ediciones directas en el host |

## Qué entra en su lugar (aditivo, ninguna versión de `main` se pierde)

Archivos nuevos en las tres copias o superconjunto estricto de `main`:

| Archivo | Origen | Líneas |
|---|---|---|
| `skills/reevolutiva-infra-gitops/references/kustomization-operational-status.md` | vm-services | 101 |
| `skills/reevolutiva-infra-gitops/references/almacenamiento-nodos.md` | vm-services | 112 |
| `skills/reevolutiva-infra-gitops/references/http-performance-tailnet.md` | vm-services | 105 |
| `skills/reevolutiva-infra-gitops/templates/handoff-con-gates.md` | vm-services | 77 |
| `skills/reevolutiva-infra-gitops/references/declarar-crs-de-runtime-en-git.md` | imac27 | 98 |
| `skills/wordpress-bedrock-migration/SKILL.md` | vm-services | 479 |
| `skills/wordpress-performance-diagnosis/SKILL.md` | vm-services | 315 |

## Qué queda pendiente de adjudicación (no se tocó `main`)

| Archivo | `main` | vm-services | imac27 | Por qué no se puede mergear solo |
|---|---|---|---|---|
| `reevolutiva-infra-gitops/SKILL.md` | 805 | 1063 | 850 | tres reescrituras independientes; ninguna es superconjunto de otra (main pierde 35 líneas con la de vm-services y 63 con la de imac27). Merge 3-way automático pierde secciones enteras de imac27: no se aplicó |
| `reevolutiva-infra-gitops/references/ghcr-imagenes.md` | 183 | 105 | 183 | son dos documentos distintos con el mismo nombre: `main`=`imac27` cubren *visibilidad y pull anónimo en GHCR*; la de vm-services cubre *jerarquía de registros + build multi-arch*. Decidir renombre (p. ej. `publicacion-imagenes-multiarch.md`) o fusión |
| `reevolutiva-infra-gitops/references/cloudflare-tunnel.md` | 196 | 196 | 196 | la de imac27 sustituye 8 líneas de `main`; el resto es idéntico |
| `reevolutiva-infra-gitops/references/tailscale-acl.md` | 62 | 62 | 62 | la de imac27 sustituye 2 líneas de `main` |
| `wordpress-bedrock-migration/SKILL.md` | 476 | 479 | 549 | la de vm-services es superconjunto de `main` (ya aplicada), pero la de imac27 aporta 13 líneas propias que no están en ninguna otra |
| `wordpress-performance-diagnosis/SKILL.md` | 281 | 315 | 295 | la de vm-services es superconjunto de `main` (ya aplicada), pero la de imac27 aporta 14 líneas propias |

## Cómo se verificó que no se pierde nada

- Para cada archivo se calculó el conjunto de líneas no vacías y se comparó contra las otras
  dos copias: `vms ⊇ main` e `imac ⊇ main` se midieron por ausencia de líneas, no por tamaño.
- Los archivos donde ninguna copia es superconjunto **no se aplicaron**: se conservan completos
  bajo `rescate/2026-10-15/`.
- El clon de `vm-services` no tenía commits locales (su `HEAD` era `origin/main`): todo su
  aporte estaba en el árbol de trabajo, y está todo acá.

## Hashes de lo conservado

| Archivo | sha256 (12) |
|---|---|
| `rescate/2026-10-15/vm-services/reevolutiva-infra-gitops.SKILL.md` | `914b997d0c61` |
| `rescate/2026-10-15/vm-services/reevolutiva-infra-gitops.references-ghcr-imagenes.md` | `c0bb95920fb8` |
| `rescate/2026-10-15/imac27/reevolutiva-infra-gitops.SKILL.md` | `15e00b13c0a3` |
| `rescate/2026-10-15/imac27/reevolutiva-infra-gitops.references-cloudflare-tunnel.md` | `974f37703066` |
| `rescate/2026-10-15/imac27/reevolutiva-infra-gitops.references-tailscale-acl.md` | `549bd18adcb9` |
| `rescate/2026-10-15/imac27/wordpress-bedrock-migration.SKILL.md` | `eec4a66a9813` |
| `rescate/2026-10-15/imac27/wordpress-performance-diagnosis.SKILL.md` | `831edd7de7e5` |

Procedencia de las fuentes: host `vm-services` → `~`/reevolutiva-skills`; host `imac27` → `~/.hermes/skills/infrastructure/`.
