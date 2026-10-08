# Imágenes propias en GHCR: publicar, verificar visibilidad, bajar

Contexto: las imágenes de las apps se construyen en un workflow del monorepo y se
publican en `ghcr.io/<org>/<app>` con el **`GITHUB_TOKEN` del job**
(`permissions: packages: write`), multi-arquitectura (`linux/amd64,linux/arm64`).

## 1. Visibilidad: qué se puede automatizar y qué no

| Camino | Resultado verificado |
|---|---|
| UI: org → Packages → `<paquete>` → Package settings → Danger Zone → Change visibility | funciona (pide escribir el nombre del paquete). **Es el único camino** |
| `PATCH /orgs/{org}/packages/container/{pkg}` con fine-grained PAT | 403 `need read:packages scope` |
| El mismo endpoint con el `GITHUB_TOKEN` del job (`packages: write`) | **404** |

El 404 con el token del job es el dato que importa: **para paquetes de organización el
endpoint de visibilidad no opera**, con ninguna credencial. No es scope, es el endpoint.
Consecuencia operativa: la visibilidad es un **paso manual del dueño**; avisarlo apenas
se publica el primer paquete, no cuando falla un despliegue.

Y **repo ≠ paquete**: publicar el repositorio no publica el paquete.

## 2. Dejar la lectura confiable en el log del build

Paso a agregar al workflow, después del push:

```yaml
      - name: Visibilidad del paquete
        continue-on-error: true          # nunca romper el build por esto
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          PKG: ${{ github.repository_owner }}/packages/container/<app>
        run: |
          echo "=== actual ==="
          gh api "/orgs/$PKG" --jq '.visibility, .version_count' || echo "  (no consultable)"
          echo "=== intento de cambio ==="
          gh api --method PATCH "/orgs/$PKG" -f visibility=public --jq '.visibility' \
            || echo "  PATCH no disponible (limitación del endpoint)"
          echo "=== final ==="
          gh api "/orgs/$PKG" --jq '.visibility' || echo "  (no consultable)"
```

`.version_count` de paso prueba que el paquete **existe**, que es lo que resuelve la
ambigüedad: un token sin permisos recibe `DENIED` tanto si el paquete existe como si no,
así que la API con el token del job es la única lectura confiable.

## 3. Verificación de que el clúster puede bajarla

La prueba que no admite interpretación es el **kubelet**, porque es el mecanismo real:

```bash
kubectl -n <ns> run pull-test --image=ghcr.io/<org>/<app>:<tag> \
  --restart=Never --command -- sleep 20
kubectl -n <ns> get pod pull-test -o jsonpath='{.status.phase} {.status.containerStatuses[0].state}'
kubectl -n <ns> describe pod pull-test | grep -iE 'pull|back-off|error'
kubectl -n <ns> delete pod pull-test
```

`failed to fetch anonymous token: 401 Unauthorized` = el paquete no es público.

Un `curl` anónimo contra `ghcr.io/token?…&scope=repository:…` **no sirve** como sonda: un
paquete público de referencia devuelve lo mismo que uno privado o inexistente. Si se usa
igual, correr siempre un control contra un paquete conocido-público antes de reportar —
una sonda que no distingue el caso bueno del malo no es evidencia.

## 4. Si el paquete debe quedar privado

Hace falta un `imagePullSecret` con un **PAT classic** con `read:packages`:

- **GHCR no acepta fine-grained PATs para pulls.** Verificado end-to-end: el fine-grained
  **obtiene token de registro (200)** y el manifest devuelve **403 DENIED**. **El 200 del
  token es la trampa** — la prueba que vale es pedir el manifest, no obtener el token.
- El PAT classic va a AKV y se materializa con ExternalSecret
  (`type: kubernetes.io/dockerconfigjson`) + `imagePullSecrets` en el pod.
- Es una credencial de vida larga, con vencimiento y rotación manual: usarla solo donde
  hace falta de verdad. Una imagen que **contiene código** no puede ser pública; una de
  **runtime** (PHP + extensiones, sin código ni secretos) sí, y el paquete público ahorra
  el secreto entero.

## 5. Pinning por digest

El build **no es bit-reproducible**: `apt-get install` trae las versiones del día, así que
el mismo commit produce digests distintos entre corridas. Fijar por **digest**
(`@sha256:…`) donde importe la inmutabilidad, no por tag: un cambio de digest es un PR y
el rollback es el digest anterior.

## 6. Higiene

- Con `cache-to: type=gha,mode=max`, una reconstrucción tarda **decenas de segundos** si
  las capas ya están en el registry. Un build corto **no** significa que no construyó
  nada: verificar el digest en el log.
- Los tags `sha-…` se acumulan (cada build suma una versión al paquete). Revisar
  `version_count` y definir retención si crece sin control.
- **Nunca imprimir un token de registro en la salida.** Un `head -c` sobre el JSON del
  token lo filtra; es efímero y de scope `pull`, pero no debe quedar en la conversación.
