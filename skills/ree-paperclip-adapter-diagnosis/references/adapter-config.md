# Configuración y diagnóstico de adapters Paperclip

Referencia técnica para `opencode_local` (OpenCode), proveedores compatibles con
OpenAI como LiteLLM, y la configuración general de `hermes_gateway`. La fuente de
verdad del comportamiento es el paquete instalado y su versión, no una ruta o
una recomendación histórica copiada sin comprobar.

## 1. Inspección inicial y versión

1. `paperclipai --version` identifica la CLI activa; `readlink -f
   ~/.paperclip/cli/current` (Linux) identifica el payload gestionado.
2. Inspeccionar solo el paquete de la versión activa:
   `~/.paperclip/cli/current/node_modules/@paperclipai/`.
3. En la versión verificada `2026.1012.0`, los paquetes incluyen
   `@paperclipai/adapter-opencode-local` y
   `@paperclipai/hermes-paperclip-adapter`; versiones posteriores requieren
   verificar otra vez los símbolos y comportamientos citados aquí.
4. Para configuración Paperclip: `paperclipai agent configuration <agentId>
   --json` devuelve config redactada; `agent config-revisions <agentId>` da el
   historial; `secrets usage <secretId>` lista referencias. No leer valores del
   secreto desde DB ni exponerlos en logs.

## 2. Ubicación de configuración OpenCode

| Pieza | Ubicación o fuente | Observación |
|---|---|---|
| Definición provider OpenCode | `~/.config/opencode/opencode.json`, key de nivel superior `provider` | Debe incluir el mapa `models`; un wrapper arbitrario como `{"LiteLLM": {...}}` se ignora. |
| Credencial upstream | `.env` consumido por OpenCode o entorno efectivo del run | Evitar pegar valores en configuración versionada o comandos visibles. |
| Provider inyectado por Paperclip | `PAPERCLIP_OPENCODE_PROVIDERS` en el entorno servidor Paperclip | JSON compatible con la clave `provider` de OpenCode. |
| Modelo por agente | `adapterConfig.model` | Identificador `provider/model`; confirmar qué paquete instalado lo consume. |
| Comando/cwd | `adapterConfig.command`, `adapterConfig.cwd` | El default de `command` es `opencode`. El PATH del servicio puede diferir del shell interactivo. |
| Modelo auxiliar | `PAPERCLIP_OPENCODE_SMALL_MODEL` | Debe ser servible por el gateway; evita que el modelo small default falle en session titles. |
| Clave del adapter gateway | `adapterConfig.apiKey` o referencia gestionada | Revisar la representación redactada/config-revisions; jamás imprimir el valor. |
| URL del gateway | `adapterConfig.apiBaseUrl` | Debe dirigirse al API, no al health exporter ni a una ruta web de dashboard. |

### `PAPERCLIP_OPENCODE_PROVIDERS` y sustituciones env

El adapter interpreta la configuración JSON inyectada y admite placeholders del
estilo `{env:VAR}`. En la versión fuente inspeccionada, la sustitución ocurre en
el proceso Paperclip/adapter usando el entorno del run o el entorno del proceso
servidor. Si la variable existe solo en el shell del operador, el valor puede no
llegar al proceso servidor. No imprimir la variable para comprobarla; validar
por presencia/resultado funcional en el contexto autorizado.

Las variables cargadas con dotenv pueden no aparecer en `/proc/<pid>/environ`:
ese archivo expone principalmente el entorno de exec, no todas las mutaciones
hechas después por dotenv. No concluir que `.env` no se cargó solo por una
lectura de `/proc`.

### Model IDs con segmentos anidados

`provider/modelId` necesita al menos una barra. El parseo de OpenCode usa el
primer segmento como provider y el resto como ID del modelo:

- `litellm/gpt-6-luna` → provider `litellm`, model `gpt-6-luna`
- `litellm/azure_ai/gpt-6-luna` → provider `litellm`, model `azure_ai/gpt-6-luna`

El ID exacto debe existir en `provider.<id>.models` o estar resuelto por la
fuente de modelos admitida por OpenCode.

## 3. Resolución de comando y diferencias entre test y execute

El test de adapter y la ejecución pueden resolver `command` de forma diferente.
En el `test.js` instalado se lee `config.command` con default `opencode`; el
`execute.js` también considera `PAPERCLIP_OPENCODE_COMMAND`. Por eso:

- Un run que usa `PAPERCLIP_OPENCODE_COMMAND` puede funcionar aunque el test de
  UI diga `Command not found in PATH`.
- Un shell interactivo puede resolver `opencode`, mientras que el servicio
  systemd de usuario tiene un PATH reducido.
- Comparar `adapterConfig.command`, entorno del servicio y comando del run antes
  de modificar cualquiera.

Si se confirma PATH incompleto en un servicio systemd, un drop-in como
`~/.config/systemd/user/paperclipai.service.d/10-path.conf` puede extender PATH.
Modificar drop-ins y reiniciar el servicio son cambios persistentes: primero
presentar diff/propuesta, solicitar autorización y derivar la operación de
servicio a `ree-paperclip-instance-admin`.

## 4. `Model unavailable`: árbol de diagnóstico

1. Leer `adapterConfig.model` y validar `provider/modelId`.
2. Revisar `opencode.json`: provider bajo la propiedad top-level `provider`, ID
   del provider coincide exactamente y el mapa `models` incluye el ID.
3. Si Paperclip inyecta providers, revisar forma y disponibilidad de
   `PAPERCLIP_OPENCODE_PROVIDERS` en el entorno servidor.
4. Ejecutar `opencode models` en el host/entorno que usa el adapter. El test
   puede ejecutarse en un target remoto; el catálogo local del operador no
   demuestra el remoto.
