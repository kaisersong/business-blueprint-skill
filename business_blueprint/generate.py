from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .clarify import build_clarify_requests
from .model import load_json, new_revision_meta, write_json
from .normalize import merge_or_create_system


ACTOR_RULES: tuple[tuple[str, str, str], ...] = (
    ("导购", "actor-store-guide", "门店导购"),
    ("客服", "actor-service", "客服"),
    ("运营", "actor-ops", "运营"),
)

CAPABILITY_RULES: tuple[tuple[str, str, str, str], ...] = (
    ("会员", "cap-membership", "会员运营", "管理会员拉新、促活和留存。"),
    ("订单", "cap-order", "订单管理", "管理订单创建、处理和履约。"),
    ("门店", "cap-store-ops", "门店运营", "支撑门店日常经营和导购协作。"),
)

FLOW_RULES: tuple[tuple[str, dict[str, Any]], ...] = (
    (
        "注册",
        {
            "id": "flow-membership-register",
            "name": "会员注册",
            "actorId": "actor-store-guide",
            "capabilityIds": ["cap-membership"],
        },
    ),
    (
        "下单",
        {
            "id": "flow-order-create",
            "name": "订单创建",
            "actorId": "actor-store-guide",
            "capabilityIds": ["cap-order"],
        },
    ),
    (
        "累计",
        {
            "id": "flow-points-accrual",
            "name": "积分累计",
            "actorId": "actor-store-guide",
            "capabilityIds": ["cap-membership"],
        },
    ),
    (
        "跟进",
        {
            "id": "flow-service-followup",
            "name": "售后跟进",
            "actorId": "actor-service",
            "capabilityIds": ["cap-order"],
        },
    ),
)

SYSTEM_RULES: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("CRM", "CRM", "客户关系管理系统", ("cap-membership", "cap-order")),
    ("POS", "POS", "门店收银与交易系统", ("cap-order",)),
    ("ERP", "ERP", "企业资源计划系统", ("cap-store-ops",)),
)


def load_seed(repo_root: Path, industry: str) -> dict[str, Any]:
    seed_path = repo_root / "business_blueprint" / "templates" / industry / "seed.json"
    return load_json(seed_path)


def _contains(source_text: str, trigger: str) -> bool:
    return trigger.casefold() in source_text.casefold()


def _ensure_actor(
    blueprint: dict[str, Any],
    actor_id: str,
    actor_name: str,
) -> dict[str, Any]:
    for actor in blueprint["library"]["actors"]:
        if actor.get("id") == actor_id or actor.get("name") == actor_name:
            return actor
    actor = {"id": actor_id, "name": actor_name}
    blueprint["library"]["actors"].append(actor)
    return actor


def _ensure_capability(
    blueprint: dict[str, Any],
    capability_id: str,
    capability_name: str,
    description: str,
) -> dict[str, Any]:
    for capability in blueprint["library"]["capabilities"]:
        if capability.get("id") == capability_id or capability.get("name") == capability_name:
            capability.setdefault("description", description)
            capability.setdefault("level", 1)
            capability.setdefault("ownerActorIds", [])
            capability.setdefault("supportingSystemIds", [])
            return capability

    capability = {
        "id": capability_id,
        "name": capability_name,
        "level": 1,
        "description": description,
        "ownerActorIds": [],
        "supportingSystemIds": [],
    }
    blueprint["library"]["capabilities"].append(capability)
    return capability


def _populate_actors(blueprint: dict[str, Any], source_text: str) -> None:
    for trigger, actor_id, actor_name in ACTOR_RULES:
        if _contains(source_text, trigger):
            _ensure_actor(blueprint, actor_id, actor_name)


def _populate_capabilities(
    blueprint: dict[str, Any],
    source_text: str,
) -> list[str]:
    matched_capability_ids: list[str] = []
    for trigger, capability_id, capability_name, description in CAPABILITY_RULES:
        if _contains(source_text, trigger):
            _ensure_capability(
                blueprint,
                capability_id,
                capability_name,
                description,
            )
            matched_capability_ids.append(capability_id)
    return matched_capability_ids


def _generated_capability_ids(blueprint: dict[str, Any]) -> set[str]:
    return {
        capability["id"]
        for capability in blueprint["library"]["capabilities"]
        if isinstance(capability, dict) and capability.get("id")
    }


def _infer_actor_id(
    blueprint: dict[str, Any],
    preferred_actor_id: str,
) -> str:
    if any(actor.get("id") == preferred_actor_id for actor in blueprint["library"]["actors"]):
        return preferred_actor_id
    return ""


def _populate_flow_steps(
    blueprint: dict[str, Any],
    source_text: str,
    allowed_capability_ids: set[str],
) -> None:
    for trigger, flow in FLOW_RULES:
        if _contains(source_text, trigger):
            capability_ids = [
                capability_id
                for capability_id in flow["capabilityIds"]
                if capability_id in allowed_capability_ids
            ]
            flow_step = {
                "id": flow["id"],
                "name": flow["name"],
                "actorId": _infer_actor_id(blueprint, flow["actorId"]),
                "capabilityIds": capability_ids,
                "systemIds": [],
                "stepType": "task",
                "inputRefs": [],
                "outputRefs": [],
            }
            if not any(step.get("id") == flow_step["id"] for step in blueprint["library"]["flowSteps"]):
                blueprint["library"]["flowSteps"].append(flow_step)


def _populate_systems(
    blueprint: dict[str, Any],
    source_text: str,
    allowed_capability_ids: set[str],
) -> None:
    for trigger, raw_name, description, supported_capability_ids in SYSTEM_RULES:
        if _contains(source_text, trigger):
            system = merge_or_create_system(
                blueprint["library"]["systems"],
                raw_name=raw_name,
                description=description,
            )
            allowed_capabilities = [
                capability_id
                for capability_id in supported_capability_ids
                if capability_id in allowed_capability_ids
            ]
            system["capabilityIds"] = allowed_capabilities


def _link_system_backlinks(blueprint: dict[str, Any]) -> None:
    capability_by_id = {
        capability["id"]: capability
        for capability in blueprint["library"]["capabilities"]
        if isinstance(capability, dict) and capability.get("id")
    }
    for system in blueprint["library"]["systems"]:
        for capability_id in system.get("capabilityIds", []):
            capability = capability_by_id.get(capability_id)
            if capability is None:
                continue
            supporting_system_ids = capability.setdefault("supportingSystemIds", [])
            if system["id"] not in supporting_system_ids:
                supporting_system_ids.append(system["id"])


def _missing_flow_capability_requests(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    for flow_step in blueprint["library"]["flowSteps"]:
        if flow_step.get("capabilityIds"):
            continue
        requests.append(
            {
                "code": "MISSING_FLOW_CAPABILITY_LINKAGE",
                "question": f"Flow step '{flow_step.get('name', '')}' is missing a capability linkage.",
                "affectedIds": [flow_step["id"]],
            }
        )
    return requests


def _build_views(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    return [
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

    _populate_actors(blueprint, source_text)
    _populate_capabilities(blueprint, source_text)
    generated_capability_ids = _generated_capability_ids(blueprint)
    _populate_flow_steps(blueprint, source_text, generated_capability_ids)
    _populate_systems(blueprint, source_text, generated_capability_ids)
    _link_system_backlinks(blueprint)

    blueprint["views"] = _build_views(blueprint)
    blueprint["context"]["clarifyRequests"] = [
        *build_clarify_requests(blueprint),
        *_missing_flow_capability_requests(blueprint),
    ]
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
