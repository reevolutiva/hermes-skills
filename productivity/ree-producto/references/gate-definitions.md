# Gate Definitions — /ree-producto

Payloads exactos para cada gate Jev, con tipos, instrucciones y criterios.

---

## Gate de Intake (Jev Choice)

```json
{
  "state": "<intake serializado como JSON string>",
  "model": "jev-latest",
  "questions": {
    "intake_completeness": {
      "type": "choice",
      "instructions": "Can the product documentation workflow proceed with this intake?",
      "criteria": {
        "proceed_all_phases": "Intake has all required fields and enough detail for all phases",
        "proceed_with_caveats": "Required fields present but some optional detail missing",
        "incomplete_needs_more": "Missing one or more required fields; cannot proceed"
      }
    }
  }
}
```

Si `incomplete_needs_more` → volver a recolectar campos faltantes.
Si `proceed_with_caveats` → marcar gaps en bitácora y continuar.

---

## Pre-gate por Fase (Jev Noul)

```json
{
  "state": "<contexto: intake + resúmenes de fases previas>",
  "model": "jev-latest",
  "questions": {
    "phase_N_readiness": {
      "type": "noul",
      "instructions": "Is there enough context from the intake and previous phases to execute phase N?",
      "criteria": {
        "true": "Sufficient context — the agent has the inputs it needs",
        "false": "Not enough context — output would be poor or incomplete"
      }
    }
  }
}
```

- noul < 0.6: advertir y preguntar si continuar
- noul >= 0.6: proceder

---

## Post-gate de Calidad (Jev Score)

```json
{
  "state": "<deliverable markdown completo>",
  "model": "jev-latest",
  "questions": {
    "phase_N_quality": {
      "type": "score",
      "instructions": "How complete and actionable is this phase deliverable?",
      "criteria": [
        "insuficiente — Does not cover the basics",
        "mínimo_viable — Covers essentials; needs refinement",
        "bueno — Well-founded and actionable",
        "excelente — Ready for stakeholder review"
      ]
    }
  }
}
```

- `insuficiente`: preguntar si re-ejecutar o aceptar
- `mínimo_viable` o superior: registrar y continuar

---

## Gate Final de Coherencia (Jev Score)

```json
{
  "state": "<resúmenes de entregables de fases ejecutadas>",
  "model": "jev-latest",
  "questions": {
    "cross_phase_coherence": {
      "type": "score",
      "instructions": "Do all phase deliverables form a coherent product documentation set?",
      "criteria": [
        "inconsistente — Serious contradictions between phases",
        "coherencia_parcial — Minor discrepancies; mostly aligned",
        "coherente — Consistent and aligned across all deliverables"
      ]
    }
  }
}
```

- `inconsistente`: identificar fases conflictivas, ofrecer re-ejecución
- `coherencia_parcial` o superior: proceder a QA final

---

## Modo fallback (sin TYPESAFE_API_KEY)

Sin `TYPESAFE_API_KEY`, el agente evalúa cada gate con razonamiento de Hermes:

1. Misma pregunta que Jev habría evaluado
2. Decisión marcada `[hermes-judgment]` con nivel de confianza
3. Si confianza baja en decisión crítica → pedir input al usuario
4. Bitácora registra motor usado en cada gate:

```markdown
| Gate | Motor | Resultado | Confianza |
|------|-------|-----------|-----------|
| Intake | jev | proceed_all_phases | 0.89 |
| Pre-Fase 1 | hermes | noul 0.72 | alta |
| Post-Fase 1 | jev | bueno (score 2.3) | 0.85 |
| Gate Final | hermes | coherente | media |
```
