# Business Blueprint Skill V1.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve business-blueprint-skill V1 in three ordered increments: generation quality, editing loop quality, and validation quality while preserving the IR-first contract.

**Architecture:** Keep the existing Python-first repository shape and extend the current deterministic pipeline instead of replacing it. Generation remains rule-based, the viewer remains a static HTML workbench, and validation remains machine-readable JSON over the canonical blueprint IR.

**Tech Stack:** Python 3.14+, pytest, static HTML/CSS/JavaScript, standard library only

---

## File Structure

| File | Operation | Responsibility |
|------|-----------|----------------|
| `D:\projects\business-blueprint-skill\business_blueprint\generate.py` | Modify | richer extraction, linkage assembly, and view generation |
| `D:\projects\business-blueprint-skill\business_blueprint\normalize.py` | Modify | normalized term registries and reusable entity matching helpers |
| `D:\projects\business-blueprint-skill\business_blueprint\clarify.py` | Modify | stronger clarify request generation for linkage and coverage gaps |
| `D:\projects\business-blueprint-skill\business_blueprint\viewer.py` | Modify | richer handoff manifest and patch export scaffolding |
| `D:\projects\business-blueprint-skill\business_blueprint\assets\viewer.html` | Modify | edit additional semantic fields and layout hints |
| `D:\projects\business-blueprint-skill\business_blueprint\validate.py` | Modify | cross-view integrity and richer summary fields |
| `D:\projects\business-blueprint-skill\tests\test_generate.py` | Modify | richer generation and view tests |
| `D:\projects\business-blueprint-skill\tests\test_normalize.py` | Modify | registry and matching tests |
| `D:\projects\business-blueprint-skill\tests\test_viewer.py` | Modify | patch and handoff output tests |
| `D:\projects\business-blueprint-skill\tests\test_validate.py` | Modify | new validation rule tests |
| `D:\projects\business-blueprint-skill\tests\test_e2e.py` | Modify | end-to-end v1.1 flow assertions |

---

### Task 1: Improve text extraction and shared-model generation

**Files:**
- Modify: `D:\projects\business-blueprint-skill\business_blueprint\generate.py`
- Modify: `D:\projects\business-blueprint-skill\business_blueprint\normalize.py`
- Modify: `D:\projects\business-blueprint-skill\tests\test_generate.py`
- Modify: `D:\projects\business-blueprint-skill\tests\test_normalize.py`

- [ ] **Step 1: Extend the failing normalize test for known system term normalization**

Write this additional test in `D:\projects\business-blueprint-skill\tests\test_normalize.py`:

```python
from business_blueprint.normalize import normalize_system_name


def test_normalize_system_name_maps_known_aliases() -> None:
    assert normalize_system_name("Salesforce CRM") == "CRM"
    assert normalize_system_name("企微") == "企业微信"
```

- [ ] **Step 2: Extend the failing generation test for actors, flow steps, systems, and views**

Replace `D:\projects\business-blueprint-skill\tests\test_generate.py` with:

```python
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_plan_writes_blueprint_json(tmp_path: Path) -> None:
    source = tmp_path / "brief.txt"
    source.write_text(
        "零售客户需要会员运营，门店导购负责会员注册，客服负责售后跟进，CRM和POS需要支撑订单管理与积分累计。",
        encoding="utf-8",
    )
    output = tmp_path / "solution.blueprint.json"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "business_blueprint.cli",
            "--plan",
            str(output),
            "--from",
            str(source),
            "--industry",
            "retail",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["meta"]["industry"] == "retail"
    assert any(cap["name"] == "会员运营" for cap in payload["library"]["capabilities"])
    assert any(cap["name"] == "订单管理" for cap in payload["library"]["capabilities"])
    assert any(actor["name"] == "门店导购" for actor in payload["library"]["actors"])
    assert any(actor["name"] == "客服" for actor in payload["library"]["actors"])
    assert any(step["name"] == "会员注册" for step in payload["library"]["flowSteps"])
    assert any(system["name"] == "CRM" for system in payload["library"]["systems"])
    assert any(system["name"] == "POS" for system in payload["library"]["systems"])
    view_types = {view["type"] for view in payload["views"]}
    assert "business-capability-map" in view_types
    assert "swimlane-flow" in view_types
    assert "application-architecture" in view_types
```

