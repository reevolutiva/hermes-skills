# Skills de Reevolutiva

Skills de infraestructura, aprendizaje, alineamiento y documentación de producto para Hermes Agent.

## Estructura

```
productivity/
└── ree-producto/              # Orquestadora de 8 fases para documentación de producto
    ├── SKILL.md
    ├── references/
    │   ├── intake-schema.md
    │   ├── gate-definitions.md
    │   └── phase-catalog.md
    └── templates/
        └── session-log.md

infrastructure/
└── ree-learn/                 # Orquestador de aprendizaje y alineamiento (error + aprender)
    ├── SKILL.md
    ├── references/
    │   ├── gate-definitions.md
    │   └── intake-schema.md
    └── templates/
        └── session-log.md
```

## Skills disponibles

### `/ree-producto` — Documentación de Producto
Flujo en 8 etapas para documentar productos desde cero con intake interactivo y gates Jev de validación entre fases.

### `/ree-learn` — Aprendizaje y Alineamiento
Dos modos:
- **`ree-learn error`** — diagnostica y corrige la fuente raíz de un error usando herramientas nativas Hermes (memory, skill_manage, approvals.deny, /refine) con Jev como validador.
- **`ree-learn aprender`** — construye una nueva skill orquestada con la metodología de 4 fases (Investigar → Diseñar → Implementar → Revisar) y gates Jev.

## Instalación

```bash
# Como external dir (máquina local)
echo 'skills:\n  external_dirs:\n    - ~/proyectos/reevolutiva-skills' >> ~/.hermes/config.yaml

# Como GitHub Tap (compartido con el equipo)
hermes skills tap add reevolutiva/hermes-skills
hermes skills install reevolutiva/skills/ree-producto
hermes skills install reevolutiva/skills/ree-learn
```

## Reglas

- La skill principal tiene una description de ≤60 caracteres (límite de Hermes)
- Los archivos de referencia usan el formato progressive disclosure
- Cada skill debe incluir When to Use, Procedure, Pitfalls y Verification
- Toda skill orquestada incluye sección `## Jev Integration Points`
- Usar `TYPESAFE_API_KEY` cuando esté disponible; fallback con razonamiento Hermes si no