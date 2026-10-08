# Gate Definitions — /ree-learn

Payloads exactos para cada gate Jev, con tipos, instrucciones y criterios.
Sigue el mismo formato que `ree-producto/references/gate-definitions.md`.

---

## Modo Error

### Gate de Clasificación de Fuente (Jev Choice)

```json
{
  "state": "<descripción del error + política violada + skills cargadas + memory actual + approvals.deny activo>",
  "questions": {
    "error_source": {
      "type": "choice",
      "instructions": "What is the root source of this error/discrepancy?",
      "options": [
        "skill_desactualizada",
        "memoria_faltante",
        "regla_config_ausente",
        "discrepancia_user_policy",
        "error_contexto_sesion"
      ]
    }
  }
}
```

Cada opción dispara una acción correctiva distinta (ver SKILL.md Fase 3).

### Gate de Validación de Corrección (Jev Noul)

```json
{
  "state": "<skill/memoria/regla ANTES del cambio>\\n---\\n<skill/memoria/regla DESPUÉS del cambio>\\n---\\n<descripción del error original>",
  "questions": {
    "fix_sufficient": {
      "type": "noul",
      "instructions": "Does the correction fully eliminate the root source of the error such that the same mistake cannot happen again? Consider: (a) is the corrected rule explicit and unambiguous? (b) does it cover the exact scenario that triggered the error? (c) is there any remaining loophole?",
      "criteria": {
        "true": "Correction is sufficient — the error source is eliminated",
        "false": "Correction is insufficient — the same error could still occur"
      }
    }
  }
}
```

- noul ≥ 0.8: corrección suficiente.
- 0.5-0.8: corrección parcial, documentar gap.
- < 0.5: volver a diagnosticar.

### Gate de Coherencia Post-Corrección (Jev Noul)

```json
{
  "state": "<nueva skill/memoria/regla>\\n---\\n<skills y memory existentes relevantes>",
  "questions": {
    "no_new_contradictions": {
      "type": "noul",
      "instructions": "Does the new correction introduce any contradiction with existing policies, skills, or memory entries?",
      "criteria": {
        "true": "No contradictions — the fix is coherent with existing state",
        "false": "The fix contradicts something else — needs reconciliation"
      }
    }
  }
}
```

---

## Modo Aprender

### Gate de Clasificación de Skills (Jev Choice)

```json
{
  "state": "Skill: <nombre y descripción de la skill candidata>\\nRequerimiento: <lo que el usuario pide construir>",
  "questions": {
    "skill_classification": {
      "type": "choice",
      "instructions": "Given this existing skill and the requirement, how should it be classified?",
      "options": ["reuse_as_is", "adapt", "obsolete"]
    }
  }
}
```

### Gate de Detección de Gaps (Jev Noul)

```json
{
  "state": "Requerimiento: <descripción completa del requerimiento>\\nSkills existentes: <lista de skills con sus descripciones>",
  "questions": {
    "has_gap": {
      "type": "noul",
      "instructions": "Does the requirement ask for something no existing skill covers?",
      "criteria": {
        "true": "There is a gap — at least one thing the user needs has no existing skill",
        "false": "No gap — existing skills cover everything"
      }
    }
  }
}
```

- noul ≥ 0.7: crear skill(s) nueva(s) para cubrir el gap.
- < 0.7: reutilizar existentes con adaptación si necesario.

### Gate de Validación de Diseño (Jev Score)

```json
{
  "state": "<Design Spec completo: metodología, proceso, modelo de datos, gates, gestión de contexto, artefactos>",
  "questions": {
    "design_quality": {
      "type": "score",
      "instructions": "How complete and viable is this skill design?",
      "levels": [
        "incompleto — Missing key sections (methodology, process, or gates)",
        "minimo_viable — Core sections present but needs refinement",
        "completo — Well-structured, all sections filled, viable",
        "sobreconstruido — Over-engineered for the requirement"
      ]
    }
  }
}
```

- `incompleto`: volver a Diseñar.
- `minimo_viable` o superior: proceder a Implementar.

### Gate de Description Check (Jev Noul)

```json
{
  "state": "Description: \"<description candidata>\"\\nCriterios: ≤60 chars, una oración, verbo gatillo primero, sin adjetivos de marketing",
  "questions": {
    "description_valid": {
      "type": "noul",
      "instructions": "Does this description meet all the criteria (≤60 chars, trigger-first, one sentence, no marketing adjectives)?",
      "criteria": {
        "true": "Description is valid and meets all criteria",
        "false": "Description fails one or more criteria"
      }
    }
  }
}
```

### Gate de Redundancia (Jev Noul)

```json
{
  "state": "Skill A: <fragmento relevante de SKILL.md>\\n---\\nSkill B: <fragmento relevante de SKILL.md>",
  "questions": {
    "has_overlap": {
      "type": "noul",
      "instructions": "Is there content overlap between these two skills that warrants extraction into a shared transverse skill?",
      "criteria": {
        "true": "Significant overlap — extract shared content",
        "false": "Minimal or no overlap — skills are properly separated"
      }
    }
  }
}
```

### Gate Final de Coherencia (Jev Score)

```json
{
  "state": "<lista completa de skills creadas con una oración de propósito cada una>\\n---\\n<requerimiento original del usuario>",
  "questions": {
    "system_coherence": {
      "type": "score",
      "instructions": "How coherent and complete is this skill system as a whole?",
      "levels": [
        "inconsistente — Serious contradictions between skills or missing pieces",
        "coherencia_parcial — Minor discrepancies; mostly aligned",
        "coherente — Consistent and aligned across all skills",
        "excelente — Production-ready with no gaps or contradictions"
      ]
    }
  }
}
```

### Gate Final de Completitud (Jev Choice)

```json
{
  "state": "<requerimiento original del usuario>\\n---\\n<lista de skills creadas con sus descripciones y entregables>",
  "questions": {
    "completeness": {
      "type": "choice",
      "instructions": "Does the skill set cover everything the user asked for?",
      "options": ["falta_cobertura", "cubre_parcialmente", "cubre_completo"]
    }
  }
}
```

- No `cubre_completo` → volver a Fase 1 (Investigar).

---

## Modo Fallback (sin TYPESAFE_API_KEY)

Sin `TYPESAFE_API_KEY`, el agente evalúa cada gate con razonamiento de Hermes:
1. Misma pregunta que Jev habría evaluado.
2. Decisión marcada `[hermes-judgment]` con nivel de confianza (alta, media, baja).
3. Si confianza baja en decisión crítica → pedir input al usuario.
4. Bitácora registra motor usado en cada gate:

```markdown
| Gate | Motor | Resultado | Confianza |
|------|-------|-----------|-----------|
| Fuente raíz | jev | skill_desactualizada | 0.87 |
| Validación | hermes | noul 0.78 | media |
| Coherencia | hermes | noul 0.91 | alta |
```

---

## Regla de Redacción de Preguntas

- **Preguntar siempre en positivo.** "¿Son coherentes?" → noul alto = bueno.
  "¿Se contradicen?" → noul alto = malo (invierte la lectura del gate).
- **Una pregunta atómica por gate.** Si un gate sale `uncertain` (0.3-0.7),
  lanzar 2-4 sondas atómicas adicionales para localizar la falla.
- **No reescribir el state para que el gate pase.** Si el state es evidencia
  real y Jev devuelve `uncertain`, corregir el artefacto y volver a medir.
- **Gate de comandos citados (solo modo aprender).** Antes del gate final,
  extraer todos los comandos que citan las skills nuevas y validarlos contra
  la ayuda real del CLI (un verbo inventado invalida la guía entera).