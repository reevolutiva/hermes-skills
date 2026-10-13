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

Valida la coherencia global del proyecto y declara "listo para desarrollo" según el Definition of Done acordado para su destino. Ejecuta `make health` solo si hay despliegue K3s y usa Jev Score para evaluar la coherencia entre fases.

## When to Use

- Desde `/ree-repo` orquestadora (F6), después de completar las fases requeridas por el destino.
- "verificar proyecto", "checklist de deploy", "validar coherencia", "make health" (para K3s).
- Trigger: las fases requeridas por el destino están ejecutadas y se necesita la verificación final.

## Procedure

### 1. Determinar el destino y los criterios aplicables

Leer el intake y registrar el destino acordado: repo/CI solamente, servicio en
`vm-services` o workload K3s vía Flux. No exigir criterios de clúster a un repo
sin despliegue, ni asumir Paperclip o workspace si no se seleccionaron.

#### Workload K3s vía Flux (si aplica)

- Kustomization y HelmRelease, si corresponde, están Ready en la revisión esperada.
- Pods, Service, PVC y endpoint están sanos; ejecutar una transacción funcional, no solo `/health`.
- Secretos se materializan por `ExternalSecret`/SOPS y no hay valores en Git.
- Ingress y exposición coinciden con la política aprobada; placement y rollback están declarados.
- Los manifiestos viven en `reevolutiva-infra/apps/<proyecto>/`; la ubicación vive en `clusters/<activo>/apps.yaml`.

#### Servicio de sistema en vm-services (si aplica)

- Servicio systemd, endpoint y prueba funcional están sanos.
- Secretos se obtienen por el canal aprobado y el restore/rollback de datos tiene evidencia.

#### Repo sin runtime desplegado (si aplica)

- Un checkout limpio completa el setup, tests y CI documentados.
- No se marca como fallo la ausencia de Kustomization, endpoint o Paperclip cuando no forman parte del alcance.

#### Integraciones opcionales

- Verificar workspace y registro Paperclip solo si fueron seleccionados en el intake.
- `AGENTS.md`, `README.md` e `integrations/` reflejan las decisiones reales de stack y destino.

### 2. Ejecutar `make health` cuando haya K3s

Desde el Makefile de `reevolutiva-infra`, solo para un destino K3s:
```bash
make health
```
Para otros destinos, ejecutar la prueba de salud correspondiente; documentar como no aplicable lo que el proyecto no despliega.

### 3. Verificar coherencia entre fases

- ¿Los diagramas C4 reflejan el pipeline de Fase 6?
- ¿Los manifiestos en `reevolutiva-infra/apps/<proyecto>/` corresponden al repo de código y a la imagen acordada?
- ¿El placement de `clusters/<activo>/apps.yaml` coincide con la arquitectura y la capacidad del nodo?
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

### 7. Registrar y entregar la checklist

Guardar `CHECKLIST.md` en el repo del proyecto con la evidencia, los criterios no
aplicables y los bloqueos. Seguir el flujo de PR del repo; no hacer push directo a
`main` ni commitear/publicar cambios sin autorización.

## Jev Integration Points

| Punto | Primitivo | Pregunta |
|---|---|---|
| Coherencia global | score | Levels: `incoherente`, `fragmentado`, `coherente`, `excelente`. State: resúmenes de cada fase con paths de archivos generados. |
| DoD checklist | noul | "Does the project meet the DoD criteria applicable to its selected target, with evidence for runtime, secrets, rollback, docs, and optional integrations?" |
| Gate F6 | score | ≥ `coherente`. Si menor, reportar gaps y ofrecer re-ejecutar fases. |

## Pitfalls

- **No verificar sin fases requeridas**: F4 puede omitirse si no hay despliegue K3s; resolver las dependencias de las fases elegidas antes de cerrar.
- **make health requiere acceso al cluster**: si no hay conectividad VPN, `make health` fallará.
- **DoD checklist requiere evidencia**: no marcar ✅ sin verificar. Cada criterio debe tener evidencia real.
- **Coherencia no es solo checklist**: verificar que los artefactos de distintas fases no se contradicen.
- **Rollback depende del destino**: probar `flux suspend`/`resume` solo para K3s; verificar el mecanismo correspondiente para otros runtimes.

## Verification

1. `CHECKLIST.md` existe con evidencia para cada criterio aplicable y motivos para los no aplicables.
2. `make health` ejecutado para K3s; para otros destinos, prueba de salud específica ejecutada o ausencia documentada.
3. Gate de coherencia ≥ `coherente`.
4. Gate DoD noul ≥ 0.7.
5. No hay contradicciones entre diagramas C4, repo de código, manifiestos `reevolutiva-infra/apps/`, placement y AGENTS.md.
6. `skills_list` muestra `ree-repo-verify` en categoría `productivity`.