- [ ] **Step 3: Run the targeted tests to verify they fail**

Run:

```powershell
Set-Location D:\projects\business-blueprint-skill
python -m pytest tests/test_normalize.py tests/test_generate.py -q --basetemp=.tmp\pytest
```

Expected: FAIL because `normalize_system_name` does not exist and generation does not yet emit the richer model.

- [ ] **Step 4: Add minimal normalization registries and helpers**

Update `D:\projects\business-blueprint-skill\business_blueprint\normalize.py` to:

```python
from __future__ import annotations

from typing import Any


KNOWN_SYSTEM_ALIASES = {
    "salesforcecrm": "CRM",
    "salesforce": "CRM",
    "crm": "CRM",
    "pos": "POS",
    "enterprisewechat": "企业微信",
    "企微": "企业微信",
}


def _normalized(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")


def normalize_system_name(raw_name: str) -> str:
    normalized = _normalized(raw_name)
    return KNOWN_SYSTEM_ALIASES.get(normalized, raw_name.strip())


def merge_or_create_system(
    systems: list[dict[str, Any]],
    raw_name: str,
    description: str,
) -> dict[str, Any]:
    canonical_name = normalize_system_name(raw_name)
    normalized_name = _normalized(canonical_name)
    for system in systems:
        aliases = system.get("aliases", [])
        names = [system.get("name", ""), *aliases]
        if any(_normalized(candidate) == normalized_name for candidate in names):
            if raw_name not in aliases and raw_name != system.get("name"):
                system.setdefault("aliases", []).append(raw_name)
            if description and not system.get("description"):
                system["description"] = description
            return system

    created = {
        "id": f"sys-{normalized_name or 'unknown'}",
        "kind": "system",
        "name": canonical_name,
        "aliases": [] if canonical_name == raw_name else [raw_name],
        "description": description,
        "resolution": {"status": "canonical", "canonicalName": canonical_name},
        "capabilityIds": [],
    }
    systems.append(created)
    return created


def mark_ambiguous(entity: dict[str, Any], canonical_name: str) -> dict[str, Any]:
    entity["resolution"] = {
        "status": "ambiguous",
        "canonicalName": canonical_name,
    }
    return entity
```

- [ ] **Step 5: Expand generation with deterministic extraction and full view emission**

Update `D:\projects\business-blueprint-skill\business_blueprint\generate.py` to:

