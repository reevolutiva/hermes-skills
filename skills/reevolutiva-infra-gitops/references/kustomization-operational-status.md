# Estado operativo de Kustomizations Flux

Usar esta referencia al revisar suspensiones, Kustomizations fallidas o diferencias entre `Ready=True` y disponibilidad del servicio.

## Clasificación: mantener separados tres estados

| Dimensión | Evidencia | Qué demuestra |
|---|---|---|
| Intención declarada | `spec.suspend` en Git, overlay del clúster y diseño/documentación | Si Flux debe reconciliar o esperar |
| Estado de Flux | `Ready`, `Healthy`, `Reconciling`, revisión aplicada/intento y dependencias | Si el controlador pudo aplicar/validar los manifiestos |
| Operación real | Deployment/StatefulSet/Pod/Service/PVC, eventos y prueba funcional | Si el servicio está disponible y hace su función |

Una Kustomization `Ready=True` con `wait: false` solo confirma que Flux aplicó los objetos; no valida la salud de pods. Un pod `Running` tampoco prueba API, modelo o flujo de datos.

## Procedimiento

1. Verifica el contexto del clúster y lee el diseño/manifiestos antes de decidir si una pausa es intencional. Localiza `dependsOn`, `wait`, `prune`, ruta y recursos que aplicará la Kustomization.
2. Captura el estado declarativo y Flux sin imprimir Secret `.data`:

   ```bash
   kubectl -n flux-system get kustomization <nombre> -o json | jq '{name:.metadata.name,suspend:(.spec.suspend // false),generation:.metadata.generation,lastApplied:.status.lastAppliedRevision,lastAttempted:.status.lastAttemptedRevision,conditions:.status.conditions}'
   flux get kustomizations -A
   ```

3. Verifica el runtime por namespace, no solo el resumen de Flux:

   ```bash
   kubectl -n <namespace> get deploy,sts,ds,svc,pvc -o wide
   kubectl -n <namespace> get pods -o wide
   kubectl -n <namespace> get events --sort-by=.lastTimestamp
   ```

   Para una app con `wait: false`, inspecciona explícitamente readiness de Deployments, estados `ImagePullBackOff`/`ContainerCreating`, eventos de PVC/CSI y Service endpoints. Ejecuta una prueba funcional específica: HTTP/API, listado del modelo cargado, operación de lectura/escritura o catálogo de imágenes. Si compruebas TLS, usa `curl` normal y valida `ssl_verify_result=0`; `curl -k` no valida el certificado. `/v2/_catalog` solo enumera repositorios, no garantiza que exista el tag requerido: valida el manifest exacto o el pull desde el nodo destino antes de declarar disponible una imagen.

4. Decide intención sin confundir fallo con pausa:
   - Si el servicio debe estar operativo por diseño, declara `spec.suspend: false` en el overlay por PR y registra los bloqueos observados. Una aplicación no funcional requiere seguimiento/corrección; no la conviertas en pausa silenciosa.
   - Si la pausa es deliberada, declara `spec.suspend: true` en Git y documenta por qué, qué recursos persisten y qué gate permite reanudar.
   - Antes de activar una Kustomization, evalúa si creará PVCs/DBs vacíos, si hay datos previos, qué imagen necesita y cómo se preserva rollback. Una PVC recién `Bound` no implica DB inicializada ni migración aceptada.

5. Valida el cambio declarativo y usa el ciclo PR→merge→Flux:

   ```bash
   make lint
   git diff --check
   kubectl apply --dry-run=server -f clusters/<cluster>/apps.yaml
   ```

   El dry-run server-side valida el recurso contra el API sin aplicarlo. Tras mergear, sincroniza primero el root:

   ```bash
   flux reconcile kustomization flux-system -n flux-system --with-source
   flux get kustomizations -A
   ```

   Luego avanza solo por la cadena de dependencias necesaria y en orden topológico, por ejemplo `infra-controllers` → `infra-configs`/`infra-storage` → `infra-secrets`/`infra-exposure` → `infra-registry`/`apps-databases` → `apps-litellm` → Kustomización objetivo. Ajusta el orden al `dependsOn` real del manifiesto; no copies este ejemplo a ciegas.

