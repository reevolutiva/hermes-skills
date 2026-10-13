# AGENTS.md — Hermes Skills Repository

## Objetivo

Desarrollar y mantener el sistema de skills corporativas de Reevolutiva como tap
público/compartido en `reevolutiva/hermes-skills`.

## Estructura del repositorio

```
skills/                              # Convención del tap: skills/<name>/SKILL.md
├── ree-learn/                       # Aprendizaje: error, aprender, actualizar
├── ree-producto/                    # Documentación de producto en 8 fases
├── ree-repo/                        # Orquestador de habilitación F1-F6
├── ree-repo-architect/              # Diagramas C4 + ADRs
├── ree-repo-deploy/                 # Manifiestos GitOps + registro Flux
├── ree-repo-harness/                # AGENTS.md, integrations y setup
├── ree-repo-scaffold/               # Repo de código, entorno y CI
├── ree-repo-validate/               # Validación de documentos fuente
├── ree-repo-verify/                 # Coherencia y Definition of Done
├── reevolutiva-infra-gitops/        # GitOps: Flux + K3s + AKV
├── wordpress-bedrock-migration/     # Migración WP Bedrock → K3s
└── wordpress-performance-diagnosis/ # Diagnóstico de WP en K8s
scripts/
  setup.sh
  update.sh
  install-vm-services.sh
  validate-skills-catalog.py
.github/workflows/
  block-push-main.yml
  validate-skills.yml
docs/
  arquitectura-repositorios.md
  infrastructure-README.md
skills.sh.json                       # Catálogo para Skills Hub
AGENTS.md                            # Este archivo
README.md                            # Documentación general
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
5. **Merge → `hermes skills update`** para reflejar cambios

## Reglas de desarrollo

- **Nunca push directo a main** — bloqueado por branch protection + workflow `block-push-main.yml`
- **Una skill = una responsabilidad** — si hace dos cosas no relacionadas, dividirla
- **Description ≤ 60 caracteres** — regla de Hermes, no negociable
- **Toda skill orquestada incluye `## Jev Integration Points`**
- **Referencias en `references/`**, templates en `templates/` — no mezclar
- **Skills existentes se referencian en `metadata.hermes.related_skills`**, no se duplican
- **Inventario atómico** — toda skill debe aparecer en AGENTS.md, README.md y skills.sh.json en el mismo PR; validar con `python3 scripts/validate-skills-catalog.py`
- **Usar `TYPESAFE_API_KEY`** cuando esté disponible; fallback `[hermes-judgment]` si no

## Instalación (para usuarios)

```bash
# Agregar tap
hermes skills tap add reevolutiva/hermes-skills

# Instalar skills individuales
hermes skills install reevolutiva/hermes-skills/skills/<skill-name>

# Actualizar todas
hermes skills update
```

## Instalación en vm-services

```bash
ssh giolapietra@vm-services
bash /home/giolapietra/reevolutiva-skills/scripts/install-vm-services.sh
```

## Comandos comunes

```bash
# Desarrollar localmente
cd ~/proyectos/reevolutiva-skills
git checkout -b feat/<skill-name>

# Validar antes de commit
grep "^description:" skills/<skill>/SKILL.md | head -1
echo "<description>" | wc -c  # debe ser ≤ 60

# Sincronizar con upstream
git checkout main && git pull origin main

# Actualizar skills en Hermes
hermes skills update
```