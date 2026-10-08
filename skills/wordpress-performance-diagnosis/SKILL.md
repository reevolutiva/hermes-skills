---
name: wordpress-performance-diagnosis
category: infrastructure
version: 1.0.0
description: "Use when a WordPress in K8s is slow or unhealthy."
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [wordpress, kubernetes, performance, cache, diagnostics]
    related_skills: [wordpress-bedrock-migration, reevolutiva-infra-gitops]
---

# WordPress en Kubernetes: diagnosticar lentitud y salud

## When to Use
Cuando alguien dice "el sitio está lento", "se siente pesado", "¿está desplegado de
verdad?" o "verificá su estado actual y las configuraciones que lo hacen lento" sobre un
WordPress que corre en Kubernetes. El deliverable no es una impresión: es **un número y una
causa**, con el antes/después medido. Usalo aunque el sitio parezca funcionar — el caso
típico es un sitio que responde `200` y tarda segundos. También cuando el sitio está
**caído** (`502`, error duro, «¿por qué se cayó?»): la sección *El sitio CAÍDO* camina la
cadena desde el borde hacia el pod y separa WordPress de la plataforma.

El detalle de infraestructura del clúster (nodos, túnel de Cloudflare, Longhorn, secretos)
no se repite acá: vive en `reevolutiva-infra-gitops` y `wordpress-bedrock-migration`.

## La escalera: subir en orden, no saltarla

Cada escalón descarta una capa. Saltear al de caché es cómo se termina "optimizando" un
disco que respondía en 0,3 ms.

| # | Pregunta | Cómo se contesta |
|---|---|---|
| 1 | ¿Quién sirve el dominio? | log del conector de Cloudflare (`originService=`) + `tailscale status` |
| 2 | ¿El pod está sano y con qué recursos? | `get pods -o wide`, `lastState.terminated.reason`, `resources:` |
| 3 | ¿Es almacenamiento o es render? | estático del core vs home **dentro del pod** |
| 4 | ¿Dónde se paga el tiempo? | 3 mediciones: borde / ingress / pod |
| 5 | ¿Hay alguna caché activa? | `cf-cache-status`, `advanced-cache.php`, `object-cache.php` |
| 6 | ¿Qué agrega trabajo por request? | barrido de redirects, WP-Cron, colas |

### 1. Quién sirve el dominio — y desde qué túnel

**Primero, ubicar el túnel activo**: en un clúster puede haber múltiples deployments de
cloudflared (legacy + produccion) en el mismo namespace. Listarlos todos y leer la
configuración remota del que esté activo:

```bash
kubectl get deploy -A | grep cloudflare
# Para cada deploy: buscar "Updated to new configuration" en sus logs
kubectl -n <ns> logs deploy/<cloudflared> --tail=100 | grep 'Updated to new configuration'
```

El JSON de configuración trae `originService` por hostname y la `version=N`. El `version`
más alto entre los deployments **no siempre es el que manda**: cada túnel autentica con su
propio token y Cloudflare Zero Trust rutea por túnel, no por conector. Si hay dos túneles
distintos, verificar cuál tiene el hostname en su configuración remota.

**Después, verificar DNS**: si un hostname responde con headers de servidor legacy (p.ej.
`x-litespeed-cache: hit`) pero ningún túnel apunta a ese host, el registro DNS A puede ir
directo a la IP pública del host legacy sin pasar por Cloudflare:

```bash
dig +short <dominio> A
```

Una IP que NO es de Cloudflare (no empieza con 104.x, 172.x) indica ruta directa.

**También revisar el host legacy por Docker** como referencia histórica:

```bash
ssh <user>@<host> 'docker ps --format "{{.Names}} {{.Status}} {{.Image}}" | grep -iE "<app>|wordpress|ols|caddy"'
```

Un host legacy con los contenedores `Up (healthy)` pero sin tráfico es un **huérfano vivo**,
no un archivo: no está retirado y sigue consumiendo. Decirlo así en el reporte.

### 2. Nodos y pods — el nodo manda

**Antes de mirar pods, mirar nodos**: un nodo `NotReady` bloquea todo lo programado ahí y
explica pods en `ContainerCreating`/`Pending` sin que la aplicación tenga la culpa.

```bash
kubectl get nodes -o wide
```

