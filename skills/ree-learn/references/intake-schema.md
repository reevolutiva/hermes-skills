# Intake Schema — /ree-learn

Modelo de datos de entrada para ambos modos de `ree-learn`.
Define los campos mínimos y opcionales que el agente recolecta antes de ejecutar.

---

## Modo Error

### Campos obligatorios

| Campo | Tipo | Descripción | Ejemplo |
|-------|------|-------------|---------|
| `error.description` | string | Qué error cometió el agente | "Aplicó kubectl apply en vez de abrir un PR para Flux" |
| `error.context` | string | Mensaje exacto o transcripción donde ocurrió | "El agente ejecutó: kubectl apply -f infrastructure/..." |
| `error.policy_violated` | string | Qué regla, skill o política se violó | "Regla GitOps: nunca aplicar manifiestos a mano" |

### Campos opcionales

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `error.session_id` | string | ID de sesión donde ocurrió (para búsqueda con session_search) |
| `error.consequence` | string | Impacto del error (producción, datos, ninguno) |
| `error.reproduction` | string | Cómo reproducir el error (comando o secuencia) |
| `error.correction_hint` | string | Si el usuario ya indicó cómo corregirlo |

---

## Modo Aprender

### Campos obligatorios

| Campo | Tipo | Descripción | Ejemplo |
|-------|------|-------------|---------|
| `skill.domain` | string | Dominio o área de la skill a construir | "infraestructura", "productividad", "research" |
| `skill.purpose` | string | Qué debe hacer la skill (una oración) | "Orquestar la migración de cargas entre nodos K3s" |
| `skill.category` | string | Categoría propuesta (nueva o existente) | "infrastructure" |
| `skill.output_base_dir` | string | Directorio base donde guardar artefactos | `/data/workspace/projects/reevolutiva-infra/.worktrees/...` |

### Campos opcionales

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `skill.related_skills` | list | Skills existentes que deberían referenciarse |
| `skill.constraints` | list | Restricciones (arquitectura, plataforma, seguridad) |
| `skill.examples` | list | Ejemplos de uso esperado |
| `skill.sources` | list | URLs, documentos o repos de referencia vinculantes |
| `skill.skip_phases` | list | Fases a saltar (ej: solo Investigar + Diseñar) |

---

## Salida (ambos modos)

La bitácora de sesión (`session-log.md`) registra:
- Campos del intake recolectados.
- Gates ejecutados con motor y resultado.
- Acciones correctivas aplicadas (modo error) o skills creadas (modo aprender).
- Gaps pendientes si los hay.