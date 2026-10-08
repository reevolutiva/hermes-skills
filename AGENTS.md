# AGENTS.md — Hermes Skills Repository

## Objetivo

Desarrollar y mantener el sistema de skills corporativas de Reevolutiva como tap
público/compartido en `reevolutiva/hermes-skills`.

## Estructura del repositorio

```
productivity/          # Skills de productividad y diseño
infrastructure/        # Skills de infraestructura, DevOps y aprendizaje
infrastructure/README.md
scripts/               # Scripts de instalación y actualización
  setup.sh             # Instalación completa del tap + skills
  update.sh            # Pull + recarga de skills
  install-vm-services.sh  # Instalación en vm-services
.github/
  workflows/
    block-push-main.yml  # Rechaza push directo a main
skills.sh.json         # Catálogo para Skills Hub
AGENTS.md              # Este archivo
```

## Flujo de trabajo

1. **Desarrollar localmente** con `skill_manage` (create/patch/write_file)
2. **Verificar con validation gates:**
   - `description` ≤ 60 caracteres
   - `name` en lowercase con guiones
   - `author: Hermes`
   - Sin secretos ni credenciales
3. **Commit en rama** `feat/<skill-name>` o `fix/<skill-name>`
4. **Abrir PR** contra `main`
5. **Merge → tap se actualiza automáticamente** al hacer `hermes skills reload`

## Reglas de desarrollo

- **Nunca push directo a main** — bloqueado por branch protection + workflow `block-push-main.yml`
- **Una skill = una responsabilidad** — si hace dos cosas no relacionadas, dividirla
- **Description ≤ 60 caracteres** — regla de Hermes, no negociable
- **Toda skill orquestada incluye `## Jev Integration Points`**
- **Referencias en `references/`**, templates en `templates/` — no mezclar
- **Skills existentes se referencian en `metadata.hermes.related_skills`**, no se duplican
- **Usar `TYPESAFE_API_KEY`** cuando esté disponible; fallback `[hermes-judgment]` si no

## Instalación (para usuarios)

```bash
# Agregar tap
hermes skills tap add reevolutiva/hermes-skills

# Instalar skills individuales
hermes skills install reevolutiva/skills/<skill-name>

# Actualizar todas
hermes skills reload
```

## Instalación en vm-services

```bash
ssh giolapietra@vm-services
bash /data/workspace/projects/reevolutiva-skills/scripts/install-vm-services.sh
```

## Comandos comunes

```bash
# Desarrollar localmente
cd ~/proyectos/reevolutiva-skills
git checkout -b feat/<skill-name>

# Validar antes de commit
grep "^description:" <categoria>/<skill>/SKILL.md | head -1
echo "<description>" | wc -c  # debe ser ≤ 60

# Sincronizar con upstream
git checkout main && git pull origin main

# Recargar skills en Hermes
hermes skills reload
```