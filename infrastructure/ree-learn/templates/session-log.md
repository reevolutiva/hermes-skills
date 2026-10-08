# Session Log Template — /ree-learn

Bitácora de sesión para ambos modos.
Se escribe en `<output_base_dir>/.ree-learn-session-<timestamp>.md`.

---

# Sesión ree-learn — <timestamp>

## Modo: <error | aprender>

## Intake

| Campo | Valor |
|-------|-------|
| <campo> | <valor> |

---

## Fases ejecutadas

### Fase 1 — <nombre>

- **Acciones:** <resumen>
- **Gates:**

| Gate | Motor | Resultado | Confianza / Score |
|------|-------|-----------|--------------------|
| <gate> | jev / hermes | <resultado> | <valor> |

---

### Fase N — <nombre>

...

---

## Correcciones aplicadas (solo modo error)

| Capa | Herramienta | Antes | Después | Validación |
|------|------------|-------|---------|------------|
| skill | skill_manage patch | <path> | <path> | noul 0.92 |
| memory | memory add | — | <contenido> | verificado |
| config | approvals.deny staging | — | <patrón> | pendiente revisión |

---

## Skills creadas (solo modo aprender)

| Nombre | Categoría | Dependencias | Gate post-creación |
|--------|-----------|-------------|---------------------|
| <nombre> | <cat> | <lista> | noul 0.88 |

---

## Gate final

| Gate | Motor | Resultado | Confianza / Score |
|------|-------|-----------|--------------------|
| <gate> | jev / hermes | <resultado> | <valor> |

---

## Gaps pendientes

- <gap 1>
- <gap 2>

---

## Artefactos generados

| Archivo | Path | Tamaño |
|---------|------|--------|
| SKILL.md | <path> | <bytes> |
| references/gate-definitions.md | <path> | <bytes> |
| ... | ... | ... |