---
name: kai-business-blueprint
description: Use when turning presales requirements, meeting notes, or solution materials into editable business capability blueprints, swimlane flows, and application architecture diagrams. Use when generating blueprint JSON, static HTML viewers, or exporting to SVG, draw.io, Excalidraw, or Mermaid formats.
---

# Business Blueprint Skill

Use the Python scripts in this repository as the execution surface.

## Output Directory

All generated files (blueprint JSON, viewers, exports) go into `projects/workspace/` — not the repository root.

```bash
python -m business_blueprint.cli --plan projects/workspace/solution.blueprint.json --from "..."
python -m business_blueprint.cli --export projects/workspace/solution.blueprint.json
```

## Industry Selection

Choose `--industry` from exactly one of: `"common"`, `"finance"`, `"manufacturing"`, `"retail"`. Select the closest match based on the user's domain and materials; do not invent other values.

| Industry | Hints content |
|----------|-------------|
| `common` | No hints — generic domains |
| `finance` | Risk control, credit, compliance, customer profile, etc. |
| `manufacturing` | Production planning, quality, warehouse, supply chain, etc. |
| `retail` | Store operations, membership, POS, order fulfillment, etc. |

## How to Generate a Blueprint

The AI agent is responsible for entity extraction. The Python tool handles JSON writing, visualization, and export.

### Step 1: Read industry hints

Read the seed template at `business_blueprint/templates/{industry}/seed.json` and get the `industryHints.checklist`.

### Step 2: Extract entities from source text

Using the user's source material AND the industry hints checklist, extract:
- **capabilities**: business capability areas (name, description)
- **actors**: roles/people involved (name)
- **flowSteps**: business process steps (name, actorId, capabilityIds, stepType)
- **systems**: IT systems that support capabilities (name, description, capabilityIds)

### Step 3: Write the blueprint JSON

Write the JSON file directly to the output path. Use this schema:

```json
{
  "version": "1.0",
  "meta": {
    "title": "...",
    "industry": "retail",
    "revisionId": "rev-YYYYMMDD-NN",
    "parentRevisionId": null,
    "lastModifiedAt": "ISO8601",
    "lastModifiedBy": "ai"
  },
  "context": {
    "goals": [],
    "scope": [],
    "assumptions": [],
    "constraints": [],
    "sourceRefs": [{"type": "inline-text", "excerpt": "..."}],
    "clarifyRequests": [],
    "clarifications": []
  },
  "library": {
    "capabilities": [
      {"id": "cap-xxx", "name": "...", "level": 1, "description": "...", "ownerActorIds": [], "supportingSystemIds": []}
    ],
    "actors": [
      {"id": "actor-xxx", "name": "..."}
    ],
    "flowSteps": [
      {"id": "flow-xxx", "name": "...", "actorId": "actor-xxx", "capabilityIds": ["cap-xxx"], "systemIds": [], "stepType": "task", "inputRefs": [], "outputRefs": []}
    ],
    "systems": [
      {"id": "sys-xxx", "kind": "system", "name": "...", "aliases": [], "description": "...", "resolution": {"status": "canonical", "canonicalName": "..."}, "capabilityIds": ["cap-xxx"]}
    ]
  },
  "relations": [
    {"id": "rel-xxx", "type": "supports", "from": "sys-xxx", "to": "cap-xxx", "label": "支撑"}
  ],
  "views": [],
  "editor": {"fieldLocks": {}, "theme": "enterprise-default"},
  "artifacts": {}
}
```

### Step 4: Generate visualizations

```bash
python -m business_blueprint.cli --export <blueprint.json>
```

This generates SVG + HTML viewer by default. Use `--format drawio|excalidraw|mermaid` for other formats.

## Workflow Decision Tree

```
User provides raw requirements / meeting notes?
  → AI agent reads hints, extracts entities, writes blueprint JSON
  → Then run --export for visualization

User needs diagram files (SVG, draw.io, etc.)?
  → --export (default: SVG + HTML viewer)

User unsure about blueprint quality?
  → --validate
```

## Commands

