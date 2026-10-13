---
name: ree-repo-harness
description: "Configura AGENTS.md, integrations y setup.sh"
version: 1.0.0
author: Hermes
license: MIT
category: productivity
tags: [ree-repo, harness, agents, paperclip, hermes, restore-path, mcp]
---

# ree-repo-harness — F5: Configuración de agentes y entorno

Establece AGENTS.md, configuración de agentes, integrations y setup según el stack y destino elegidos. El repo de aplicación contiene código y CI; los manifiestos K3s viven en `reevolutiva-infra`. Paperclip, vm-services y el restore path se configuran solo cuando forman parte del alcance; no imponer AKV, systemd ni un workspace a todos los proyectos.

## When to Use

- Desde `/ree-repo` orquestadora (F5), después de F3 Scaffold; F4 es independiente y solo se ejecuta si aplica K3s.
- "configurar agentes", "preparar harness", "crear setup.sh", "registrar en Paperclip".
- Trigger: el proyecto necesita que los agentes AI puedan trabajar autónomamente.

## Procedure

### 1. Generar AGENTS.md

Incluir:
- Stack y arquitectura (desde Fase 6)
- Separación entre repo de código, `reevolutiva-infra/apps/<proyecto>/` y placement en `clusters/<activo>/apps.yaml`
- Convenciones de código (naming, linting, testing)
- Comandos comunes (`npm run dev`, `npm test` y `make health` solo si aplica K3s)
- Agentes disponibles y cómo invocarlos
- Flujo de trabajo (branch feat/ → PR → review → merge)
- Restore path y troubleshooting del runtime elegido, si aplica

### 2. Generar opencode.json (si se selecciona OpenCode)

Si OpenCode forma parte del harness, crear `config/opencode.json`:
- Permisos granulares (lectura, edición, bash)
- MCP servers requeridos
- Skills cargadas
- Agentes definidos

### 3. Registrar proyecto en Paperclip (si aplica)

- Si Paperclip fue seleccionado en intake, usar la Company proporcionada.
- Crear el proyecto apuntando al workspace acordado; no asumir vm-services si se eligió otro entorno.
- Verificar con `paperclip project list --company <company>` solo cuando se haya creado el registro.
- Si Paperclip no fue seleccionado, omitir este paso y anotarlo en la bitácora.

### 4. Generar integrations/hermes/

`integrations/hermes/config.yaml` — configuración canónica del gateway Hermes:
- Nombre del proyecto
- Ruta del workspace elegido, solo si se aprovisiona uno
- MCP servers requeridos
- Skills propias del proyecto

`integrations/hermes/env.template` — solo nombres de variables (valores → gestor de secretos aprobado; AKV `giorgio` cuando corresponda):
- Cada variable con comentario descriptivo
- Nombres que coinciden con `externalsecret.yaml` `remoteRef.key` cuando se use ExternalSecret
- Nunca valores reales

`integrations/hermes/skills/` — skills propias del proyecto (si las tiene).

### 5. Generar integrations/paperclip/ (si aplica)

Si Paperclip fue seleccionado, configurar:
- Adaptadores y contextos
- Skills que Paperclip puede delegar a agentes
- MCP servers accesibles desde el workspace

### 6. Generar config/paperclip-context.md (si aplica)

Si Paperclip fue seleccionado, documentar el contexto que inyecta a los agentes:
- Stack y arquitectura
- Convenciones del proyecto
- Comandos útiles
- Variables de entorno requeridas (nombres, no valores)

### 7. Generar scripts/setup.sh cuando el destino lo requiera

Crear `setup.sh` solo si aporta un bootstrap o recuperación repetible. Para un servicio
vm-services/systemd, documentar checkout, configuración secreta aprobada, restore de datos
si aplica, activación y health check. Para K3s, limitarlo al entorno de desarrollo: Flux
gestiona workloads y ExternalSecret/AKV gestiona secretos. Para un repo sin runtime propio,
no generar un script de recuperación artificial. Nunca incluir valores secretos.

### 8. Gate F5

Jev Noul: ≥ 0.7.

## Jev Integration Points

| Punto | Primitivo | Pregunta |
|---|---|---|
| Cobertura de agentes | noul | "Does the agent harness cover context, skills, tools, and MCP servers?" |
| Setup/restore path | noul | "Does the setup procedure cover the selected target without bypassing GitOps or exposing secrets?" |
| Gate F5 | noul | Threshold ≥ 0.7. Evalúa completitud del harness y restore path. |

## Pitfalls

- **Integra solo los sistemas seleccionados**: Paperclip y el restore path de vm-services son condicionales; no los declares listos si no fueron implementados.
- **env.template sin valores reales**: solo nombres de variables; los valores van al gestor de secretos aprobado para el destino.
- **Paperclip Company condicional**: solo pedir Company y registrar proyecto cuando Paperclip forme parte del alcance.
- **opencode.json debe ser válido**: si se genera, validar con `jq empty opencode.json` antes del PR.
- **setup.sh debe ser ejecutable**: si se genera, validar permisos y probarlo en un checkout limpio.
- **Restore path según destino**: exigir backup/systemd solo para servicios que realmente usan ese runtime; K3s se recupera por GitOps.
- **No duplicar AGENTS.md base**: extender, no reescribir, las convenciones de `reevolutiva-infra`.

## Verification

1. `AGENTS.md` existe con stack, separación código/GitOps, convenciones, flujo de trabajo y recuperación aplicable.
2. Si OpenCode fue seleccionado, `config/opencode.json` existe y es JSON válido.
3. Si Paperclip fue seleccionado, `paperclip project list --company <company>` muestra el proyecto; si no, la omisión queda documentada.
4. `integrations/hermes/config.yaml` existe.
5. `integrations/hermes/env.template` tiene solo nombres de variables (no valores).
6. Si Paperclip fue seleccionado, `integrations/paperclip/` y `config/paperclip-context.md` existen.
7. `scripts/setup.sh` existe solo si aplica, es ejecutable y sus pasos corresponden al destino.
8. Gate F5 ≥ 0.7.
9. `skills_list` muestra `ree-repo-harness` en categoría `productivity`.