```python
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .clarify import build_clarify_requests
from .model import load_json, new_revision_meta, write_json
from .normalize import merge_or_create_system


ACTOR_RULES = {
    "导购": ("actor-store-guide", "门店导购"),
    "客服": ("actor-service", "客服"),
    "运营": ("actor-ops", "运营"),
}

CAPABILITY_RULES = {
    "会员": ("cap-membership", "会员运营", "管理会员拉新、促活和留存。"),
    "订单": ("cap-order", "订单管理", "管理订单创建、处理和履约。"),
    "门店": ("cap-store-ops", "门店运营", "支撑门店日常经营和导购协作。"),
}

FLOW_RULES = {
    "注册": ("flow-membership-register", "会员注册"),
    "下单": ("flow-order-create", "订单创建"),
    "累计": ("flow-points-accrual", "积分累计"),
    "跟进": ("flow-service-followup", "售后跟进"),
}

SYSTEM_RULES = {
    "CRM": "客户关系管理系统",
    "POS": "门店收银与交易系统",
    "ERP": "企业资源计划系统",
}


def load_seed(repo_root: Path, industry: str) -> dict[str, Any]:
    seed_path = repo_root / "business_blueprint" / "templates" / industry / "seed.json"
    return load_json(seed_path)


def _ensure_actor(blueprint: dict[str, Any], actor_id: str, actor_name: str) -> None:
    if not any(actor["id"] == actor_id for actor in blueprint["library"]["actors"]):
        blueprint["library"]["actors"].append({"id": actor_id, "name": actor_name})


def _ensure_capability(
    blueprint: dict[str, Any],
    capability_id: str,
    capability_name: str,
    description: str,
) -> None:
    if not any(cap["id"] == capability_id for cap in blueprint["library"]["capabilities"]):
        blueprint["library"]["capabilities"].append(
            {
                "id": capability_id,
                "name": capability_name,
                "level": 1,
                "description": description,
                "ownerActorIds": [],
                "supportingSystemIds": [],
            }
        )


def _capability_ids_for_text(source_text: str, blueprint: dict[str, Any]) -> list[str]:
    pairs = []
    for trigger, (capability_id, capability_name, description) in CAPABILITY_RULES.items():
        if trigger in source_text:
            _ensure_capability(blueprint, capability_id, capability_name, description)
            pairs.append(capability_id)
    return pairs


def _infer_actor_id(source_text: str) -> str | None:
    for trigger, (actor_id, actor_name) in ACTOR_RULES.items():
        if trigger in source_text:
            return actor_id
    return None


def create_blueprint_from_text(
    source_text: str,
    industry: str,
    repo_root: Path,
) -> dict[str, Any]:
    blueprint = deepcopy(load_seed(repo_root, industry))
    blueprint["meta"] = {
        "title": "Generated Blueprint",
        "industry": industry,
        **new_revision_meta(parent_revision_id=None, modified_by="ai"),
    }
    blueprint["context"]["sourceRefs"] = [{"type": "inline-text", "excerpt": source_text}]

    for trigger, (actor_id, actor_name) in ACTOR_RULES.items():
        if trigger in source_text:
            _ensure_actor(blueprint, actor_id, actor_name)

    capability_ids = _capability_ids_for_text(source_text, blueprint)

    for trigger, (flow_id, flow_name) in FLOW_RULES.items():
        if trigger in source_text and not any(step["id"] == flow_id for step in blueprint["library"]["flowSteps"]):
            blueprint["library"]["flowSteps"].append(
                {
                    "id": flow_id,
                    "name": flow_name,
                    "actorId": _infer_actor_id(source_text),
                    "capabilityIds": capability_ids[:1] or [],
                    "systemIds": [],
                    "stepType": "task",
                    "inputRefs": [],
                    "outputRefs": [],
                }
            )

    for system_name, description in SYSTEM_RULES.items():
        if system_name in source_text.upper():
            system = merge_or_create_system(
                blueprint["library"]["systems"],
                raw_name=system_name,
                description=description,
            )
            for capability_id in capability_ids:
                if capability_id not in system.setdefault("capabilityIds", []):
                    system["capabilityIds"].append(capability_id)
            system.setdefault("category", "business-app")

    capability_by_id = {cap["id"]: cap for cap in blueprint["library"]["capabilities"]}
    for system in blueprint["library"]["systems"]:
        for capability_id in system.get("capabilityIds", []):
            capability = capability_by_id.get(capability_id)
            if capability and system["id"] not in capability.setdefault("supportingSystemIds", []):
                capability["supportingSystemIds"].append(system["id"])

    blueprint["views"] = [
        {
            "id": "view-capability",
            "type": "business-capability-map",
            "title": "业务能力蓝图",
            "includedNodeIds": [entity["id"] for entity in blueprint["library"]["capabilities"]],
            "includedRelationIds": [],
            "layout": {"groups": []},
            "annotations": [],
        },
        {
            "id": "view-swimlane",
            "type": "swimlane-flow",
            "title": "泳道流程图",
            "includedNodeIds": [
                entity["id"]
                for entity in blueprint["library"]["actors"] + blueprint["library"]["flowSteps"]
            ],
            "includedRelationIds": [],
            "layout": {"lanes": [actor["id"] for actor in blueprint["library"]["actors"]]},
            "annotations": [],
        },
        {
            "id": "view-architecture",
            "type": "application-architecture",
            "title": "应用架构图",
            "includedNodeIds": [
                entity["id"]
                for entity in blueprint["library"]["systems"] + blueprint["library"]["capabilities"]
            ],
            "includedRelationIds": [],
            "layout": {"groups": []},
            "annotations": [],
        },
    ]

    blueprint["context"]["clarifyRequests"] = build_clarify_requests(blueprint)
    return blueprint


def write_plan_output(
    output_path: Path,
    source_text: str,
    industry: str,
    repo_root: Path,
) -> dict[str, Any]:
    blueprint = create_blueprint_from_text(source_text, industry, repo_root)
    write_json(output_path, blueprint)
    return blueprint
```

