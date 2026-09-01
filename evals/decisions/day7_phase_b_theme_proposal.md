# Day 7 Phase B three-theme proposal

**Status:** Approved by Nicole  
**Proposed:** 2026-08-29  
**Approved:** 2026-09-01  
**Constraint:** Select exactly three portfolio-relevant evidence themes before corpus expansion.

## Selection criteria

Each theme must support a concrete product or implementation decision, remain inside the existing non-clinical decision-support scope, admit credible and reviewable sources, and add a distinct portfolio signal. A source may inform more than one theme, but each record must retain a primary theme and source role. Theme selection does not itself justify effectiveness claims.

## Recommended themes

### Theme 1 — AI conversational agents for mental health and well-being

**Decision scenario:** A health-product team asks whether an AI conversational-agent pilot is justified, for which outcomes and populations, and what uncertainty must be measured.

**Include:** Systematic reviews, meta-analyses, controlled trials, and implementation studies of interactive AI conversational agents reporting mental-health or well-being outcomes; older-adult subgroup evidence must be identified explicitly.

**Exclude:** Autonomous diagnosis or treatment recommendations, medication guidance, non-interactive content tools, vendor marketing, and studies without traceable outcome evidence.

**Current seed:** `li-2023`.

### Theme 2 — Voice assistants and digital social connection for older adults

**Decision scenario:** An aging-services or care team asks whether and how to pilot voice or digital interventions for loneliness and social isolation, separating usability from effectiveness.

**Include:** Older-adult studies and syntheses of voice assistants, virtual interactive agents, and digitally mediated social-connection interventions; loneliness, social isolation, usability, acceptability, access, and adherence must be distinguishable.

**Exclude:** Generic smart-home convenience, non-digital social programs, younger-only evidence without an explicit transferability limitation, and claims that usability alone proves reduced loneliness.

**Current seeds:** `marziali-2024`, `dino-2025`, and `welch-2023-egm` as an evidence-map source.

### Theme 3 — Responsible design and implementation of AI companions

**Decision scenario:** A product or implementation team asks what safeguards, interaction principles, policy context, and human-oversight requirements belong in a bounded AI-companion pilot.

**Include:** Empirical human-factors research, design studies, credible evidence maps, standards, and authoritative policy or public-health guidance covering attachment, escalation, privacy, accessibility, equity, human oversight, and implementation risk. Every record must preserve its source role.

**Exclude:** Treating viewpoints or policy guidance as effectiveness evidence, autonomous clinical advice, persuasive attachment as a success metric, unsupported vendor safety claims, and unrestricted consumer deployment.

**Current seeds:** `loveys-2019`, `who-2025`, and `welch-2023-egm` where its evidence-map role is explicit.

## Cross-theme rules

- Each source has one primary theme, one source role, and explicit decision eligibility.
- Context, design, and evidence-map records may frame decisions but cannot establish intervention effectiveness.
- Older-adult-specific evidence is not inferred from mixed populations.
- Usability, acceptability, loneliness, social isolation, depression, distress, and overall well-being remain separate outcomes.
- Phase B targets 10–20 validated sources per theme and 30–60 total active records; ingestion and provenance controls must exist before activation.

## Approval decision

Nicole approved these three themes unchanged on 2026-09-01. This completes `B-01`; it does not authorize paid-model integration, broad clinical claims, or immediate ingestion without the schema/provenance gate.
