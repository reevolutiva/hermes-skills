# Handoff — <tema> (<fecha>)

**Estado:** abierto · **Issue de seguimiento:** <ISSUE> · **Autor:** <quién>

**Objetivo en una línea:** <resultado medible que cierra la tarea>.

## 0. Reglas de ejecución (leer antes de tocar nada)

1. **Cada fase termina en un gate.** Sin el resultado esperado no se avanza, y el resultado se
   registra en el issue.
2. **Todo cambio de clúster va por rama → PR → merge → Flux.** `kubectl` solo lectura/diagnóstico.
3. **Los pasos que son de un humano** (formateo de filesystems, acciones irreversibles, entrega de
   credenciales) van con el comando exacto y su verificación posterior.
4. **Nada de secretos** en Git, comentarios ni informes.
5. **Idioma y commits:** <convención del repo>.

## 1. Contexto (por qué)

<El síntoma medido y la causa de fondo, en 3-5 líneas. Sin narrativa ni cronología.>

## 2. Estado verificado (<fecha>)

<Tablas de medición: nodos, capacidades, montajes, versiones, réplicas. Cada número salió de un
comando corrido en esa sesión.>

| Nodo | Ready | DiskPressure | <métrica> |
|---|---|---|---|
| | | | |

## 3. Alcance

- **W-A ·** <frente de trabajo>
- **W-B ·** <frente de trabajo>

**Fuera de alcance:** <lo que explícitamente no se toca>.

## 4. Gates

### G0 — Baseline antes de tocar (obligatorio, primero)

```bash
<comandos>
```

**Esperado:** <...>. **Guardar la salida en el issue** (es el rollback de referencia).

### G1 — <nombre>

```bash
<comandos>
```

**Esperado:** <...>
**Si falla:** <rollback>

<... un gate por fase, siempre con comando y resultado esperado ...>

## 5. Secuencia con responsables

| # | Paso | Responsable |
|---|---|---|
| 1 | <...> | agente / humano / board |

## 6. Riesgos y rollback

| Riesgo | Mitigación / rollback |
|---|---|
| | |

## 7. Definición de terminado

- [ ] <criterio verificable>

## 8. Arranque de la próxima sesión

> <Bloque listo para pegar: repo y checkout, issue, doc, estado, reglas, accesos, próxima acción
> concreta.>
