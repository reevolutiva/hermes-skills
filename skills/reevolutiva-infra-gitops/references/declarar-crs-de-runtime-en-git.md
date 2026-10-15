# Declarar en Git un CR que un controlador posee en runtime

Contexto: Flux aplica con **server-side apply** y `force: false`. Cuando el objeto lo crea
y mantiene el controlador de una plataforma —`nodes.longhorn.io` lo crea `longhorn-manager`
en el namespace del release—, **el dueño de cada campo no es Flux**. Declararlo en Git es lo
correcto (la capacidad del clúster no puede vivir en un objeto que ningún PR revisa), pero
hay que hacerlo sin provocar un conflicto.

## 1. Medir la propiedad antes de escribir el manifiesto

```bash
kubectl -n <ns> get <crd> <nombre> --show-managed-fields -o json \
  | jq '.metadata.managedFields[] | {manager, operation, subresource}'
```

- **`kubectl get -o json` OCULTA `managedFields`**: sin `--show-managed-fields` la lista sale
  vacía y se concluye lo contrario de la verdad (parece que nadie posee el objeto).
- Un controlador que escribe con `Update` (no SSA) igual figura como dueño, y el mensaje del
  conflicto lo nombra: `conflict with "longhorn-manager" using longhorn.io/v1beta2`.

## 2. Dry-run que emula a Flux (la única prueba que vale antes del PR)

```bash
kubectl kustomize <dir-de-la-kustomization> \
  | kubectl apply --server-side --dry-run=server --field-manager=kustomize-controller -f -
```

`--dry-run=server` es obligatorio (el cliente no evalúa conflictos SSA) y el
`--field-manager` tiene que ser el de Flux, no `kubectl`.

| cambio en el manifiesto | resultado |
|---|---|
| clave NUEVA en un mapa (`spec.disks.local-disk-data`) | aplica (exit 0) — el mapa es granular campo por campo |
| campo existente co-poseído con su valor VIVO | aplica (exit 0) |
| campo existente con valor DISTINTO (`allowScheduling: true → false`) | `Apply failed with 1 conflict: conflict with "<manager>" … <campo>` (exit 1) |

## 3. Qué declarar de un disco de Longhorn (`nodes.longhorn.io`)

| campo | ¿en Git? | por qué |
|---|---|---|
| `path` | sí | es la decisión (dónde vive el disco) |
| `allowScheduling` | sí | es la decisión (si recibe réplicas) |
| `diskType` | sí (`filesystem`) | es decisión y el manager no lo cambia |
| `storageReserved` | **sí, en un disco declarado** | MEDIDO: el manager lo deriva (%= setting `storageReservedPercentageForDefaultDisk`) **sólo para los discos que crea él**. Un disco que declara Git queda **sin reserva** después del primer reconcile (`storageReserved` ausente ⇒ `storageAvailable` = el filesystem entero) y el planificador puede llenar el volumen completo, que suele ser el compartido con toolchains y caches del nodo. Se declara **10 % de `status.diskStatus.<disco>.storageMaximum`** (la convención de los discos del manager); si una versión futura empezara a derivarlo, el reconcile avisa como conflicto en vez de derivar en silencio |
| `tags`, `evictionRequested` | **no** | los escribe la UI/el manager (evacuación de disco) |
| `spec.name` y los `allowScheduling`/`tags` de nivel nodo | **no** | ya los posee y mantiene el manager; declararlos sólo amplía la superficie de conflicto |

- **Nombre del disco:** los que Longhorn crea solo quedan como `default-disk-<hash>` (esa
  clave es la que hay que citar en Git); un disco declarado conserva el nombre que se le da.
- **El `path` tiene que existir y estar montado en el nodo ANTES del apply** — verificado
  dentro del nodo (`ls -ld <path>` + `df -h <path>` + `df -h /`), no asumido desde el
  manifiesto. Sin la ruta, el manager deja el disco en error y no da capacidad.

## 4. Cambiar un campo que el manager ya posee (dos pasos)

1. Ejecutar el cambio por la vía del manager (UI/API del controlador): el manager escribe el
   campo y pasa a ser dueño del valor nuevo.
2. Verificar el valor **vivo** y el dueño del campo (`--show-managed-fields` + `-o jsonpath`).
3. Abrir el PR declarando **ese mismo valor** (co-poseer, sin `force`): con el valor
   coincidente el apply entra y el campo queda co-poseído por los dos managers.
4. Registrar el paso fuera de Git en el issue **con su deuda documentada** — es la excepción
   puntual aceptada a «nunca `kubectl patch`», no la estrategia normal.

`force: true` no es una alternativa: es el mecanismo que borró el Deployment de CoreDNS y
 dejó el sitio en 502 (~20 min).

## 5. Estructura en el repo

- Directorio propio (`clusters/<clúster>/<tema>-nodes/`), un archivo por nodo, y su
  Kustomization con:
  - `dependsOn` de la Kustomization que instala la plataforma (el CRD y el manager tienen que
    existir primero; si no, el manifiesto no se puede ni aplicar),
  - `prune: false` (quitar el manifiesto deja de gestionar el disco; no borra el objeto),
  - **`wait: false`** — `status.conditions` de estos CRs no lleva `observedGeneration`, así que
    kstatus lo lee `InProgress` y `wait: true` pinta de rojo una Kustomization que sí aplicó,
  - `force: false` explícito y comentado: un campo en disputa tiene que verse como rojo de
    Flux, no resolverse tomando el objeto.

## 6. Gate de aceptación de un disco declarado

```bash
kubectl -n <ns> get kustomizations <ks> -o json   # Ready=True en la revisión nueva, sin force
kubectl -n <ns> get nodes.longhorn.io <nodo> -o json   # spec.disks: Git == vivo
# el estado del disco: conditions (Ready/Schedulable) + storageAvailable/storageMaximum.
# `diskState` viene VACÍO en las versiones en uso — el gate que lo espera `ready` se lee como falla.
kubectl -n <ns> get replicas.longhorn.io -o wide | grep -c <nodo>   # retiro inocuo sólo con 0
kubectl get pvc -A | grep -v Bound            # vacío
# dentro del nodo:
df -h / <ruta-del-disco>                      # el raíz no crece; el volumen tiene la capacidad nueva
ls -ld <ruta-del-disco>                       # el manager lo inicializó (dir + su archivo de config)
```

- **El gate se corre después de que Flux aplique, y sobre el CR — no sobre el manifiesto.**
  El apply no espera (`wait: false`) y el disco tarda lo que tarde el manager en inicializarlo.
- **Un retiro con réplicas en el disco viejo reconstruye** (y con el nodo apretado puede no
  caber): verificar 0 réplicas antes de darlo por inocuo.
- **La escritura fuera de Git (§4) se registra como deuda en el ADR y en el issue.** Si se
  repite más de una vez por nodo, deja de ser excepción: se reabre la decisión.