Si hay nodos `NotReady`, los pods atascados en ese nodo son **consecuencia**, no causa.
Listarlos para saber el alcance pero no diagnosticarlos todavía:

```bash
kubectl get pods -A -o wide | grep -E 'ContainerCreating|Pending|Terminating'
```

**Después, estado y causa de reinicio** para los pods que sí tienen nodo:

```bash
kubectl -n <ns> get pods -o wide
kubectl -n <ns> get pod <pod> -o jsonpath='{range .status.containerStatuses[*]}{.name} restarts={.restartCount} last={.lastState.terminated.reason} exit={.lastState.terminated.exitCode}{"\n"}{end}'
```

`last=OOMKilled exit=137` junto a un `memory_limit` de PHP en su default no es coincidencia
(ver *Reglas* abajo). `restartCount` alto con `last` vacío es un reinicio limpio de
despliegue, no un crash.

### 3. Separar almacenamiento de render

```bash
kubectl -n <ns> exec deploy/<sitio> -- sh -c '
for i in 1 2 3; do curl -s -o /dev/null -w "static ttfb=%{time_starttransfer} code=%{http_code}\n" \
  -H "Host: <dominio>" http://127.0.0.1/wp/wp-includes/js/jquery/jquery.min.js; done
for i in 1 2 3; do curl -sL -o /dev/null -w "render ttfb=%{time_starttransfer} total=%{time_total} redir=%{num_redirects} size=%{size_download}\n" \
  -H "Host: <dominio>" -H "X-Forwarded-Proto: https" "http://127.0.0.1/?cb=$RANDOM$i"; done'
```

Estático en **milisegundos** + home en **segundos** ⇒ el costo es PHP, y ningún ajuste de
almacenamiento (réplicas, `dataLocality`, discos) lo va a mover. Si el estático **también**
tarda, el problema está antes de PHP y el camino es el `fsGroup`/I-O del volumen (ver
`wordpress-bedrock-migration`).

### 4. Dónde se paga el tiempo

Medir la misma URL por Cloudflare, contra el ingress y contra el pod, y comparar el
`%{time_starttransfer}` de la **última** respuesta del redirect. Comando listo en
`references/probe-recetas.md`.

### 5. Auditoría de caché — las tres capas se pierden en silencio

```bash
curl -s -D- -o /dev/null "https://<dominio>/?cb=$RANDOM" | grep -i 'cf-cache-status'
kubectl -n <ns> exec deploy/<sitio> -- sh -c \
  'ls -l /var/www/html/web/app/advanced-cache.php /var/www/html/web/app/object-cache.php 2>&1'
kubectl get pods -A | grep -i redis
```

Sin `advanced-cache.php` no hay page cache; sin `object-cache.php` no hay object cache. Un
Redis sano en el clúster que el sitio **no** usa es la mejora más barata que hay.

**Las rutas de archivos varían por imagen**: en imágenes estándar (`wordpress:latest`,
`php:8.3-apache`) es `/var/www/html/wp-content/`. En imágenes Bedrock es
`/var/www/html/web/app/`. Verificar con `ls` antes de declarar ausencia.

### 6. Trabajo extra por request

Barrer un conjunto de URLs y ver **cuáles redirigen**. Receta y tabla de significados en
`references/probe-recetas.md`: un `301` a `https://` es benigno y un `307` con parámetro
agregado no.

## El sitio CAÍDO (error duro): diagnosticar la cadena, no WordPress

Un `502` no es lentitud: es **ausencia de backend**. La escalera de arriba asume que alguien
responde; acá primero se ubica **quién** contesta y después se camina la cadena hacia adentro.

```
Cloudflare (túnel `front`, configuración REMOTA) → proxy del tailnet del Ingress
(`ts-<nombre>-<hash>-0`, en flux-system) → traefik → Service → endpoints → pod
```

```bash
T=$TMPDIR
timeout 25 curl -sS -o $T/f.html -D $T/f.h https://<dominio>; head -8 $T/f.h  # quién contesta
kubectl get nodes --no-headers
kubectl -n <ns> get pods -o wide --no-headers
kubectl -n <ns> get endpoints --no-headers                                  # ← la señal más rápida
kubectl get ds -A                                                           # ← la segunda
kubectl -n <ns> get events --sort-by=.lastTimestamp | tail -15
```