6. Verifica el resultado contra el clúster en la revisión nueva: `spec.suspend`, revisiones, condiciones, pods/PVCs/eventos y prueba funcional. Si `flux reconcile` agota el timeout del cliente, el reconcile del controlador puede seguir corriendo: lee las condiciones y eventos antes de volver a dispararlo. `DependencyNotReady` por revisión/dependencia desfasada tras cambiar el root puede ser convergencia transitoria; actualiza primero los ancestros y vuelve a comprobar antes de diagnosticarlo como falla permanente.

7. Actualiza el issue que sigue la desviación con intención Git, estado actual de cada capa, evidencia funcional y bloqueos. No cierres un issue amplio solo porque el PR de declaración de estado se mergeó; deja explícitas las tareas de recuperación y los criterios de aceptación pendientes.

## Dar de baja una carga o un plano entero

Suspender la Kustomization es el **primer** paso, no el último. Un plano se da de baja con seis
barridos; si falta uno, queda una referencia viva que después alguien lee como drift.

1. **Decisión y ruta de reactivación, primero.** Quién lo pide, por qué, y qué haría falta para
   levantarlo de nuevo. Si no está justificado/validado/comunicado, va a referencia — no se borra.
2. **`spec.suspend: true` con motivo en el overlay** (`clusters/<cluster>/apps.yaml`), no solo en
   live: un `suspend=true` que solo está en live es drift. Escribe en el comentario por qué y cómo
   revertir, y abre el PR.
3. **Barrido de residuos live** (los cinco comandos, todos con salida vacía como criterio):

   ```bash
   kubectl get all,ingress,svc,pvc -n <ns>                          # recursos del namespace
   kubectl get pv,pvc -A | grep -i <nombre>                        # volúmenes
   kubectl get volumes.longhorn.io -n flux-system | grep -i <nombre>  # CRD de Longhorn
   kubectl get externalsecret -A | grep -i <nombre>                # secretos que quedan
   tailscale status | grep -i <nombre>                             # dispositivo del tailnet
   ```

   **El namespace se vuelve a crear.** Si está declarado en `infrastructure/configs/namespaces.yaml`,
   `infra-configs` lo recrea aunque `apps-<plano>` esté suspendido: un `kubectl delete namespace`
   parece funcionar y a la hora está de vuelta, vacío. Decidí explícitamente: quitarlo de la
   declaración (baja total) **o** dejarlo vacío y decirlo en el comentario, para que un namespace
   vacío no se lea como drift.
4. **Barrido de documentación.** Las filas del servicio en `docs/auditoria-servicios.md` y cualquier
   inventario o README que lo liste como activo. Marcalas como archivadas con la fecha y la ruta de
   reactivación; no las borres.
5. **Preservar la referencia fuera del clúster.** Los manifiestos de `apps/<plano>/` quedan como
   plantilla y los repos de diseño/estrategia se conservan donde están. "Archivar" es retirar del
   clúster activo, no destruir el material.
6. **Verificar el efecto, no el PR.** Tras el merge: `flux get ks -A` con la Kustomization
   `SUSPENDED=True`, el namespace vacío, y el hostname sin resolver (NXDOMAIN) si tenía ruta.

## Pitfalls

- No concluyas “operativo” desde `Ready=True` si la Kustomization usa `wait: false`; verifica Deployment/Pod y una prueba real.
- No concluyas “pausa intencional” porque live tenga `suspend=true`; compara con Git y el diseño. Live suspendido sin declaración es drift.
- No cambies hijos antes de que el root haya aplicado la revisión nueva; sus dependencias pueden permanecer `DependencyNotReady` hasta converger.
- No asumas que reanudar solo quita una pausa: puede crear PVCs y bases vacías aunque la imagen de app falte; inventaría persistencia y rollback antes.
- No uses `curl -k` como prueba de TLS ni confundas una respuesta de catálogo vacía/incompleta con pipeline de imágenes sano.