- [ ] **Step 6: Run the targeted tests to verify they pass**

Run:

```powershell
Set-Location D:\projects\business-blueprint-skill
python -m pytest tests/test_normalize.py tests/test_generate.py -q --basetemp=.tmp\pytest
```

Expected: PASS.

- [ ] **Step 7: Commit the generation-quality slice**

Run:

```powershell
Set-Location D:\projects\business-blueprint-skill
git add business_blueprint\generate.py business_blueprint\normalize.py tests\test_generate.py tests\test_normalize.py
git commit -m "feat: improve blueprint generation coverage"
```

---

### Task 2: Improve viewer editing loop and handoff metadata

**Files:**
- Modify: `D:\projects\business-blueprint-skill\business_blueprint\viewer.py`
- Modify: `D:\projects\business-blueprint-skill\business_blueprint\assets\viewer.html`
- Modify: `D:\projects\business-blueprint-skill\tests\test_viewer.py`

- [ ] **Step 1: Extend the failing viewer test for parent revision and patch file output**

Replace `D:\projects\business-blueprint-skill\tests\test_viewer.py` with:

```python
import json
from pathlib import Path

from business_blueprint.model import write_json
from business_blueprint.viewer import write_viewer_package


def test_write_viewer_package_creates_viewer_handoff_and_patch_seed(tmp_path: Path) -> None:
    blueprint = {
        "version": "1.0",
        "meta": {
            "revisionId": "rev-2",
            "parentRevisionId": "rev-1",
            "lastModifiedBy": "human",
        },
        "context": {},
        "library": {
            "capabilities": [{"id": "cap-membership", "name": "会员运营", "description": "原始描述"}],
            "actors": [],
            "flowSteps": [],
            "systems": [{"id": "sys-crm", "name": "CRM", "description": "原始系统描述"}],
        },
        "relations": [],
        "views": [],
        "editor": {"fieldLocks": {"meta.title": "human"}},
        "artifacts": {},
    }
    blueprint_path = tmp_path / "solution.blueprint.json"
    write_json(blueprint_path, blueprint)

    viewer_path = tmp_path / "solution.viewer.html"
    handoff_path = tmp_path / "solution.handoff.json"
    patch_path = tmp_path / "solution.patch.jsonl"

    write_viewer_package(blueprint_path, viewer_path, handoff_path, patch_path)

    assert viewer_path.exists()
    handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
    assert handoff["revisionId"] == "rev-2"
    assert handoff["parentRevisionId"] == "rev-1"
    assert handoff["lastModifiedBy"] == "human"
    patch_seed = patch_path.read_text(encoding="utf-8").strip().splitlines()
    assert patch_seed
    assert json.loads(patch_seed[0])["op"] == "seed_patch_log"
```

- [ ] **Step 2: Run the viewer test to verify it fails**

Run:

```powershell
Set-Location D:\projects\business-blueprint-skill
python -m pytest tests/test_viewer.py -q --basetemp=.tmp\pytest
```

Expected: FAIL because handoff is missing the new metadata and patch output is empty.

- [ ] **Step 3: Enrich the viewer package writer**

Update `D:\projects\business-blueprint-skill\business_blueprint\viewer.py` to:

