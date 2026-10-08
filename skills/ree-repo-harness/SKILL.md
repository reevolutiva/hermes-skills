---
name: ree-repo-harness
description: "Configura AGENTS.md, integrations y setup.sh"
version: 1.0.0
author: Hermes
license: MIT
category: productivity
tags: [ree-repo, harness, agents, paperclip, hermes, restore-path, mcp]
---

# ree-repo-harness — F5: Configuración de Agentes y Restore Path

Establece AGENTS.md, opencode.json, integrations/, MCP, scripts/setup.sh con restore path completo (git clone → AKV → backup → systemd), y registra el proyecto en Paperclip. Sin este harness, los agentes autónomos no pueden operar y no hay plan de recuperación tras destrucción de vm-services.

## When to Use

- Desde `/ree-repo` orquestadora (F5), después de F3 Scaffold y F4 Deploy.
- "configurar agentes", "preparar harness", "crear setup.sh", "registrar en Paperclip".
- Trigger: el proyecto necesita que los agentes AI puedan trabajar autónomamente.

## Procedure

### 1. Generar AGENTS.md

Incluir:
- Stack y arquitectura (desde Fase 6)
- Modelo de despliegue (GitOps, Flux, `apps/<proyecto>/`)
- Convenciones de código (naming, linting, testing)
- Comandos comunes (`npm run dev`, `npm test`, `make health`)
- Agentes disponibles y cómo invocarlos
- Flujo de trabajo (branch feat/ → PR → review → merge)
- Restore path y troubleshooting

### 2. Generar opencode.json

Crear `config/opencode.json`:
- Permisos granulares (lectura, edición, bash)
- MCP servers requeridos
- Skills cargadas
- Agentes definidos

### 3. Registrar proyecto en Paperclip

- Usar la Paperclip Company proporcionada en intake
- Crear el proyecto dentro de esa compañía apuntando al workspace `vm-services:/data/workspace/projects/<repo>`
- Verificar: `paperclip project list --company <company>` muestra el proyecto

### 4. Generar integrations/hermes/

`integrations/hermes/config.yaml` — configuración canónica del gateway Hermes:
- Nombre del proyecto
- Ruta del workspace en vm-services
- MCP servers requeridos
- Skills propias del proyecto

`integrations/hermes/env.template` — solo nombres de variables (valores → AKV `giorgio`):
- Cada variable con comentario descriptivo
- Nombres que coinciden con `externalsecret.yaml` `remoteRef.key`
- Nunca valores reales

`integrations/hermes/skills/` — skills propias del proyecto (si las tiene).

### 5. Generar integrations/paperclip/

Configuración de Paperclip:
- Adaptadores y contextos
- Skills que Paperclip puede delegar a agentes
- MCP servers accesibles desde el workspace

### 6. Generar config/paperclip-context.md

Contexto que Paperclip inyecta a los agentes al delegar tareas:
- Stack y arquitectura
- Convenciones del proyecto
- Comandos útiles
- Variables de entorno requeridas (nombres, no valores)

### 7. Generar scripts/setup.sh

Wizard bash que cubre el restore path completo:

```bash
#!/bin/bash
# Restore path: git clone → AKV secrets → backup restore → systemd enable

# Paso 1: git clone
# Paso 2: Leer env.template → pedir valores → guardar en AKV giorgio
# Paso 3: Restaurar desde backup (scripts/backup-agentes.sh de reevolutiva-infra)
# Paso 4: systemctl enable --now <service>
# Paso 5: make health
```

### 8. Gate F5

Jev Noul: ≥ 0.7.

## Jev Integration Points

| Punto | Primitivo | Pregunta |
|---|---|---|
| Cobertura de agentes | noul | "Does the agent harness cover context, skills, tools, and MCP servers?" |
| Restore path | noul | "Does setup.sh cover git clone → AKV → backup restore → systemd enable?" |
| Gate F5 | noul | Threshold ≥ 0.7. Evalúa completitud del harness y restore path. |

## Pitfalls

- **Integrations/ son parte del restore path**: si `integrations/` no está completo, `setup.sh` no puede restaurar el agente tras destrucción de vm-services.
- **env.template sin valores reales**: solo nombres de variables. Los valores van a AKV `giorgio`.
- **Paperclip Company requerida**: sin Company definida, no se puede registrar el proyecto. Preguntar al usuario.
- **opencode.json debe ser válido**: validar con `jq empty opencode.json` antes de commit.
- **setup.sh debe ser ejecutable**: `chmod +x scripts/setup.sh`.
- **Restore path completo**: si falta algún paso (clone, AKV, backup, systemd), el harness está incompleto.
- **No duplicar AGENTS.md base**: extender, no reescribir, las convenciones de `reevolutiva-infra`.

## Verification

1. `AGENTS.md` existe con stack, despliegue, convenciones, flujo de trabajo y restore path.
2. `config/opencode.json` existe y es JSON válido.
3. `paperclip project list --company <company>` muestra el proyecto.
4. `integrations/hermes/config.yaml` existe.
5. `integrations/hermes/env.template` tiene solo nombres de variables (no valores).
6. `integrations/paperclip/` contiene config de Paperclip.
7. `config/paperclip-context.md` existe.
8. `scripts/setup.sh` existe, es ejecutable, y cubre los 4 pasos del restore path.
9. Gate F5 ≥ 0.7.
10. `skills_list` muestra `ree-repo-harness` en categoría `productivity`.