- **`endpoints: <none>` ⇒ el problema está ANTES del pod.** Un pod `Running` con
  `ready=false` no es un backend: el error del borde es consecuencia, no causa.
- **Un DaemonSet con `deseados < cantidad de nodos` es un incidente latente**: algo lo está
  filtrando (un taint o un nodeSelector) y va a explotar en el próximo reinicio de ese nodo.
- **Pods en `ContainerCreating` con el nodo `Ready` ⇒ mirar el almacenamiento, no la
  aplicación.** `volumes.longhorn.io` en `attaching` / `robustness=unknown` y **sin
  `instance-manager` en ese nodo** = el motor no puede correr ahí y el volumen no se adjunta
  nunca.
- **Un taint de carga no puede alcanzar a la plataforma.** Un taint como `env=prod:NoSchedule`
  existe para que no aterricen *cargas* en el nodo de producción; si el motor de
  almacenamiento no lo tolera, ese nodo no puede montar **sus propios** volúmenes. Y como
  `NoSchedule` **no expulsa** los pods que ya corren, el clúster se ve **sano hasta que el nodo
  reinicia**. Todo lo que corre en todos los nodos (CSI, CNI, DNS, exporters) tiene que tolerar
  los taints de carga. Se declara en los `values` del HelmRelease de storage, y las claves
  exactas se leen de las plantillas del chart, no de memoria.
- **Un reinicio no es el final de la cadena:** agente K3s → `instance-manager` → adjuntar el
  volumen → pod `Ready` → endpoints. «El nodo volvió» ≠ «el sitio volvió», y un reinicio de
  nodo puede medir minutos.
- **Restaurar son DOS movimientos, siempre:** el parche en caliente que devuelve el servicio
  (~1 min) **y** el cambio en el repo, en el mismo movimiento. Si solo se parchea en vivo, el
  `HelmRelease` (interval 1 h) reconcilia, **revierte el parche** y la caída vuelve. Un arreglo
  que no está en Git no es un arreglo, es una demora.
- **Confirmar qué reinició el nodo antes de contarlo.** En Flatcar, un kernel distinto entre
  arranques (`last -x | head`) delata una **actualización de SO**, no un cuelgue; y un `uptime`
  de minutos con unidades en `activating` explica que el nodo esté `NotReady` *ahora* — el
  `lastTransitionTime` de las condiciones dice cuándo empezó, no cuánto lleva.
- **Si la carga vive en un solo nodo, no tiene failover**, y eso va en el reporte junto con la
  elección pendiente: darle dos nodos a esa carga (taint/selector por *clase*, no por host) o
  aceptar el nodo único con reinicios planificados (cordon + drain antes de actualizar).
- **Sin alertas, la caída la descubre el dueño preguntando.** Medir la duración real (`uptime`
  del nodo, antigüedad de los pods) antes de describir el alcance del incidente.

## Reglas que aplican SIEMPRE

- **`cf-cache-status: DYNAMIC` significa que el borde NO está cacheando**, no que el sitio
  sea dinámico. Revisarlo en cada respuesta.
- **Un 404 con el contenido real del sitio no es un 404 de presencia — es un 404 de respuesta HTTP.** Cuando OpenLiteSpeed resuelve un directorio sirviendo `index.php` con status 404 (porque `indexFiles` no lista `index.php`), el body es la portada renderizada y el monitor la ve caída. Señal: `curl -w '%{http_code}'` da 404 pero el HTML tiene `body class="home …"` y el contenido esperado. Esto NO es lo mismo que un 404 de URL inexistente (`class="error404 …"`).
- **Un `307` que agrega un parámetro (`?v=<hash>`) a cada URL del front es un defecto.** Es un
  *cache buster*: agrega un round trip por visita fría y **es la causa directa de que ninguna
  caché de borde acierte**. Mientras exista, activar caché es trabajo perdido.
- **`DISABLE_WP_CRON` tiene que estar en `true`.** Si el dominio público resuelve a Cloudflare
  desde adentro del pod, el loopback de `wp-cron.php` **sale a internet, entra por el túnel y
  muere** (`context canceled` en el log del conector), y la cola de Action Scheduler queda con
  `pending`/`failed`. El cron va por un **CronJob que pegue por dentro del Service**, nunca por
  el hostname público. Generalizalo: **cualquier loopback a la URL pública desde este clúster
  es una salida a internet** (ya rompió también un readiness probe).
