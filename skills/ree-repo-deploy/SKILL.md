---
name: ree-repo-deploy
category: productivity
version: 1.1.0
description: "Registra proyectos en K3s con Flux y verifica su despliegue."
author: Hermes
license: MIT
metadata:
  hermes:
    tags: [ree-repo, deploy, flux, gitops, kustomization, akv, k3s]
---

# ree-repo-deploy — habilitar un proyecto en K3s

## When to Use

Cuando un servicio ya tiene o necesita un repositorio de código y debe desplegarse mediante Flux en `reevolutiva-infra`.

## Procedure

### 1. Descubrir la topología y las convenciones vigentes

Antes de editar, leer el `AGENTS.md` del checkout operativo, comprobar `git status`, y revisar `clusters/<activo>/flux-system/gotk-sync.yaml`, `clusters/<activo>/apps.yaml`, un workload comparable, `infrastructure/configs/namespaces.yaml` y el `ClusterSecretStore` actual. Usar el manifiesto vigente para nombres, ramas, ubicación y esquema de secretos; documentación histórica y plantillas antiguas pueden estar desactualizadas.

En esta plataforma el clúster activo se declara bajo `clusters/produccion/`; `produccion` y `desarrollo` son clases de nodos dentro de ese clúster, no nombres de clúster separados. Volver a confirmarlo en la fuente operativa antes de asumir que seguirá así.

### 2. Separar desarrollo de despliegue

Mantener separados estos artefactos:

- Repositorio del proyecto: código fuente, pruebas, entorno de desarrollo y CI.
- `reevolutiva-infra/apps/<proyecto>/`: recursos que Flux aplica al clúster.
- `reevolutiva-infra/clusters/<activo>/apps.yaml`: registro de Flux y decisión de ubicación.

Dar de alta en Paperclip/workspaces prepara el entorno de trabajo de una persona o agente; no despliega en K3s. La Kustomization de Flux despliega recursos; no crea el repositorio ni el workspace.

Decidir primero si el proceso debe correr como workload de K3s o como servicio del sistema en `vm-services`. No convertir automáticamente todo proyecto en un Deployment.

### 3. Confirmar imagen, arquitectura y destino

Si se requiere contenedor, identificar quién construye/publica la imagen, acordar tag inmutable o digest y comprobar que el nodo destino puede hacer pull. Preferir multi-arch: el nodo `produccion` es arm64; `vm-services` y `vm-worker` son amd64. El registry interno es la fuente preferida, pero no asumir que el pull entre nodos funciona: probarlo desde la clase destino antes de aceptar el despliegue. Para imagen monomórfica, fijar arquitectura/clase expresamente.

### 4. Declarar el workload en la plataforma

Crear `apps/<proyecto>/kustomization.yaml` y los recursos necesarios: `Deployment` o `HelmRelease`, `Service`, probes, requests/limits y `Ingress` para HTTP(S) interno (`ingressClassName: tailscale`). Agregar PVC solo con plan de tamaño, backup y recuperación. Si se usa Helm, confirmar que el `HelmRepository` existe en `infrastructure/configs/helm-repositories.yaml`.

Reutilizar un namespace apropiado. Si falta, agregarlo a `infrastructure/configs/namespaces.yaml`; no crear namespaces manualmente. Añadir al Kustomization de Flux las dependencias reales: por ejemplo, `infra-configs` para namespace/config, `infra-secrets` para ExternalSecrets, `infra-storage` para PVC, `infra-exposure` para Tailscale y `infra-nodos` para ubicación. Incluir además workloads de los que dependa la aplicación.

### 5. Gestionar secretos fuera de Git

Guardar valores en Azure Key Vault `giorgio` y referenciarlos con `ExternalSecret`. El ClusterSecretStore vigente en los manifiestos consultados se llama `azure-kv`; comprobar el nombre en el checkout actual antes de escribir. Validar que cada `remoteRef.key` exista, sin imprimir valores secretos. Nunca versionar `.env` resuelto, tokens ni contraseñas.

