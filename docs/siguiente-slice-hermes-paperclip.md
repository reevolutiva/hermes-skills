# Siguiente slice: método Hermes → Paperclip

## Objetivo (Goals)

Diseñar, aprobar e implementar un flujo repetible donde Hermes recibe y clarifica la solicitud, Paperclip coordina su ejecución delegada, y Hermes verifica resultados y captura aprendizajes reutilizables. El slice termina con un piloto end-to-end y un método documentado/versionado; no incluye por defecto cambios en producción, despliegue de Paperclip ni migración masiva de todas las skills divergentes.

## Alcance y entregables

1. Contrato metodológico con roles, estados, artefactos y puntos de aprobación humana.
2. Mapa de integración actual Hermes↔Paperclip, basado en el entorno real y con identificadores/URLs sin credenciales.
3. Decisión de destino del método: skill del tap, skill local o ambas con límites claros.
4. Propuesta de adjudicación de las 3 skills divergentes y los 7 archivos nuevos indicados en `rescate/2026-10-15/MANIFEST.md`.
5. Un piloto no destructivo y trazable que recorra intake, tarea Paperclip, ejecución controlada, revisión independiente y cierre.
6. PR de implementación en rama, con tests/documentación y evidencia de piloto.

## Pasos (Steps)

### S0 — Revalidar contexto y permisos

- Confirmar rama limpia, `origin/main` actualizado y CI vigente.
- Revisar issues #9 y #10 sobre webhook de CI y determinar si son parte del slice o dependencia separada.
- Verificar el estado actual (no histórico) de Paperclip, Hermes gateway y agentes asignables.
- Aclarar acceso a Paperclip/API/CLI y la autorización del usuario para crear tareas de prueba.

**Salida:** brief, SSOT, actores, repositorios, entornos y permisos disponibles; incertidumbres marcadas.

### S1 — Diseñar el contrato Hermes intake

Especificar campos obligatorios: objetivo/outcome, contexto, SSOT, alcance y non-goals, solicitante, riesgos, permisos, repositorio/rama/workspace, entregables, acceptance criteria observables, pruebas anti-regresión, datos sensibles prohibidos, política de rollback, responsable y política de revisión.

Añadir regla para preguntar solo por ambigüedades bloqueantes y requerir confirmación humana antes de acciones irreversibles o de producción.

**Salida:** esquema de intake y ejemplos de solicitudes listas / bloqueadas.

### S2 — Diseñar handoff y ciclo de vida Paperclip

- Mapear intake a Company/proyecto/agente/issue correcto.
- Definir cuándo usar una tarea única vs. fan-out con dependencias explícitas.
- Copiar brief aprobado y contexto mínimo suficiente al crear la tarea (sin arrastrar secretos).
- Definir estados de salida (in_review/done/blocked u opciones válidas en la instalación real) y dueño de siguiente acción.
- Preservar issue/run ID, enlaces, artefactos y commits como trazabilidad.

**Salida:** contrato de handoff, mapa de estados reales y esquema de responsabilidad (RACI ligero).

### S3 — Definir ejecución segura y review independiente

- Una rama/worktree y dueño por entregable; no compartir checkout entre agentes.
- Implementador registra commit, pruebas ejecutadas y limitaciones.
- Reviewer comprueba criterios originales, inspecciona artefactos y ejecuta pruebas relevantes.
- Definir `request_changes` para fallos corregibles y `blocked` solo para decisión humana/externa.
- Rechazar claims sin evidencia observable.

**Salida:** checklist de ejecución/review y ejemplos de handoff bueno/malo.

### S4 — Resolver consolidación de las skills

- Comparar las versiones del tap, imac27 y vm-services línea por línea/sección por sección.
- Adjudicar cada pieza como aceptar, reescribir, renombrar, mantener project-local o descartar (con razón).
- No combinar automáticamente las 3 skills con divergencia ni borrar versiones originales.
- Actualizar `rescate/2026-10-15/MANIFEST.md` con estado por archivo (pendiente/propuesto/aplicado/verificado).

**Salida:** matriz de adjudicación revisable antes de editar skills canónicas.

### S5 — Implementar skill/documentación en rama + PR

- Implementar el método aprobado en skill separada o extensión justificada de `ree-intake`/`ree-learn`.
- Actualizar `README.md`, `AGENTS.md`, `skills.sh.json`, referencias y tests de catálogo en el mismo PR si cambia inventario.
- Incluir enlaces a issue(s) Paperclip y evidencias; nunca incluir dumps de sesión ni secretos.
- Abrir PR a `main`, esperar checks y review, incorporar cambios solicitados.

