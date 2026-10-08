# Infrastructure — Reevolutiva Skills

Skills de infraestructura, aprendizaje y alineamiento para la plataforma Reevolutiva.

## Diagrama de flujo

```
ree-learn (orquestadora de aprendizaje)
├── Modo: error
│   ├── 1. Capturar error
│   ├── 2. Diagnosticar fuente (Jev choice)
│   ├── 3. Corregir (memory | skill_manage | approvals.deny)
│   ├── 4. Validar (Jev noul)
│   └── 5. Registrar (session-log.md)
│
└── Modo: aprender
    ├── 1. Investigar (skills_list + Skills Hub + Jev classification)
    ├── 2. Diseñar (Design Spec + Jev score gate)
    ├── 3. Implementar (skill_manage create + Jev noul por skill)
    └── 4. Revisar (Jev score gate final + command validation)
```

## Skills

| Skill | Rol | Dependencias |
|-------|-----|-------------|
| `ree-learn` | Orquestadora de aprendizaje y alineamiento (error + aprender) | `ree-aprender` (absorbida), `typesafe-ai`, `ree-kanban-ops` |

## Herramientas Hermes nativas orquestadas

| Herramienta | Capa | Uso en ree-learn |
|-------------|------|-----------------|
| `skill_manage` | Procedural | Crear/patch skills para corregir o construir |
| `memory` | Memoria | Añadir/reemplazar/eliminar entradas en MEMORY.md y USER.md |
| `approvals.deny` | Política | Bloquear comandos peligrosos (kubectl apply, etc.) |
| `skill_view` | Lectura | Cargar skills existentes para diagnosticar |
| `session_search` | Historial | Buscar sesiones pasadas con errores |
| `/refine` | Self-improvement | Forzar background review con foco en alineamiento |
| `kanban_comment` | Trazabilidad | Registrar correcciones en la carta activa |

## Jev Integration Points

Todos los gates usan Jev (TypeSafe) como motor de decisión estructurada:
- **Choice**: clasificar fuente raíz, clasificar skills, evaluar completitud.
- **Noul**: validar corrección, detectar gaps, verificar coherencia, revisar description.
- **Score**: evaluar calidad de diseño, coherencia final del sistema.

Modo fallback sin `TYPESAFE_API_KEY`: razonamiento Hermes con nivel de confianza explícito.

## Entregables

| Archivo | Descripción |
|---------|-------------|
| `SKILL.md` | Skill principal con procedimiento, pitfalls y verification |
| `references/gate-definitions.md` | Payloads Jev exactos para cada gate |
| `references/intake-schema.md` | Modelo de datos de entrada para ambos modos |
| `templates/session-log.md` | Plantilla de bitácora de sesión |

## Instalación

```bash
# Desde el repo local
mkdir -p ~/.hermes/skills/infrastructure/
cp -r infrastructure/ree-learn ~/.hermes/skills/infrastructure/

# Desde GitHub Tap
hermes skills tap add reevolutiva/hermes-skills
hermes skills install reevolutiva/hermes-skills/skills/ree-learn
```

## Uso

```bash
# Corregir un error — el agente diagnosticará la fuente y aplicará la corrección
/ree-learn error

# Construir una nueva skill orquestada
/ree-learn aprender
```