- **El `memory_limit` por defecto de una imagen `php:8.3-apache` (128M) no alcanza para
  arrancar WordPress con WooCommerce en el autoload**: el bootstrap agota la memoria. Medirlo
  (`php -i | grep memory_limit`) antes de atribuir lentitud a la CPU, y mirar el `OOMKilled`
  del pod — el contenedor con `limits.memory: 1Gi` se cae por lo mismo.
- **Una sola réplica con `strategy: Recreate` convierte cualquier reinicio en un corte
  visible.** Decirlo en el reporte, no tratarlo como detalle.
- **No hay mejora demostrable sin el antes/después con la misma prueba** (`?cb=$RANDOM` +
  `%{time_starttransfer}`). Un `200` detrás de Cloudflare tampoco prueba que el origen esté
  vivo: puede ser caché.

## Trampas que cuestan rondas enteras

- **No leer `Longhorn` en `-n longhorn-system`.** Sus CRD son *cluster-scoped* y el release
  vive en otro namespace (acá, `flux-system`), así que un
  `kubectl -n longhorn-system get volumes.longhorn.io` devuelve *No resources found* con el
  storage sano. Usar `-A`, y el estado real con `custom-columns` (`NODE`, `REPLICAS`,
  `ROBUSTNESS`, `STATE`). **Un vacío que confirma lo que uno sospecha no es un dato.** Mismo error de clase, otro
  recurso: el destino de backup de Longhorn **no** es el setting
  `settings.longhorn.io/backup-target` (devuelve `NotFound` y hace concluir que no hay
  backups) sino el CRD **`backupTargets.longhorn.io`**. Antes de declarar una ausencia,
  verificar el **kind** contra la versión instalada — un chequeo negativo hecho con el nombre
  viejo no es un chequeo.
- **El `sh` de las imágenes mínimas es `dash`**: no hay `time` ni `find`. Cronometrar con
  `date +%s%N` o con `microtime(true)` dentro del propio probe, y desconfiar de todo
  resultado instantáneo (un `find` ausente devuelve "0 archivos en 2 ms").
- **Lo mismo aplica en imágenes OLS/php-apache para `command` en el Deployment.** Un `sed` que corrige el vhost no se puede probar con `lshttpd -r`: no es un reload, es un cambio de configuración que necesita `lswsctrl restart` para tomar. Verificar el .conf en el pod, no asumir que el restart del proceso lo aplica.
- **Un probe por CLI no reproduce lo que depende del contexto web.** Medido: un redirect de
  front-end que aparece en cada request real **no se dispara** en CLI. Si el probe y el sitio
  real se contradicen, gana el sitio real.
- **El estado activo/archivado de una app lo manda el manifiesto del clúster**, no el `README`
  de la carpeta de la app ni los docs de exposición: verificado que divergen. Ante duda,
  `kubectl -n <ns-flux> get kustomizations` y el `suspend` del manifiesto.
- **Nunca imprimir credenciales al sondear la base.** El pod ya tiene `DB_HOST`/`DB_USER`/
  `DB_PASSWORD` en su entorno: usar PDO desde ahí, nunca `-p<password>` en la línea de
  comandos ni leer el `.data` de un Secret. Receta en `references/probe-recetas.md`.

## Orden de arreglo (por impacto)

1. **Sacar el cache buster / redirect del camino.** Es prerequisito, no optimización: con él
   adentro ninguna caché acierta.
2. **Object cache con el Redis que ya existe en el clúster**, después page cache, y recién
   entonces el borde.
3. **`DISABLE_WP_CRON=true` + CronJob interno.**
4. **`memory_limit` a 256M/512M** en la imagen, y ajustar `limits`/`requests` del pod.
5. Recién al final el rediseño de capas (código en imagen, `uploads` en PVC): mover decenas de
   miles de archivos fuera del volumen replicado por red quita trabajo del camino crítico,
   **pero no arregla un render sin caché**.

## Cerrar el reporte con honestidad

Si la causa no se identificó del todo, decirlo así **con lo que sí se midió** (impacto, URLs
 y capas afectadas, lo que se descartó y cómo) y con el siguiente paso concreto. No cerrar
 afirmando un culpable sin traza, y no prometer que una caché arregla el sitio mientras el
 redirect siga ahí.