**Salida:** PR verde, diff revisado y listo para merge; no hacer merge sin gate/permiso requerido.

### S6 — Piloto end-to-end y transferencia

- Ejecutar en Paperclip un caso reversible/no productivo aprobado por el usuario.
- Verificar intake → handoff → issue asignado → ejecución → review → disposición final → retorno a Hermes.
- Comprobar trazabilidad desde la petición hasta commit/evidencia y que cierre no ocurre sin aceptación.
- Documentar resultado, excepciones, rollback y mejoras; si el piloto modifica hosts, pedir permiso explícito para actualización de skill y verificar runtime.

**Salida:** informe del piloto y checklist de aceptación cumplida/no cumplida.

## Validaciones (Validation gates)

### V0 — Baseline

- `git status` limpio antes de iniciar y `origin/main` actualizado.
- Issues/PRs existentes inspeccionados; no duplicar el trabajo de #9/#10.
- Estado Paperclip/gateway basado en una consulta actual, no solo en memoria histórica.

### V1 — Seguridad

- Cero tokens/keys/passwords/Bearer/private keys en código, docs, logs o comentarios públicos.
- No incluir dumps de sesión, `MEMORY.md`, `USER.md`, inventarios con rutas sensibles ni material profile-only sin saneamiento y autorización.
- Todas las acciones externas enumeradas; gates humanos antes de despliegue, publicación o datos de producción.

### V2 — Calidad metodológica

- Cada paso tiene owner, input, output y criterio observable.
- Contrato evita handoffs ambiguos y declara estados terminales/no terminales.
- Revisión separada de implementación; fallos corregibles retornan a cambios.

### V3 — Repo y CI

- Ejecutar `python3 scripts/validate-skills-catalog.py`.
- Validar frontmatter (`name`, `description` ≤60 chars, `author: Hermes`), referencias existentes y sección `## Jev Integration Points` donde aplique.
- Ejecutar workflows/checks CI requeridos; PR apunta a `main` desde rama no protegida.
- El diff incluye solo alcance aprobado y no modifica hosts.

### V4 — Aceptación del piloto

- Un intake de prueba produce un contrato aprobable.
- Paperclip conserva issue/run ID, assignee, estados y artefactos enlazados.
- La ejecución satisface todos los acceptance criteria o deja el issue bloqueado/request-changes con razón accionable.
- Hermes comunica el resultado usando evidencia, no solo el resumen del implementador.
- No queda tarea huérfana ni se marca `done` sin verificación.

### V5 — Transferencia

- Skill/doc aprobada y mergeada en PR.
- Instalación/update solo después del merge y con autorización; no instalar durante la fase de investigación.
- Runtime objetivo confirma que la skill cargada coincide con el commit del tap.
- Issue Paperclip y documentación registran cierre, artefactos y decisiones pendientes.

## Fuera de alcance salvo aprobación

- Merge directo a `main`, despliegue a producción, actualización/instalación en hosts, cambios de configuración o credenciales.
- Activar automáticamente curator/consolidación en hosts.
- Migrar o fusionar las 97 skills aprendidas de imac27.
- Exponer Paperclip/Hermes públicamente o cambiar la topología de red.

## Prompt operativo listo para Paperclip

**Goal:** Diseñar, validar e implementar de manera segura el método Reevolutiva Hermes intake → Paperclip ejecución → verificación independiente → transferencia de aprendizaje, y entregar un piloto trazable más un PR listo para review.

**Steps:** S0 revalidar entorno/issues/permiso; S1 diseñar intake; S2 mapear handoff/estados Paperclip reales; S3 especificar ejecución y review independiente; S4 producir matriz de adjudicación de divergencias; S5 implementar exclusivamente lo aprobado en rama + PR; S6 ejecutar piloto reversible solo con autorización explícita.

**Validations:** V0 baseline y no duplicación #9/#10; V1 cero secretos y sin dumps; V2 contrato con owner/inputs/outputs/criterios; V3 catalog validator + CI verde + PR a main; V4 evidencia de extremo a extremo sin cierre prematuro; V5 transferencia post-merge autorizada y verificada. Bloquear y pedir decisión ante permiso ausente, API inaccesible, fuentes no verificables o ambigüedad que cambie alcance/riesgo. Nunca push directo a main ni instalar/update skills remotas sin autorización.

**Entrega al coordinador:** Issue/run ID, rama, commits, PR URL, tests/checks con resultados reales, matriz de divergencias, evidencia del piloto, bloqueos/decisiones y estado Paperclip final.