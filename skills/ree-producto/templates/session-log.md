# Template de Registro de Sesión

Este template se copia al inicio de cada sesión de `/ree-producto` y se actualiza después de cada fase.

---

# Bitácora de Sesión — /ree-producto

- **Producto**: {{product.name}}
- **Inicio**: {{session.start_time}}
- **Estado**: {{session.status}}

---

## Intake

```yaml
product:
  name: {{product.name}}
  domain: {{product.domain}}
  stage: {{product.stage}}

target_geography: {{product.target_geography}}

problem:
  statement: {{problem.statement}}
  evidence: {{problem.evidence}}

solution:
  summary: {{solution.summary}}
  platform: {{solution.platform}}

sources:
  folders: {{sources.folders}}
  documents: {{sources.documents}}
  urls: {{sources.urls}}
  notes: {{sources.notes}}

users:
  primary_segments: {{users.primary_segments}}

output:
  base_dir: {{output.base_dir}}
  format: {{output.format}}
  language: {{output.language}}
```

**Gate de Intake**: {{intake_gate_result}} (motor: {{intake_gate_motor}})

---

## Fases Ejecutadas

### Fase 1: Descubrimiento e Investigación de Mercado
- **Timestamp**: {{phase_1.timestamp}}
- **Subskill**: {{phase_1.subskill}}
- **Pre-gate**: noul={{phase_1.pre_noul}}, motor={{phase_1.pre_motor}}, passed={{phase_1.pre_passed}}
- **Post-gate**: score={{phase_1.post_score}} ({{phase_1.post_level}}), motor={{phase_1.post_motor}}
- **Archivos generados**: {{phase_1.files}}
- **Decisiones del usuario**: {{phase_1.decisions}}

### Fase 2: Definición de Usuario y Personas
- **Timestamp**: {{phase_2.timestamp}}
- **Subskill**: {{phase_2.subskill}}
- **Pre-gate**: noul={{phase_2.pre_noul}}, motor={{phase_2.pre_motor}}, passed={{phase_2.pre_passed}}
- **Post-gate**: score={{phase_2.post_score}} ({{phase_2.post_level}}), motor={{phase_2.post_motor}}
- **Archivos generados**: {{phase_2.files}}
- **Decisiones del usuario**: {{phase_2.decisions}}

### Fase 3: Estrategia de Producto
- **Timestamp**: {{phase_3.timestamp}}
- **Subskill**: {{phase_3.subskill}}
- **Pre-gate**: noul={{phase_3.pre_noul}}, motor={{phase_3.pre_motor}}, passed={{phase_3.pre_passed}}
- **Post-gate**: score={{phase_3.post_score}} ({{phase_3.post_level}}), motor={{phase_3.post_motor}}
- **Archivos generados**: {{phase_3.files}}
- **Decisiones del usuario**: {{phase_3.decisions}}

### Fase 4: Especificación del Producto (PRD)
- **Timestamp**: {{phase_4.timestamp}}
- **Subskill**: {{phase_4.subskill}}
- **Pre-gate**: noul={{phase_4.pre_noul}}, motor={{phase_4.pre_motor}}, passed={{phase_4.pre_passed}}
- **Post-gate**: score={{phase_4.post_score}} ({{phase_4.post_level}}), motor={{phase_4.post_motor}}
- **Archivos generados**: {{phase_4.files}}
- **Decisiones del usuario**: {{phase_4.decisions}}

### Fase 5: Diseño Visual y Sistema de Diseño
- **Timestamp**: {{phase_5.timestamp}}
- **Subskill**: {{phase_5.subskill}}
- **Pre-gate**: noul={{phase_5.pre_noul}}, motor={{phase_5.pre_motor}}, passed={{phase_5.pre_passed}}
- **Post-gate**: score={{phase_5.post_score}} ({{phase_5.post_level}}), motor={{phase_5.post_motor}}
- **Archivos generados**: {{phase_5.files}}
- **Decisiones del usuario**: {{phase_5.decisions}}

### Fase 6: Documentación Técnica
- **Timestamp**: {{phase_6.timestamp}}
- **Subskill**: {{phase_6.subskill}}
- **Pre-gate**: noul={{phase_6.pre_noul}}, motor={{phase_6.pre_motor}}, passed={{phase_6.pre_passed}}
- **Post-gate**: score={{phase_6.post_score}} ({{phase_6.post_level}}), motor={{phase_6.post_motor}}
- **Archivos generados**: {{phase_6.files}}
- **Decisiones del usuario**: {{phase_6.decisions}}

### Fase 7: Go-to-Market y Lanzamiento
- **Timestamp**: {{phase_7.timestamp}}
- **Subskill**: {{phase_7.subskill}}
- **Pre-gate**: noul={{phase_7.pre_noul}}, motor={{phase_7.pre_motor}}, passed={{phase_7.pre_passed}}
- **Post-gate**: score={{phase_7.post_score}} ({{phase_7.post_level}}), motor={{phase_7.post_motor}}
- **Archivos generados**: {{phase_7.files}}
- **Decisiones del usuario**: {{phase_7.decisions}}

### Fase 8: Métricas, Analytics y Mejora Continua
- **Timestamp**: {{phase_8.timestamp}}
- **Subskill**: {{phase_8.subskill}}
- **Pre-gate**: noul={{phase_8.pre_noul}}, motor={{phase_8.pre_motor}}, passed={{phase_8.pre_passed}}
- **Post-gate**: score={{phase_8.post_score}} ({{phase_8.post_level}}), motor={{phase_8.post_motor}}
- **Archivos generados**: {{phase_8.files}}
- **Decisiones del usuario**: {{phase_8.decisions}}

---

## Fases Omitidas

<!-- Registrar fases saltadas con motivo -->

---

## Gate Final

- **Resultado**: {{final_gate_score}} ({{final_gate_level}})
- **Motor**: {{final_gate_motor}}

---

## Resumen de Gates

| Gate | Motor | Resultado | Confianza |
|------|-------|-----------|-----------|

---

## Completitud

- **Fases ejecutadas**: {{executed_count}}/8
- **Fases omitidas**: {{skipped_count}}
- **Tiempo total**: {{total_duration}}
- **QA Harness**: {{harness_result}}