```python
from __future__ import annotations

from pathlib import Path
import json

from .model import load_json, write_json


def write_viewer_package(
    blueprint_path: Path,
    viewer_path: Path,
    handoff_path: Path,
    patch_path: Path,
) -> None:
    blueprint = load_json(blueprint_path)
    asset_path = Path(__file__).parent / "assets" / "viewer.html"
    viewer_template = asset_path.read_text(encoding="utf-8")
    rendered = viewer_template.replace(
        "__BLUEPRINT_JSON__",
        json.dumps(blueprint, ensure_ascii=False),
    )
    viewer_path.write_text(rendered, encoding="utf-8")

    meta = blueprint.get("meta", {})
    handoff = {
        "revisionId": meta.get("revisionId"),
        "parentRevisionId": meta.get("parentRevisionId"),
        "lastModifiedBy": meta.get("lastModifiedBy"),
        "blueprintPath": str(blueprint_path),
        "viewerPath": str(viewer_path),
        "patchPath": str(patch_path),
    }
    write_json(handoff_path, handoff)

    seed_entry = {
        "op": "seed_patch_log",
        "revisionId": meta.get("revisionId"),
        "fieldLocks": blueprint.get("editor", {}).get("fieldLocks", {}),
    }
    patch_path.write_text(json.dumps(seed_entry, ensure_ascii=False) + "\n", encoding="utf-8")
```

- [ ] **Step 4: Expand the static viewer editing surface**

Update `D:\projects\business-blueprint-skill\business_blueprint\assets\viewer.html` so it supports:

- title edit
- first capability description edit
- first system description edit
- patch log entries for semantic edits
- field locks for edited semantic fields

Use this script block:

```html
<script>
  const blueprint = __BLUEPRINT_JSON__;
  const patchLog = [];

  function firstCapability() {
    return (blueprint.library?.capabilities || [])[0] || null;
  }

  function firstSystem() {
    return (blueprint.library?.systems || [])[0] || null;
  }

  function ensureLocks() {
    blueprint.editor = blueprint.editor || {};
    blueprint.editor.fieldLocks = blueprint.editor.fieldLocks || {};
  }

  function updateSummary() {
    document.getElementById("revision-id").textContent = blueprint.meta.revisionId || "unknown";
    document.getElementById("dirty-state").textContent = patchLog.length ? "Unsaved edits" : "Saved";
    document.getElementById("json-view").value = JSON.stringify(blueprint, null, 2);
    document.getElementById("capability-description").value = firstCapability()?.description || "";
    document.getElementById("system-description").value = firstSystem()?.description || "";
  }

  function renameTitle() {
    const nextValue = document.getElementById("title-input").value.trim();
    blueprint.meta.title = nextValue || blueprint.meta.title || "Generated Blueprint";
    ensureLocks();
    blueprint.editor.fieldLocks["meta.title"] = "human";
    patchLog.push({ op: "update_meta", fields: { title: blueprint.meta.title } });
    updateSummary();
  }

  function updateCapabilityDescription() {
    const capability = firstCapability();
    if (!capability) return;
    capability.description = document.getElementById("capability-description").value.trim();
    ensureLocks();
    blueprint.editor.fieldLocks[`library.capabilities.${capability.id}.description`] = "human";
    patchLog.push({ op: "update_node", id: capability.id, fields: { description: capability.description } });
    updateSummary();
  }

  function updateSystemDescription() {
    const system = firstSystem();
    if (!system) return;
    system.description = document.getElementById("system-description").value.trim();
    ensureLocks();
    blueprint.editor.fieldLocks[`library.systems.${system.id}.description`] = "human";
    patchLog.push({ op: "update_node", id: system.id, fields: { description: system.description } });
    updateSummary();
  }

  function exportRevision() {
    const blob = new Blob([JSON.stringify(blueprint, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "solution.blueprint.json";
    link.click();
  }

  window.addEventListener("DOMContentLoaded", () => {
    document.getElementById("title-input").value = blueprint.meta.title || "";
    document.getElementById("rename-button").addEventListener("click", renameTitle);
    document.getElementById("capability-button").addEventListener("click", updateCapabilityDescription);
    document.getElementById("system-button").addEventListener("click", updateSystemDescription);
    document.getElementById("save-button").addEventListener("click", exportRevision);
    updateSummary();
  });
</script>
```

Add these controls to the body:

```html
<label for="capability-description">First Capability Description</label>
<textarea id="capability-description"></textarea>
<button id="capability-button" type="button">Apply Capability Description</button>

<label for="system-description">First System Description</label>
<textarea id="system-description"></textarea>
<button id="system-button" type="button">Apply System Description</button>
```

