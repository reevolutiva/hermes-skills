# Alertas en el Prometheus del clúster (chart `prometheus-community/prometheus`)

## Dónde van las reglas, y la trampa que las deja inertes

El clúster corre el chart con `alertmanager.enabled: false`. Las reglas van en el **HelmRelease**
(`apps/monitoring/prometheus.yaml`), no en un `PrometheusRule` (ese CRD **no está instalado**:
`error: the server doesn't have a resource type "prometheusrule"`).

`serverFiles.alerts` se renderiza como la clave `alerts` del ConfigMap `prometheus-server`, que ya
está en `rule_files` (`/etc/config/alerts`). Hay un reloader
(`prometheus-server-configmap-reload`, `--reload-url=http://127.0.0.1:9090/-/reload`) que la aplica
**caliente**: no hay que reiniciar nada.

**La trampa:** el chart pasa el valor por `toYaml`, así que va el YAML de las reglas **directo**:

```yaml
serverFiles:
  alerts:
    groups:            # CORRECTO
      - name: mis_reglas
        rules: [...]
```

Anidar un nombre de archivo adentro (`alerts: {mi-archivo.alerts: |- ...}`) renderiza un grupo
**llamado como el archivo** y **cero reglas**. El render no da error, `make lint` pasa, el ConfigMap
se crea y Prometheus no carga ninguna alerta: **un gate que no existe y parece puesto**. Se detecta
sólo mirando la ConfigMap del clúster:

```bash
kubectl -n monitoring get cm prometheus-server -o json | \
  /usr/bin/python3 -c "import json,sys,yaml; print(yaml.safe_load(json.load(sys.stdin)['data']['alerts']))"
```

**Validar antes de mergear, con el chart real** (no alcanza con leer el YAML):

```bash
helm repo add prom https://prometheus-community.github.io/helm-charts && helm repo update prom
/usr/bin/python3 -c "import yaml; d=yaml.safe_load(open('apps/monitoring/prometheus.yaml')); \
  yaml.safe_dump(d['spec']['values'], open('/tmp/pv.yaml','w'), sort_keys=False)"
helm template prometheus prom/prometheus --version <la pineada> -f /tmp/pv.yaml | \
  /usr/bin/python3 -c "import yaml,sys
for d in yaml.safe_load_all(sys.stdin):
    if d and d.get('kind')=='ConfigMap' and d['metadata']['name']=='prometheus-server':
        print(yaml.safe_load(d['data']['alerts']))"
```

## Tres reglas de diseño para que la alerta sirva

1. **La alerta no puede depender de un canal que el diseño cierra.** `headroom` tiene una
   NetworkPolicy que sólo admite al pod del proxy; Prometheus vive en `monitoring`, así que el scrape
da **`Connection refused`**. Un `up{...} == 0` ahí es un **falso positivo permanente** (se ve en el
   clúster: la regla queda `pending` con `up=0` y pasa a `firing` para siempre). Y encima es sordo al
   caso peor. Medir el canal antes de escribir la expresión:

   | Origen | `http://<pod-ip>:8787/metrics` |
   |---|---|
   | pod de Prometheus (`monitoring`) | `Connection refused` |
   | pod de LiteLLM (`litellm`) | `200` |

2. **Una serie ausente no dispara.** Si se alerta sobre `up` de un workload que **no existe**, no hay
   serie y el resultado es **vacío**: la alerta se apaga justo cuando más hace falta. Es exactamente
   el caso «nadie declaró el sidecar». Hay que envolver con `absent()` **primero**:

   ```promql
   absent(kube_deployment_status_replicas_available{namespace="<ns>",deployment="<dep>"})
     or kube_deployment_status_replicas_available{namespace="<ns>",deployment="<dep>"} < 1
   ```

   `kube-state-metrics` ya se scrapea, así que no depende de tocar el target. Y la rama `< n` es la que
   detecta el pod caído.

3. **Un target anotado que no se puede scrapear es ruido permanente.** Anotar
   `prometheus.io/scrape: "true"` un pod cuya NetworkPolicy cierra el puerto deja un `up == 0` de por
   vida en la vista de targets. Si el diseño cierra el puerto, **no se anota**: se alerta por
   kube-state-metrics, y el porqué se escribe en el manifiesto.

## Verificar una regla: cuatro consultas, sin tocar el servicio

Contra el Prometheus del clúster, con `wget` (el contenedor **no tiene python ni curl**):

```bash
kubectl -n monitoring exec deploy/prometheus-server -c prometheus-server -- \
  wget -qO- 'http://127.0.0.1:9090/api/v1/rules'      # ¿cargó? state/health/lastError
kubectl -n monitoring exec deploy/prometheus-server -c prometheus-server -- \
  wget -qO- 'http://127.0.0.1:9090/api/v1/alerts'     # ¿hay algo activo?
```

Y para evaluar **la expresión** (las dos ramas, sin bajar el sidecar): se consulta
`/api/v1/query?query=<expr urlencoded>` con el nombre real (espera **vacío**) y con un nombre
**inexistente** como control positivo (espera que **dispare**), más un control de umbral
(p. ej. `< 2` en vez de `< 1`) para probar que la rama `<` retiene series. Todo se evalúa con
`/usr/bin/python3` en el host, no dentro del pod.

**`state` tarda en asentarse:** recién recargada, la regla reporta `health: unknown` y puede quedar un
`firing` residual de la versión anterior. No es una falla: esperar un ciclo de evaluación (~90 s con
`interval: 30s` + `for`) y volver a leer. El valor esperado es `state: inactive`, `health: ok`.

## El gate que ya falló una vez

`make lint` **no** mira estas reglas: son un string adentro de `values` de un HelmRelease. Todo lo que
hay que verificar acá se verifica contra el clúster (`/api/v1/rules`) o con `helm template`. Un
`make lint` verde no dice **nada** sobre si la alerta existe.
