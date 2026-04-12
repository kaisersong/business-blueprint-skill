# Business Blueprint Skill V1.1 Design

Date: 2026-04-12
Status: Draft for review
Owner: Codex

## Summary

V1 established the repository spine: canonical blueprint JSON, CLI, minimal generation,
static viewer, exporters, validation, and tests. V1.1 should improve the product in the
same architectural direction without changing the collaboration contract.

The contract remains:

- `solution.blueprint.json` is the only source of truth
- the viewer is an editing surface, not the canonical source
- exports are projections, not editable truth
- validation is machine-readable and Python-first

V1.1 will be delivered in three ordered milestones:

1. generation quality
2. editing loop quality
3. validation quality

## Scope

### In Scope

- richer extraction of actors, capabilities, flow steps, and systems from source text
- stronger linkage generation between capabilities, flow steps, and systems
- generation of all three first-release view types from the shared model
- viewer support for editing a larger set of semantic and layout fields
- fuller patch log and handoff metadata written by viewer packaging
- validation for orphan entities, missing actor linkage, missing flow linkage, and view completeness

### Out Of Scope

- LLM-backed extraction
- OCR or diagram import
- direct in-browser filesystem save
- server-backed multi-user editing
- rich freeform layout editing
- industry pack expansion beyond the current common and retail seeds

## Design Goals

### 1. Improve semantic completeness without changing the IR contract

The model shape introduced in V1 is sufficient for the next increment. V1.1 should expand
how much of that model is populated and validated, not replace it.

### 2. Keep the implementation deterministic

The current repository is rule-based and test-driven. V1.1 should stay deterministic so the
full pipeline remains easy to test and safe to run in restricted environments.

### 3. Make human edits survivable across regeneration

V1 introduced field locks and a minimal patch loop. V1.1 should make that collaboration
boundary more explicit by widening what can be edited and what gets traced.

## Milestone 1: Generation Quality

### Problem

The current generator only infers a narrow slice of the model:

- one membership capability
- one actor
- one CRM system
- minimal views

That is enough to prove the pipeline, but not enough to support realistic presales material.

### Changes

The generator should remain rule-based, but expand its extraction pass into four explicit stages:

1. detect candidate actors from role terms such as `导购`, `店员`, `运营`, `客服`
2. detect candidate capabilities from business nouns and fixed phrases such as `会员运营`, `订单管理`, `门店运营`
3. detect candidate systems from product or category terms such as `CRM`, `ERP`, `POS`, `OMS`
4. detect candidate flow steps from verbs and action phrases such as `注册`, `下单`, `积分累计`, `跟进`

### Linkage Rules

Generated entities must be linked with deterministic heuristics:

- flow steps reference one or more capability IDs
- flow steps reference one actor ID when actor evidence exists
- systems reference one or more capability IDs
- capabilities reference supporting system IDs when systems are linked

### View Generation

The generator should emit all three first-release views when enough evidence exists:

- `business-capability-map`
- `swimlane-flow`
- `application-architecture`

Each view must reference canonical entity IDs, not duplicate entity payloads.

### Failure Behavior

If generation cannot produce enough semantic coverage, it must still write a partial blueprint
and populate `context.clarifyRequests` with machine-readable gaps instead of inventing detail.

## Milestone 2: Editing Loop Quality

### Problem

The current viewer can only edit title and export a JSON revision. That proves the save loop,
but it is too thin to support meaningful human correction.

### Changes

The static viewer should support editing a small but high-value field set:

- blueprint title
- capability name and description
- system name and description
- flow step name
- lane or grouping assignment stored in `views[].layout`

### Patch Log

The viewer package writer should emit a fuller patch log shape. The viewer runtime does not need
to become a full merge engine, but its export format should distinguish:

- semantic node updates
- relation additions or removals
- layout moves or grouping changes

### Handoff Manifest

`solution.handoff.json` should include enough data for the next AI pass to reject stale input:

- current `revisionId`
- `parentRevisionId` when present
- `lastModifiedBy`
- canonical blueprint path
- patch log path
- viewer path

### Field Locks

Viewer edits to semantic fields must mark corresponding `editor.fieldLocks` entries so later
regeneration can preserve those fields unless explicitly overwritten.

## Milestone 3: Validation Quality

### Problem

V1 validation only checks duplicates, missing capability references, and unmapped systems or
flow steps. It does not yet enforce enough of the cross-view contract defined in the spec.

### Changes

Validation should add machine-readable rules for:

- orphan capabilities with no flow or system linkage
- flow steps missing `actorId`
- flow steps that appear isolated when links are expected
- key capabilities without supporting systems
- integrations with missing source or target systems
- view references to missing node or relation IDs
- capabilities used in flow or architecture views but absent from the capability map
- lack of shared capabilities across flow and architecture views when both exist

### Output Contract

The JSON output shape stays the same:

- `summary`
- `issues`

But `summary` should grow to include explicit completeness lists as well as ratios:

- `capability_to_flow_coverage`
- `capability_to_system_coverage`
- `shared_capability_count`
- `unmapped_flow_step_ids`
- `unmapped_system_ids`

## File-Level Changes

### `business_blueprint/generate.py`

Expand extraction heuristics, linkage assembly, and view composition.

### `business_blueprint/normalize.py`

Add more alias handling and a small registry of normalized system and actor terms.

### `business_blueprint/clarify.py`

Add gap detection for missing flow, missing architecture coverage, and unresolved linkage holes.

### `business_blueprint/viewer.py`

Enrich handoff manifest output and patch scaffolding.

### `business_blueprint/assets/viewer.html`

Support editing additional semantic fields and layout hints without changing the IR-first boundary.

### `business_blueprint/validate.py`

Add cross-view integrity rules and richer summary output.

### Tests

Add or expand tests for:

- richer text-to-blueprint generation
- capability, actor, flow, and system linkage
- viewer patch and handoff output
- validation of orphan, missing actor, and cross-view coverage failures

## Testing Strategy

V1.1 should continue using deterministic pytest coverage.

Required test layers:

- unit tests for normalize, clarify, and validate helpers
- generation tests for extraction and view emission
- viewer tests for patch and handoff package output
- end-to-end CLI tests covering `--plan`, `--generate`, `--export`, and `--validate`

## Risks And Guardrails

### Risk: heuristic sprawl

If extraction rules become too ad hoc, the generator will be hard to maintain.

Guardrail:

- keep heuristics table-driven where practical
- group rules by entity kind
- test each new extraction rule with explicit fixtures

### Risk: viewer outgrows the source-of-truth boundary

If the viewer starts mutating too much implicit state, it will behave like a hidden editor model.

Guardrail:

- all edits must map back to explicit blueprint fields or layout hints
- exported patch records must remain machine-readable
- no viewer-only semantic state

### Risk: validation becomes noisy

If warnings are too aggressive, users and downstream agents will ignore them.

Guardrail:

- keep issue codes specific
- use `error` only for structural breakage
- use `warning` for incompleteness or weak linkage

## Recommended Next Step

Write a V1.1 implementation plan that preserves the existing repository structure and delivers the
three milestones in order:

1. generation quality
2. editing loop quality
3. validation quality