| Command | Description |
|---------|-------------|
| `--plan <path> --from <text>` | Generate empty blueprint JSON from source text (AI should prefer writing JSON directly) |
| `--export <path>` | Export SVG + HTML viewer (default), or use `--format` for other formats |
| `--validate <path>` | Validate a blueprint and print JSON results |

## Export Formats

| Format | File | Use Case |
|--------|------|----------|
| `svg` (default) | `solution.exports/solution.svg` + HTML viewer | Quick preview, embedding |
| `drawio` | `solution.exports/solution.drawio` | Editable diagrams |
| `excalidraw` | `solution.exports/solution.excalidraw` | Whiteboard-style diagrams |
| `mermaid` | `solution.exports/solution.mermaid.md` | GitHub-native rendering |

## Collaboration Boundary

This skill produces **semantic intermediate artifacts**. Downstream skills consume them:

- `report-creator` consumes blueprint → assembles reports
- `slide-creator` consumes blueprint → assembles presentations
- Other skills may consume `relations` → generate PlantUML or other diagram syntax
- Downstream skills should **never directly edit** `solution.blueprint.json`

## Sandbox Execution

When running in an isolated Python sandbox (Jupyter, notebook, cloud REPL) that auto-installs dependencies:

1. **The sandbox auto-installs `kai-business-blueprint` from PyPI.** Do NOT try to `pip install -e` or use `sys.path` hacks with `__file__` — `__file__` is undefined in Jupyter.

2. **For `--export` (after blueprint JSON exists):**
   ```python
   from pathlib import Path
   from business_blueprint.model import load_json
   from business_blueprint.export_svg import export_svg_auto
   from business_blueprint.export_html import export_html_viewer

   blueprint_path = Path("solution.blueprint.json")
   blueprint = load_json(blueprint_path)
   export_dir = blueprint_path.with_name("solution.exports")
   export_dir.mkdir(parents=True, exist_ok=True)
   export_svg_auto(blueprint, export_dir / "solution.svg")
   export_html_viewer(blueprint, blueprint_path.with_name("solution.blueprint.html"))
   ```

3. **Prohibited patterns in sandbox:**
   - `__file__` — undefined in Jupyter
   - `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` — will raise NameError
   - `subprocess.run(["business-blueprint", ...])` — sandbox runs Python cells, not shell
   - `os.system()` — same reason

## Architecture Diagram Generation

When user requests an architecture diagram (keywords: "架构图", "architecture diagram", "--export", "diagram"):

1. Read `references/architecture-design-system.md` for the complete design system.
2. Read the appropriate template from `references/architecture-templates/` based on the user's domain:
   - AWS/Serverless/Lambda → `serverless.md`
   - Microservices/Kubernetes/微服务 → `microservices.md`
   - Other → use `serverless.md` as a structural reference
3. Read the blueprint JSON to extract entities and flow steps.
4. Generate a self-contained HTML file with inline SVG following the design system rules.
5. Write the output file to the same directory as the blueprint JSON.

### Generation Rules
- Use dark mode by default (`#020617` bg + 40px grid)
- L→R data flow: Clients(左) → Frontend → Backend → Database(右)
- Map `systems[].category` to semantic colors from the design system
- Map `systems[].properties.type == "aws"` → AWS Region boundary box
- Map `systems[].properties.type == "k8s"` → Kubernetes Cluster boundary box
- Use `flowSteps[].seqIndex` for L→R ordering
- Component sizing: 0-1 cap = small(44px h), 2-4 = medium(80px h), 5+ = large(80px h)
- Z-order: bg → grid → title → region → arrows → nodes → legend → cards → footer
- Component border: `rx="8"`, `stroke-width="2"`
- Region border: `rx="16"`, `stroke-dasharray="8,4"`, `opacity="0.4"`

### Output
- Single HTML file: `{blueprint_stem}.html` alongside the blueprint JSON
- No external dependencies (except Google Fonts CDN for JetBrains Mono)
- Opens in any browser, printable to PDF

## Error Handling

- If `--validate` returns errors: fix structural issues before proceeding to `--export`.
- If `--validate` returns only warnings: proceed but note the warnings in any handoff.
- If Python version < 3.12: the package will refuse to install. Use `python3 -m business_blueprint.cli` with system Python as fallback.
