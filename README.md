# Skills de Reevolutiva

Skills de documentación y diseño de producto para el pipeline `/ree-producto`.

## Estructura

```
productivity/
└── ree-producto/       # Orquestadora de 8 fases para documentación de producto
    ├── SKILL.md
    ├── references/
    │   ├── intake-schema.md       # Modelo de datos de intake
    │   ├── gate-definitions.md    # Gates Jev de validación
    │   └── phase-catalog.md       # Catálogo completo de fases
    └── templates/
        └── session-log.md         # Bitácora de sesión
```

## Instalación

```bash
# Como external dir (máquina local)
echo 'skills:\n  external_dirs:\n    - ~/proyectos/reevolutiva-skills' >> ~/.hermes/config.yaml

# Como GitHub Tap (compartido con el equipo)
hermes skills tap add reevolutiva/hermes-skills
hermes skills install reevolutiva/skills/ree-producto
```

## Reglas

- La skill principal tiene una description de ≤60 caracteres (límite de Hermes)
- Los archivos de referencia usan el formato progressive disclosure
- Cada skill debe incluir When to Use, Procedure, Pitfalls y Verification