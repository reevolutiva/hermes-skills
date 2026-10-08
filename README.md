## Reglas

- La skill principal tiene una description de ≤60 caracteres (límite de Hermes)
- Los archivos de referencia usan el formato progressive disclosure
- Cada skill debe incluir When to Use, Procedure, Pitfalls y Verification
- Toda skill orquestada incluye sección `## Jev Integration Points`
- Usar `TYPESAFE_API_KEY` cuando esté disponible; fallback con razonamiento Hermes si no
- **Nunca push directo a `main`** — solo PR mergeados. El workflow `block-push-main.yml` rechaza cualquier push que no sea un merge de PR (commit message empieza con "Merge pull request" o contiene "(#N)" de squash merge).