5. En la versión instalada, el adapter cachea la lista de modelos usando
   command/cwd/env como clave; en miss actualiza (`opencode models --refresh`)
   y vuelve a enumerar. La salida de refresh por sí sola puede ser solo una
   confirmación; se debe revisar la enumeración posterior.
6. `OPENCODE_ALLOW_ALL_MODELS=true` evita el preflight de disponibilidad, pero
   no el `getModel()` de OpenCode: no hace que un provider/model inexistente se
   vuelva válido. El camino remoto también respeta el bypass; no usarlo como
   solución general ni dejarlo activado sin decisión consciente.
7. Confirmar `PAPERCLIP_OPENCODE_SMALL_MODEL` si falla operación secundaria de
   títulos/summaries aunque el modelo principal esté disponible.

El preflight en target remoto es best-effort en fallos de comando/timeout o
catálogo vacío; pero si sí obtiene modelos y el ID configurado falta, puede
abortar con `Configured OpenCode model is unavailable on the remote execution
target`. Determinar qué camino se ejecutó antes de cambiar config.

## 5. Autenticación Hermes gateway

`hermes_gateway` requiere `apiBaseUrl` y `apiKey` (el adaptador acepta alias
`url`/`token` en ciertos caminos; confirmar schema instalado). Su `test-environment`
normaliza URLs y comprueba liveness/health. Una prueba verde no garantiza que el
secreto almacenado sirva para ejecutar `POST /v1/runs`.

En una topología local observada:

- API Hermes: `http://127.0.0.1:8642`.
- Health exporter separado: `8645`.
- Dashboard: `9119`; si se configura su raíz, el adapter puede normalizar a
  `/api`, pero dashboard `/chat` no equivale automáticamente a la API gateway.

Confirmar endpoints con config y schema instalados. Un `POST /v1/runs` crea un
run (side effect), no es un probe inocuo: ejecutarlo únicamente con autorización
explícita, payload inocuo y registro de run ID. Como diagnóstico no mutante,
preferir `GET /v1/runs/<id>` de una ejecución ya existente. HTTP 401/403 es
`hermes_gateway_auth_failed` en el código inspeccionado; 404 apunta a endpoint
no soportado y 429 es rate limit. Alinear timestamp y run antes de atribuirlo.

## 6. Secreto desalineado

1. Correlacionar 401 de Paperclip con log Hermes para el mismo timestamp.
2. `paperclipai agent config-revisions <agentId>`: identificar el secretId de la
   configuración activa (la ruta exacta del campo depende del schema y versión).
3. `paperclipai secrets usage <secretId>`: confirmar sus consumidores.
4. Comparar la credencial efectiva con la fuente de verdad en memoria/función
   local, mostrando solo igualdad/no igualdad o metadatos no sensibles; no
   imprimir valores o longitudes del secreto como si fueran prueba de igualdad.
5. Si hay discrepancia, preparar plan de rotación y solicitar autorización.
6. La rotación soporta `paperclipai secrets rotate <secretId> --value-env
   <ENV_VAR>`; nunca pasar la key literal con `--value`.
7. Reset de sesión y heartbeat también son mutaciones/ejecución de agente;
   requieren autorización propia y verificación posterior.

No recrear agente para corregir credencial. No alterar secret_ref a espaldas de
Paperclip. Después de rotar, `errorReason` puede permanecer hasta una ejecución
exitosa nueva; confirmar un `lastRunId` nuevo y actividad real.

## 7. OpenCode `serve --service`

`opencode run` puede conectarse a un daemon de larga vida. El entorno/config del
daemon es el efectivo; las variables y `XDG_CONFIG_HOME` del cliente pueden no
llegarle. Diagnosticar sin reiniciar:

1. `opencode debug paths` para la config dir efectiva.
2. `opencode debug config` para la configuración resuelta (revisar que no
   exponga credenciales al copiar/compartir salida).
3. Verificar entorno del daemon y provider definido.
4. Solo tras acordar cambio: `opencode service set env <VAR> <value>` o colocar
   la key en el `.env` que lee OpenCode; un `opencode service restart` es una
   mutación del daemon.
5. Nunca reiniciar el daemon desde un shell con `XDG_CONFIG_HOME` temporal; el
   proceso puede heredar esa ruta y cargar config de prueba.

## 8. Compatibilidad de modelo y LiteLLM

Que `opencode models` y el hello probe pasen demuestra descubrimiento y un
camino limitado de request, no compatibilidad total. Si una llamada de
herramientas falla 400 por parámetros que el deployment no acepta (p. ej.
`reasoning_effort`), clasificar como incompatibilidad de request/modelo, no como
401/auth. Probar con modelo conocido y evidencias del error redactadas. Para
cambios a tiers, fallbacks o despliegue Azure AI Foundry, delegar al skill
`litellm-azure-foundry-config`; no compensar alterando modelos sin autorización.

## 9. Otros límites de alcance

- El ENOENT de `@paperclipai/server/dist/vendor/.../opencode.exe` puede ser del
  native runner empaquetado, no de `opencode_local`. Confirmar versión, código
  propietario y existencia del path antes de proponer puente. Una actualización
  puede regenerar el vendor tree. Cambios pre-start pertenecen a operación de
  instancia y exigen aprobación.
- `hermes_gateway` en la versión inspeccionada no implementa company skill sync
  (`supported=false`); no diagnosticar un catálogo vacío como fallo de sync.
- `paperclipai service restart` es hot restart y puede preservar runs, pero
  sigue siendo operación de instancia; consultar `ree-paperclip-instance-admin`
  y no usarlo como arreglo genérico para falta de progreso.
- `opencode_local` puede tener runtime legacy y no inferir disposition del
  issue; el estado del board pertenece a `ree-paperclip-board-ops`.