- [ ] **Step 5: Run the viewer test to verify it passes**

Run:

```powershell
Set-Location D:\projects\business-blueprint-skill
python -m pytest tests/test_viewer.py -q --basetemp=.tmp\pytest
```

Expected: PASS.

- [ ] **Step 6: Commit the editing-loop slice**

Run:

```powershell
Set-Location D:\projects\business-blueprint-skill
git add business_blueprint\viewer.py business_blueprint\assets\viewer.html tests\test_viewer.py
git commit -m "feat: enrich viewer handoff and semantic editing loop"
```

---

### Task 3: Improve validation coverage and summary completeness

**Files:**
- Modify: `D:\projects\business-blueprint-skill\business_blueprint\validate.py`
- Modify: `D:\projects\business-blueprint-skill\business_blueprint\clarify.py`
- Modify: `D:\projects\business-blueprint-skill\tests\test_validate.py`
- Modify: `D:\projects\business-blueprint-skill\tests\test_e2e.py`

- [ ] **Step 1: Add failing validation tests for orphan capability and missing actor**

Append these tests to `D:\projects\business-blueprint-skill\tests\test_validate.py`:

```python
from business_blueprint.validate import validate_blueprint


def test_validate_reports_orphan_capability() -> None:
    blueprint = {
        "version": "1.0",
        "meta": {"revisionId": "r1"},
        "context": {},
        "library": {
            "capabilities": [{"id": "cap-membership", "name": "会员运营"}],
            "actors": [],
            "flowSteps": [],
            "systems": [],
        },
        "relations": [],
        "views": [],
        "editor": {},
        "artifacts": {},
    }

    result = validate_blueprint(blueprint)

    assert any(issue["errorCode"] == "ORPHAN_CAPABILITY" for issue in result["issues"])


def test_validate_reports_flow_step_missing_actor() -> None:
    blueprint = {
        "version": "1.0",
        "meta": {"revisionId": "r1"},
        "context": {},
        "library": {
            "capabilities": [{"id": "cap-order", "name": "订单管理"}],
            "actors": [],
            "flowSteps": [
                {
                    "id": "flow-order-create",
                    "name": "订单创建",
                    "capabilityIds": ["cap-order"],
                    "systemIds": [],
                }
            ],
            "systems": [],
        },
        "relations": [],
        "views": [],
        "editor": {},
        "artifacts": {},
    }

    result = validate_blueprint(blueprint)

    assert any(issue["errorCode"] == "FLOW_STEP_MISSING_ACTOR" for issue in result["issues"])
```

- [ ] **Step 2: Strengthen the end-to-end test with coverage expectations**

Replace `D:\projects\business-blueprint-skill\tests\test_e2e.py` with:

```python
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_generate_and_export_end_to_end(tmp_path: Path) -> None:
    source = tmp_path / "brief.txt"
    source.write_text(
        "零售客户需要会员运营，门店导购负责会员注册，客服负责售后跟进，CRM和POS需要支撑订单管理与积分累计。",
        encoding="utf-8",
    )
    blueprint = tmp_path / "solution.blueprint.json"
    viewer = tmp_path / "solution.viewer.html"

    subprocess.run(
        [sys.executable, "-m", "business_blueprint.cli", "--plan", str(blueprint), "--from", str(source), "--industry", "retail"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, "-m", "business_blueprint.cli", "--generate", str(viewer), "--from", str(blueprint)],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, "-m", "business_blueprint.cli", "--export", str(blueprint)],
        cwd=ROOT,
        check=True,
    )

    assert viewer.exists()
    assert (tmp_path / "solution.exports" / "solution.svg").exists()
    validation = subprocess.run(
        [sys.executable, "-m", "business_blueprint.cli", "--validate", str(blueprint)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(validation.stdout)
    assert "summary" in payload
    assert payload["summary"]["capability_to_system_coverage"] >= 0.5
    assert payload["summary"]["shared_capability_count"] >= 1
```

