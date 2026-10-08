# Skills de Reevolutiva

Skills de infraestructura, aprendizaje, alineamiento y documentación de producto para Hermes Agent.

## Estructura

```
productivity/
└── ree-producto/                     # Orquestadora de 8 fases para documentación de producto
    ├── SKILL.md
    ├── references/
    │   ├── intake-schema.md
    │   ├── gate-definitions.md
    │   └── phase-catalog.md
    └── templates/
        └── session-log.md

infrastructure/
├── reevolutiva-infra-gitops/         # Operación del repo GitOps (Flux + K3s + AKV)
│   ├── SKILL.md
│   └── references/
│       ├── backups-y-rtt.md
│       ├── cloudflare-tunnel.md
│       ├── ghcr-imagenes.md
│       ├── gotchas-verificados.md
│       ├── alertas-prometheus.md
│       ├── nodo-flatcar.md
│       ├── nodo-kit.md
│       └── tailscale-acl.md
├── wordpress-bedrock-migration/      # Migración WP Bedrock (single-site y multisite) a K3s
│   ├── SKILL.md
│   └── references/
│       ├── cloudflare-tunnel-cutover.md
│       ├── image-architecture-checks.md
│       ├── ghcr-registry.md
│       └── wp-bedrock-docroot-404-wp-admin.md
├── wordpress-performance-diagnosis/  # Diagnóstico de WP en K8s: lentitud, caídas, caché
│   ├── SKILL.md
│   └── references/
│       └── probe-recetas.md
└── ree-learn/                        # Orquestador de aprendizaje y alineamiento (error + aprender)
    ├── SKILL.md
    ├── references/
    │   ├── gate-definitions.md
    │   └── intake-schema.md
    └── templates/
        └── session-log.md
```

## Skills disponibles

### Infraestructura

#### `reevolutiva-infra-gitops`
Operación del repo GitOps de Reevolutiva: topología de clúster, secretos AKV, migración,
WordPress, backups, exposición Tailscale/Cloudflare, DNS, alertas, triage P1.
Regla de oro: todo cambio por Git → PR → merge → Flux.

#### `wordpress-bedrock-migration`
Migración completa de un WordPress Bedrock (single-site o multisite) a K3s: dump/restore,
corte de túnel Cloudflare, mixed-content, multi-arquitectura, capas de build.

#### `wordpress-performance-diagnosis`
Diagnóstico de WordPress en Kubernetes: lentitud, caídas, caché (page/object/edge), redirects,
OOMKilled, cron interno, DaemonSet/taint, almacenamiento.

#### `ree-learn`
Dos modos:
- **error** — diagnostica y corrige la fuente raíz de un error usando herramientas nativas Hermes
- **aprender** — construye una nueva skill orquestada con 4 fases y gates Jev

### Producto

#### `ree-producto`
Flujo en 8 etapas para documentar productos desde cero con intake interactivo y gates Jev.

## Instalación

```bash
# Como GitHub Tap (compartido con el equipo)
hermes skills tap add reevolutiva/hermes-skills

# Instalar skills individuales
hermes skills install reevolutiva/skills/reevolutiva-infra-gitops
hermes skills install reevolutiva/skills/wordpress-bedrock-migration
hermes skills install reevolutiva/skills/wordpress-performance-diagnosis
hermes skills install reevolutiva/skills/ree-learn
hermes skills install reevolutiva/skills/ree-producto
```

## Reglas

- La skill principal tiene una description de ≤60 caracteres (límite de Hermes)
- Los archivos de referencia usan el formato progressive disclosure
- Cada skill debe incluir When to Use, Procedure, Pitfalls y Verification
- Toda skill orquestada incluye sección `## Jev Integration Points`
- Usar `TYPESAFE_API_KEY` cuando esté disponible; fallback con razonamiento Hermes si no