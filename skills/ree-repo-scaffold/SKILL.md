---
name: ree-repo-scaffold
category: productivity
version: 1.1.0
description: "Prepara repos de proyecto con desarrollo reproducible y CI."
author: Hermes
license: MIT
metadata:
  hermes:
    tags: [ree-repo, scaffold, github, cicd, development]
---

# ree-repo-scaffold — repositorio de código y flujo de desarrollo

## When to Use

Cuando un proyecto necesita un repositorio de código nuevo o una base reproducible para que personas y agentes desarrollen, prueben y publiquen artefactos.

## Límite de responsabilidad

Este skill prepara el repositorio del proyecto: código, setup, tests, CI y, si aplica, Dockerfile/build de imagen. Los manifiestos que Flux aplica **no** viven aquí: van en `reevolutiva-infra/apps/<proyecto>/`; el registro y placement van en `reevolutiva-infra/clusters/<activo>/apps.yaml` mediante `ree-repo-deploy`. Mantén ese límite incluso si un scaffold antiguo incluye una carpeta `apps/` con YAML de Kubernetes.

## Procedure

### 1. Descubrir el proyecto y los requisitos

Leer el intake, la arquitectura acordada y las convenciones de la organización. Determinar lenguaje, toolchain, comandos de test/lint, si requiere una imagen, y qué secretos consume. No generar un monorepo de carpetas genéricas si el proyecto no las necesita.

Comprobar `gh auth status` antes de usar GitHub. Si el repo ya existe, inspeccionar su estructura y estado antes de modificarlo.

### 2. Crear la base de desarrollo

Crear o completar el repositorio bajo la organización indicada. Incluir solo lo que aplique:

- código fuente y pruebas;
- `README.md` y `AGENTS.md` con setup, convenciones, pruebas y flujo de PR;
- `.github/workflows/` con CI de lint/test/typecheck adecuado al stack;
- configuración reproducible (`.devcontainer/`, `Dockerfile` de desarrollo o equivalente si corresponde);
- scripts de desarrollo, build y migración cuando sean necesarios;
- `.env.example` con nombres/comentarios solamente, nunca valores;
- `Dockerfile` de runtime cuando el servicio se despliegue como contenedor.

No fuerces `package.json`, Node, Docker Compose ni estructura de agentes a proyectos de otro stack. No incluir manifiestos Kubernetes ni secretos de producción en el repo de aplicación.

### 3. Definir CI y artefactos

La CI debe ejecutar los checks reales del proyecto en push de rama y PR a `main`. Si el proyecto genera una imagen, construirla desde una revisión identificable y publicarla en el registry que autorice el flujo GitOps vigente. Fijar tags versionados/digest para despliegues; no promover `latest` como referencia estable. Verificar multi-arch si el servicio puede correr tanto en arm64 como amd64 y probar pull desde el nodo destino antes de dar por listo el landing.

No hardcodear GHCR ni el registry interno sin revisar las instrucciones operativas actuales: la plataforma prioriza el registry interno, pero capacidad de pull y credenciales deben comprobarse por clase/nodo.

### 4. Configurar ramas e integración

Usar el flujo de ramas y PR definido por la organización. Configurar protección de `main` y controles anti-push directo si forman parte del estándar vigente, antes de depender de ellos. Crear el commit inicial y abrir PR cuando la política del repo así lo requiere; no eludir las protecciones para ahorrar pasos.

### 5. Habilitar el workspace de desarrollo

Si el alcance incluye vm-services o Paperclip, clonar el proyecto en un checkout propio bajo `/data/workspace/projects/<repo>` y verificar el setup desde un entorno limpio. Si Paperclip se usará, registrar el repo/workspace y dejar que gestione worktrees por issue. Si el proyecto se desarrollará en otro entorno, documentar allí los pasos de checkout y setup; no aprovisionar vm-services por defecto. Nunca compartir un `.git` escribible entre agentes o entre agente y desarrollador; usar clones/worktrees aislados e integrar por PR.

### 6. Entregar a GitOps

Cuando el código y la imagen estén listos, pasar a `ree-repo-deploy` para crear los recursos de plataforma y registrar la Kustomization en `reevolutiva-infra`. Coordinar las revisiones: el manifiesto GitOps debe apuntar a una imagen que ya existe y que el nodo destino puede descargar. El alta en Paperclip es independiente del despliegue Flux.

## Jev Integration Points

| Punto | Primitivo | Pregunta / niveles |
|---|---|---|
| Setup reproducible | `noul` | ¿Un checkout limpio instala dependencias y ejecuta los comandos documentados? |
| CI | `noul` | ¿La CI ejecuta los checks reales del stack y pasa en PR? |
| Gate F3 | `score` | `incompleto`, `minimo`, `completo`, `sobreconstruido` |

State: stack elegido, comandos de setup/test y resultados de CI/imagen. Sin TYPESAFE_API_KEY, usar `[hermes-judgment]` y registrar confianza.

## Pitfalls

- **No pongas YAML de despliegue K3s dentro del repo de código como fuente de verdad:** Flux sincroniza el repo central `reevolutiva-infra`, no un directorio local ni automáticamente el repo de aplicación.
- **No supongas un stack común:** adaptar estructura y CI al manifiesto real evita scaffolds pesados que no se pueden ejecutar.
- **No hornees secretos en `.env.example`, imagen ni workflow:** variables de entorno nombran configuración, pero valores de runtime van al mecanismo aprobado de secretos.
- **No uses tags mutables como pin de producción:** un tag mutable impide determinar qué versión está ejecutándose y debilita rollback.
- **No asumas que la imagen funciona en cualquier nodo:** arm64/amd64 y acceso al registry se verifican en el destino efectivo.
- **Separa workspace y despliegue:** Paperclip o VS Code habilita desarrollo; solo el PR GitOps habilita Flux.

## Verification

- Un checkout limpio puede instalar dependencias y ejecutar los comandos documentados.
- CI corre los tests/lint/typecheck apropiados y pasa en PR.
- `.env.example` contiene nombres, no secretos.
- Si hay imagen, el tag/digest, arquitecturas y registry están documentados y el pull se probó desde el nodo destino.
- README/AGENTS explican cómo abrir workspace, testear, construir y pedir un despliegue.
- El despliegue se entrega a `ree-repo-deploy`; no se declara terminado por el solo hecho de que el repo exista.