- [ ] **Step 3: Run the validation and end-to-end tests to verify they fail**

Run:

```powershell
Set-Location D:\projects\business-blueprint-skill
python -m pytest tests/test_validate.py tests/test_e2e.py -q --basetemp=.tmp\pytest
```

Expected: FAIL because the new validation rules and summary fields are not implemented yet.

- [ ] **Step 4: Expand validation rules and summary output**

Update `D:\projects\business-blueprint-skill\business_blueprint\validate.py` to:

```python
from __future__ import annotations

from collections import Counter
from typing import Any

from .model import ensure_top_level_shape


def _issue(
    severity: str,
    error_code: str,
    message: str,
    affected_ids: list[str],
    suggested_fix: str,
) -> dict[str, Any]:
    return {
        "severity": severity,
        "errorCode": error_code,
        "message": message,
        "affectedIds": affected_ids,
        "suggestedFix": suggested_fix,
    }


def validate_blueprint(payload: dict[str, Any]) -> dict[str, Any]:
    blueprint = ensure_top_level_shape(payload)
    issues: list[dict[str, Any]] = []

    all_ids: list[str] = []
    for collection in blueprint["library"].values():
        if isinstance(collection, list):
            all_ids.extend(
                item["id"]
                for item in collection
                if isinstance(item, dict) and "id" in item
            )

    duplicates = [item_id for item_id, count in Counter(all_ids).items() if count > 1]
    for item_id in duplicates:
        issues.append(
            _issue(
                "error",
                "DUPLICATE_ID",
                f"Duplicate identifier {item_id}.",
                [item_id],
                "Rename one of the duplicate entities.",
            )
        )

    capabilities = blueprint["library"]["capabilities"]
    capability_ids = {cap["id"] for cap in capabilities if "id" in cap}
    flow_steps = blueprint["library"]["flowSteps"]
    systems = blueprint["library"]["systems"]
    views = blueprint["views"]

    unmapped_flow_steps = [
        step["id"]
        for step in flow_steps
        if not step.get("unmappedAllowed") and not step.get("capabilityIds")
    ]
    for step_id in unmapped_flow_steps:
        issues.append(
            _issue(
                "warning",
                "UNMAPPED_FLOW_STEP",
                f"Flow step {step_id} is not linked to a capability.",
                [step_id],
                "Add capabilityIds or mark the step unmappedAllowed.",
            )
        )

    unmapped_systems = [
        system["id"]
        for system in systems
        if not system.get("supportOnly")
        and system.get("category") != "external"
        and not system.get("capabilityIds")
    ]
    for system_id in unmapped_systems:
        issues.append(
            _issue(
                "warning",
                "UNMAPPED_SYSTEM",
                f"System {system_id} is not linked to any capability.",
                [system_id],
                "Link the system to one or more capabilities or mark it supportOnly.",
            )
        )

    invalid_cap_refs = []
    for step in flow_steps:
        for capability_id in step.get("capabilityIds", []):
            if capability_id not in capability_ids:
                invalid_cap_refs.append((step["id"], capability_id))
    for owner_id, capability_id in invalid_cap_refs:
        issues.append(
            _issue(
                "error",
                "MISSING_CAPABILITY_REFERENCE",
                f"{owner_id} references missing capability {capability_id}.",
                [owner_id, capability_id],
                "Create the capability or remove the bad reference.",
            )
        )

    linked_capability_ids = set()
    for step in flow_steps:
        linked_capability_ids.update(step.get("capabilityIds", []))
        if not step.get("actorId"):
            issues.append(
                _issue(
                    "warning",
                    "FLOW_STEP_MISSING_ACTOR",
                    f"Flow step {step['id']} does not identify an actor.",
                    [step["id"]],
                    "Add actorId for the flow step.",
                )
            )

    for system in systems:
        linked_capability_ids.update(system.get("capabilityIds", []))

    orphan_capabilities = [
        capability["id"] for capability in capabilities if capability["id"] not in linked_capability_ids
    ]
    for capability_id in orphan_capabilities:
        issues.append(
            _issue(
                "warning",
                "ORPHAN_CAPABILITY",
                f"Capability {capability_id} is not linked to any flow step or system.",
                [capability_id],
                "Link the capability to flow steps or supporting systems.",
            )
        )

    capability_map_view = next(
        (view for view in views if view.get("type") == "business-capability-map"),
        None,
    )
    capability_map_ids = set(capability_map_view.get("includedNodeIds", [])) if capability_map_view else set()
    for capability_id in linked_capability_ids:
        if capability_id not in capability_map_ids:
            issues.append(
                _issue(
                    "warning",
                    "CAPABILITY_MISSING_FROM_MAP",
                    f"Capability {capability_id} is used outside the map view but missing from the capability map.",
                    [capability_id],
                    "Include the capability in the business-capability-map view.",
                )
            )

    architecture_capability_ids = {
        capability_id
        for system in systems
        for capability_id in system.get("capabilityIds", [])
    }
    flow_capability_ids = {
        capability_id
        for step in flow_steps
        for capability_id in step.get("capabilityIds", [])
    }
    shared_capability_ids = architecture_capability_ids & flow_capability_ids
    if flow_steps and systems and not shared_capability_ids:
        issues.append(
            _issue(
                "warning",
                "NO_SHARED_CAPABILITY_LINKAGE",
                "Flow and architecture views do not share any capability linkage.",
                [],
                "Link at least one capability across flow steps and systems.",
            )
        )

    summary = {
        "errorCount": sum(1 for issue in issues if issue["severity"] == "error"),
        "warningCount": sum(1 for issue in issues if issue["severity"] == "warning"),
        "infoCount": sum(1 for issue in issues if issue["severity"] == "info"),
        "capability_to_flow_coverage": 0 if not flow_steps else round((len(flow_steps) - len(unmapped_flow_steps)) / len(flow_steps), 2),
        "capability_to_system_coverage": 0 if not systems else round((len(systems) - len(unmapped_systems)) / len(systems), 2),
        "shared_capability_count": len(shared_capability_ids),
        "unmapped_flow_step_ids": unmapped_flow_steps,
        "unmapped_system_ids": unmapped_systems,
    }
    return {"summary": summary, "issues": issues}
```

