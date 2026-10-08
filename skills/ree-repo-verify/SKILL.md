---
name: ree-repo-verify
description: "Verifica coherencia global y DoD"
version: 1.0.0
author: Hermes
license: MIT
category: productivity
tags: [ree-repo, verification, dod, checklist, coherence, health]
---

# ree-repo-verify — F6: Verificación Final

Valida la coherencia global del proyecto y declara "listo para desarrollo". Ejecuta checklist alineada con Definition of Done de `proyectos-habilitacion.md`, `make health`, y gate Jev Score de coherencia entre fases.

## When to Use

- Desde `/ree-repo` orquestadora (F6), después de F2-F5.
- "verificar proyecto", "checklist de deploy", "validar coherencia", "make health".
- Trigger: todas las fases anteriores están ejecutadas y se necesita la verificación final.

## Procedure

### 1. Ejecutar checklist DoD

| Criterio | Verificación |
|---|---|
| Kustomization Ready | `flux get ks apps-<proyecto> -n flux-system` → Ready=True |
| HelmRelease Ready (si aplica) | `flux get hr <proyecto> -n <ns>` → Ready=True |
| Pods corriendo | `kubectl get pods -n <ns>` → todos 1/1 |
| Endpoint responde | `curl` al FQDN del tailnet → 200 |
| Prueba funcional | Una request completa, no solo `/health` |
| Sin secretos en Git | Todo vía `ExternalSecret` o SOPS |
| Solo accesible por tailnet | Sin rutas públicas |
| Ubicación declarada | `nodeSelector`/label del nodo, commiteado |
| Rollback probado | `flux suspend ks apps-<proyecto>` detiene; `flux resume` restaura |
| Docs al día | `AGENTS.md`, `README.md` y `integrations/` reflejan namespace, FQDN y dependencias reales |
| Workspace inicializado | Proyecto existe en `giolapietra@vm-services:/data/workspace/projects/<repo>` con git clone completo |
| Registrado en Paperclip | `paperclip project list --company <company>` muestra el proyecto |

### 2. Ejecutar make health

Desde el Makefile de `reevolutiva-infra`:
```bash
make health
```

### 3. Verificar coherencia entre fases

- ¿Los diagramas C4 reflejan el pipeline de Fase 6?
- ¿Los manifiestos en `apps/<proyecto>/` corresponden a lo definido en F3?
- ¿El harness referencia correctamente el stack de Fase 6?
- ¿`.env.example` contiene todas las variables que el código y `externalsecret.yaml` referencian?

### 4. Gate final (Jev Score)

Coherencia global:
- `incoherente` — contradicciones graves; requiere re-ejecutar fases.
- `fragmentado` — gaps significativos; completar antes de desarrollo.
- `coherente` — sin contradicciones; listo para desarrollo.
- `excelente` — coherencia total con documentación completa.

### 5. Gate DoD (Jev Noul)

Evaluar si se cumplen todos los criterios de Definition of Done.

### 6. Generar CHECKLIST.md

Resultado de cada ítem con:
- ✅ Pass, ⚠️ Warn, ❌ Fail
- Evidencia o justificación

### 7. Commit final y push

```bash
git add CHECKLIST.md
git commit -m "chore: verificación final — checklist DoD y gate de coherencia"
git push
```

## Jev Integration Points

| Punto | Primitivo | Pregunta |
|---|---|---|
| Coherencia global | score | Levels: `incoherente`, `fragmentado`, `coherente`, `excelente`. State: resúmenes de cada fase con paths de archivos generados. |
| DoD checklist | noul | "Does the project meet all DoD criteria: Kustomization Ready, pods 1/1, endpoint 200, functional test, no secrets in Git, tailnet-only, nodeSelector, rollback, docs?" |
| Gate F6 | score | ≥ `coherente`. Si menor, reportar gaps y ofrecer re-ejecutar fases. |

## Pitfalls

- **No verificar sin fases completas**: si F2-F5 no están ejecutadas, no se puede verificar coherencia.
- **make health requiere acceso al cluster**: si no hay conectividad VPN, `make health` fallará.
- **DoD checklist requiere evidencia**: no marcar ✅ sin verificar. Cada criterio debe tener evidencia real.
- **Coherencia no es solo checklist**: verificar que los artefactos de distintas fases no se contradicen.
- **Rollback debe probarse**: no asumir que funciona. Ejecutar `flux suspend` y `flux resume`.

## Verification

1. `CHECKLIST.md` existe con resultado de cada criterio DoD.
2. `make health` ejecutado (o documentado como no disponible).
3. Gate de coherencia ≥ `coherente`.
4. Gate DoD noul ≥ 0.7.
5. No hay contradicciones entre diagramas C4, manifiestos apps/, y AGENTS.md.
6. `skills_list` muestra `ree-repo-verify` en categoría `productivity`.