### 6. Registrar Flux y la ubicación

Agregar en `clusters/<activo>/apps.yaml` una Kustomization `apps-<proyecto>` que apunte a `./apps/<proyecto>`, use el `GitRepository/flux-system`, y declare `interval`, `dependsOn`, `prune` y `wait` explícitamente. Ajustar `dependsOn` a las dependencias reales; no copiar ciegamente una lista de otro servicio.

La selección de nodo va en patches de la Kustomization del clúster, no en el manifiesto genérico de la aplicación. Leer las etiquetas y taints actuales. Para el clúster documentado, las clases son `reevolutiva.io/clase: produccion` y `reevolutiva.io/clase: desarrollo`, con tolerations correspondientes a los taints del nodo. Apuntar cada patch al `Deployment` correcto. No fijar una carga por hostname como mecanismo permanente.

### 7. Revisar, integrar y reconciliar

Abrir PR en `reevolutiva-infra`; no hacer cambios permanentes solo con `kubectl` ni escribir directamente en `main`. Antes del PR, ejecutar desde el repo:

```bash
PATH=/usr/bin:/bin:/usr/local/bin:$PATH make lint
```

Tras el merge, Flux sincroniza el `main` remoto. Para acelerar:

```bash
flux reconcile source git flux-system
flux reconcile kustomization apps-<proyecto> -n flux-system
```

### 8. Verificar el servicio real

Verificar la Kustomization, HelmRelease si corresponde, pods y nodo destino, Service/Ingress/PVC y estado de ExternalSecret sin exponer su `.data`. Ejecutar `make health` y probar el endpoint desde el contexto de red esperado; terminar con una transacción funcional completa, no solo un probe `/health`. Para cargas con datos, demostrar backup/restore o el rollback acordado antes de declararlas listas.

## Jev Integration Points

| Punto | Primitivo | Pregunta |
|---|---|---|
| Registro GitOps | `noul` | ¿Los manifiestos siguen las convenciones del checkout operativo? |
| Gate F4 | `noul` | ¿La Kustomization declara ubicación, dependencias, `prune` y `wait` adecuados? |

Sin TYPESAFE_API_KEY, usar `[hermes-judgment]` y registrar el nivel de confianza.

## Pitfalls

- **No mezcles el repo de código con el repo GitOps:** el primero habilita desarrollo; el segundo define recursos y placement. Confundirlos deja CI funcional sin despliegue declarativo o manifiestos que nadie prueba.
- **Comprueba el checkout antes de seguir una plantilla:** los nombres de ClusterSecretStore, paths, arquitectura y topología cambian; las plantillas históricas pueden referirse a `imac27` o a nombres ya retirados.
- **Declara solo dependencias reales en `dependsOn`:** sin la infraestructura necesaria, ESO, storage, Ingress o node selectors pueden quedar sin prerequisitos; dependencias innecesarias pueden bloquear el grafo.
- **Prueba el pull desde el nodo destino:** tener una etiqueta de imagen no demuestra conectividad, credenciales ni compatibilidad de arquitectura.
- **Trata `prune: true` como borrado real:** al retirar la Kustomization se eliminan recursos administrados; planifica datos/PVC y rollback antes de mergear.
- **Mantén todo estado duradero en Git:** Flux reconcilia el estado remoto y puede revertir parches manuales.

## Verification

- El PR de infraestructura contiene recursos bajo `apps/<proyecto>/` y su registro Flux en el clúster activo.
- Namespace, secretos, dependencias y ubicación están declarados; no hay valores secretos en Git.
- `make lint` pasa y, tras merge, la Kustomization y workload están Ready en el nodo esperado.
- Endpoint privado/público responde por el camino aprobado y una prueba funcional completa pasa.
- Backups y rollback de datos están definidos cuando el servicio mantiene estado.