- [ ] **Step 5: Expand clarify coverage for missing generated flow**

Update `D:\projects\business-blueprint-skill\business_blueprint\clarify.py` so it appends:

```python
    if library.get("capabilities") and not library.get("flowSteps"):
        requests.append(
            {
                "code": "MISSING_MAIN_FLOW",
                "question": "What is the main business flow that should be represented?",
                "affectedIds": [],
            }
        )
```

and keeps `AMBIGUOUS_SYSTEM` requests ahead of missing-field requests.

- [ ] **Step 6: Run the validation and end-to-end tests to verify they pass**

Run:

```powershell
Set-Location D:\projects\business-blueprint-skill
python -m pytest tests/test_validate.py tests/test_e2e.py -q --basetemp=.tmp\pytest
```

Expected: PASS.

- [ ] **Step 7: Run the full suite**

Run:

```powershell
Set-Location D:\projects\business-blueprint-skill
python -m pytest -q --basetemp=.tmp\pytest
```

Expected: PASS with the full suite green.

- [ ] **Step 8: Commit the validation-quality slice**

Run:

```powershell
Set-Location D:\projects\business-blueprint-skill
git add business_blueprint\validate.py business_blueprint\clarify.py tests\test_validate.py tests\test_e2e.py
git commit -m "feat: expand blueprint linkage validation"
```

---

## Self-Review

### Spec coverage

- generation quality is covered by Task 1
- editing loop quality is covered by Task 2
- validation quality is covered by Task 3

### Placeholder scan

No `TODO`, `TBD`, or deferred implementation placeholders remain. Each task includes exact files, test steps, commands, and code to write.

### Type consistency

- `revisionId`, `parentRevisionId`, and `lastModifiedBy` are used consistently across generation, viewer, and validation
- `capabilityIds`, `actorId`, `includedNodeIds`, and `fieldLocks` keep the same names across tasks
- the CLI verification command consistently uses `--basetemp=.tmp\pytest`
