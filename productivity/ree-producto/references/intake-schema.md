# Intake Schema — /ree-producto

Estructura de datos que el agente recolecta del usuario antes de ejecutar cualquier fase.
El intake se recolecta interactivamente y se almacena en contexto durante toda la sesión.

```yaml
product:
  name: string                    # REQUERIDO — Nombre del producto/proyecto
  tagline: string?                # One-liner opcional
  domain: string                  # REQUERIDO — Industria (fintech, healthtech, legaltech...)
  stage: enum                     # idea | discovery | mvp | growth | scale
  target_geography: string        # País/región principal del mercado
  target_language: string         # Idioma principal de los entregables

problem:
  statement: string               # REQUERIDO — Descripción del problema que resuelve
  evidence: string?               # Datos o señales que validan el problema
  current_alternatives: string[]  # Cómo lo resuelven hoy los usuarios

solution:
  summary: string                 # REQUERIDO — Descripción breve de la solución
  unique_value: string?           # Qué lo diferencia de alternativas
  platform: string[]              # web | mobile | api | desktop | cli
  tech_stack_hint: string?        # Stack tecnológico si ya está definido

sources:
  folders: string[]               # Rutas a carpetas que el agente debe inspeccionar
  documents: string[]             # Archivos concretos que debe leer (md, pdf, xlsx, docx...)
  urls: string[]                  # Enlaces web que deben ser consultados
  notes: string[]                 # Cualquier referencia adicional (tickets, notas, specs)

users:
  primary_segments: string[]      # REQUERIDO — Segmentos principales de usuarios
  known_personas: string[]?       # Personas ya identificadas
  user_count_estimate: string?    # "0 (pre-lanzamiento)", "1000 MAU", etc.

business:
  model: string?                  # B2B | B2C | B2B2C | marketplace
  revenue_model: string?          # SaaS, transaccional, ads, etc.
  key_metrics: string[]?          # Métricas que importan (conversión, retención...)

phases:
  enabled: string[]               # Fases a ejecutar (1-8). Vacío = todas
  skipped: string[]               # Fases a omitir explícitamente
  priority_phase: integer?        # Fase de inicio (default: 1)

output:
  base_dir: string                # REQUERIDO — Directorio para entregables
  format: enum                    # markdown | notion | google-docs
  language: string                # Idioma de entregables (default: español)
  artifact_prefix: string?        # Prefijo para archivos (default: nombre del producto)
```

## Reglas de validación

1. Campos REQUERIDOS: `product.name`, `product.domain`, `problem.statement`,
   `solution.summary`, `users.primary_segments`, `output.base_dir`.
2. Si falta algún campo requerido, la skill no avanza hasta completarlo.
3. Campos con `?` son opcionales; si no se proporcionan se marcan `TBD`.
4. `sources` es opcional pero **vinculante**: si el usuario lo proporciona,
   el agente DEBE inspeccionar todo su contenido en las fases relevantes.
5. Si `phases.enabled` y `phases.skipped` están vacíos → todas las fases.
6. `fol