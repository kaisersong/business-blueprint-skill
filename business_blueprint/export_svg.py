"""SVG exporter with container-based layout and semantic arrows.

Follows the fireworks-tech-graph pattern:
- layered containers with grid-based component layout
- semantic arrow system (solid/dashed/labelled) with SVG markers
- engineering-style title block
- clean vertical data flow, no crossing arrows
- proper z-ordering: bg → containers → arrows → label bg → nodes → text
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape


# ─── Design tokens ───────────────────────────────────────────────
C = {
    "bg": "#F8FAFC",
    "canvas": "#FFFFFF",
    "border": "#CBD5E1",
    "text_main": "#0F172A",
    "text_sub": "#64748B",
    "layer_header_bg": "#F1F5F9",
    "layer_border": "#E2E8F0",
    "cap_fill": "#E8F5F5",
    "cap_stroke": "#0B6E6E",
    "sys_fill": "#EFF6FF",
    "sys_stroke": "#3B82F6",
    "actor_fill": "#FFF7ED",
    "actor_stroke": "#F97316",
    "flow_fill": "#FEFCE8",
    "flow_stroke": "#CA8A04",
    "arrow": "#0B6E6E",
    "arrow_muted": "#94A3B8",
    "arrow_label": "#475569",
    "arrow_label_bg": "#FFFFFF",
}

FONT = "system-ui, -apple-system, sans-serif"
FONT_MONO = "'JetBrains Mono', 'SF Mono', monospace"

# Layout constants
NODE_W = 150
NODE_H = 44
NODE_RX = {"capability": 8, "system": 4, "actor": 22, "flowStep": 6}
LAYER_PAD = 28
LAYER_HEADER_H = 32
LAYER_GAP = 36
CANVAS_X = 40
CANVAS_PAD_TOP = 110  # room for title block
COL_GAP = 20


def _esc(s: str) -> str:
    return escape(str(s))


# ─── Node rendering ──────────────────────────────────────────────
def _node_svg(nid: str, label: str, x: int, y: int, kind: str) -> str:
    fill, stroke, rx = {
        "capability": (C["cap_fill"], C["cap_stroke"], NODE_RX["capability"]),
        "system": (C["sys_fill"], C["sys_stroke"], NODE_RX["system"]),
        "actor": (C["actor_fill"], C["actor_stroke"], NODE_RX["actor"]),
        "flowStep": (C["flow_fill"], C["flow_stroke"], NODE_RX["flowStep"]),
    }[kind]
    return (
        f'<g class="node node-{kind}" id="{nid}">'
        f'<rect class="node-rect" x="{x}" y="{y}" width="{NODE_W}" height="{NODE_H}" '
        f'rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        f'<text class="node-label" x="{x + NODE_W // 2}" y="{y + NODE_H // 2 + 5}" '
        f'text-anchor="middle" font-size="12.5" fill="{C["text_main"]}" '
        f'font-family="{FONT}" font-weight="500">{_esc(label)}</text>'
        f'</g>'
    )


# ─── Arrow rendering with SVG markers ────────────────────────────
def _arrow_line(x1: int, y1: int, x2: int, y2: int,
                dashed: bool = False, color: str = C["arrow"]) -> str:
    """Draw just the arrow line + marker (no label)."""
    dash = f' stroke-dasharray="5,4"' if dashed else ""
    marker_id = "arrow-solid" if not dashed else "arrow-dashed"
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="{color}" stroke-width="1.5"{dash} '
        f'marker-end="url(#{marker_id})"/>'
    )


def _arrow_label(mx: int, my: int, label: str) -> str:
    """Draw arrow label with background rect for readability."""
    label_w = len(label) * 6 + 12
    return (
        f'<rect x="{mx - label_w // 2}" y="{my - 9}" '
        f'width="{label_w}" height="18" rx="3" '
        f'fill="{C["arrow_label_bg"]}" fill-opacity="0.9"/>'
        f'<text x="{mx}" y="{my + 4}" text-anchor="middle" '
        f'font-size="10" fill="{C["arrow_label"]}" font-family="{FONT}">{_esc(label)}</text>'
    )


def _node_center(n: dict) -> tuple[int, int]:
    return n["x"] + NODE_W // 2, n["y"] + NODE_H // 2


def _edge_point(n: dict, tx: int, ty: int) -> tuple[int, int]:
    """Calculate where the arrow should connect on the node's edge.

    For vertical connections (same column), connect to bottom/top center.
    For diagonal connections, compute the intersection with the node border.
    """
    cx, cy = _node_center(n)
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return cx, cy
    hw, hh = NODE_W / 2, NODE_H / 2
    t = min(hw / abs(dx) if dx else 1e9, hh / abs(dy) if dy else 1e9)
    return int(cx + dx * t), int(cy + dy * t)


# ─── Column-based layout ─────────────────────────────────────────
def _layout_architecture(blueprint: dict[str, Any]) -> dict:
    """Position nodes in columns so arrows flow vertically without crossing.

    Strategy (fireworks-tech-graph pattern):
    1. Layer 0: Systems (top)
    2. Layer 1: Capabilities (middle)
    3. Layer 2: Flow Steps (bottom)
    4. Align columns by capability-support relationship so arrows go straight down.
    """
    lib = blueprint.get("library", {})
    systems = lib.get("systems", [])
    capabilities = lib.get("capabilities", [])
    flow_steps = lib.get("flowSteps", [])
    actors = lib.get("actors", [])

    # Build capability → systems map
    cap_to_systems: dict[str, list[str]] = {c["id"]: [] for c in capabilities}
    for s in systems:
        for cid in s.get("capabilityIds", []):
            if cid in cap_to_systems:
                cap_to_systems[cid].append(s["id"])

    # Build columns: each column = (system, capability it supports)
    # A system can span multiple columns if it supports multiple capabilities
    used_systems: set[str] = set()
    used_caps: set[str] = set()
    columns: list[tuple[str | None, str | None]] = []

    # First pass: pair systems with their capabilities
    for cap in capabilities:
        cid = cap["id"]
        supporting = cap_to_systems.get(cid, [])
        if supporting:
            for sid in supporting:
                columns.append((sid, cid))
                used_systems.add(sid)
                used_caps.add(cid)
        else:
            # Capability with no system support → standalone column
            columns.append((None, cid))
            used_caps.add(cid)

    # Add orphan systems (no capability linkage)
    for s in systems:
        if s["id"] not in used_systems:
            columns.append((s["id"], None))
            used_systems.add(s["id"])

    # Add orphan capabilities
    for c in capabilities:
        if c["id"] not in used_caps:
            columns.append((None, c["id"]))
            used_caps.add(c["id"])

    # Deduplicate columns by system (one column per system, with all its caps)
    # Group by system
    sys_columns: dict[str, list[str | None]] = {}  # sys_id → [cap_ids]
    standalone_caps: list[str] = []
    for sid, cid in columns:
        if sid:
            sys_columns.setdefault(sid, []).append(cid)
        elif cid:
            standalone_caps.append(cid)

    # Build ordered column list
    ordered_columns: list[dict] = []
    for sid in sys_columns:
        ordered_columns.append({"system": sid, "caps": sys_columns[sid]})
    for cid in standalone_caps:
        ordered_columns.append({"system": None, "caps": [cid]})

    n_cols = len(ordered_columns)
    if n_cols == 0:
        return {"nodes": {}, "arrows": [], "layers": [], "width": 500, "height": 300}

    total_w = n_cols * NODE_W + max(0, n_cols - 1) * COL_GAP
    start_x = CANVAS_X + (max(600, total_w) - total_w) // 2 + LAYER_PAD

    nodes: dict[str, dict] = {}
    arrows_list: list[dict] = []

    # ── Vertical layout model ──
    # For each layer:
    #   header_y  = y position of the layer header bar
    #   content_y = header_y + LAYER_HEADER_H + LAYER_PAD  (where nodes go)
    #   border_y  = header_y - LAYER_PAD                    (border wraps header+content)
    #   border_h  = LAYER_HEADER_H + LAYER_PAD*2 + content_h
    # Layers spaced by LAYER_GAP between consecutive content areas
    content_y = CANVAS_PAD_TOP  # first layer content starts here
    header_y = content_y - LAYER_HEADER_H - LAYER_PAD
    layer_configs: list[dict] = []

    # ── Row 0: Systems ──
    if systems:
        for col_idx, col in enumerate(ordered_columns):
            x = start_x + col_idx * (NODE_W + COL_GAP)
            if col["system"]:
                sys_node = next((s for s in systems if s["id"] == col["system"]), None)
                if sys_node:
                    nodes[sys_node["id"]] = {
                        "x": x, "y": content_y,
                        "kind": "system",
                        "label": sys_node.get("name", sys_node["id"]),
                    }
        layer_configs.append({
            "label": "Application Systems",
            "header_y": header_y,
            "content_h": NODE_H,
        })
        # Next layer: advance by content_h + LAYER_GAP
        content_y += NODE_H + LAYER_GAP
        header_y = content_y - LAYER_HEADER_H - LAYER_PAD

    # ── Row 1: Capabilities ──
    if capabilities:
        for col_idx, col in enumerate(ordered_columns):
            x = start_x + col_idx * (NODE_W + COL_GAP)
            for cid in col["caps"]:
                cap_node = next((c for c in capabilities if c["id"] == cid), None)
                if cap_node:
                    nodes[cid] = {
                        "x": x, "y": content_y,
                        "kind": "capability",
                        "label": cap_node.get("name", cid),
                    }
                    # Arrow: system → capability
                    sid = col["system"]
                    if sid and sid in nodes:
                        arrows_list.append({
                            "from": sid, "to": cid, "label": "supports", "dashed": False,
                        })
        layer_configs.append({
            "label": "Business Capabilities",
            "header_y": header_y,
            "content_h": NODE_H,
        })
        content_y += NODE_H + LAYER_GAP
        header_y = content_y - LAYER_HEADER_H - LAYER_PAD

    # ── Row 2: Flow Steps ──
    if flow_steps:
        flow_nodes: list[dict] = list(flow_steps)

        col_flow_count: dict[int, int] = {}

        # Place each flow step in the column of one of its capabilityIds
        cap_col_map: dict[str, int] = {}
        for col_idx, col in enumerate(ordered_columns):
            for cid in col["caps"]:
                if cid:
                    cap_col_map[cid] = col_idx

        for i, fs in enumerate(flow_nodes):
            best_col = i % max(n_cols, 1)
            for cid in fs.get("capabilityIds", []):
                if cid in cap_col_map:
                    best_col = cap_col_map[cid]
                    break
            row_in_col = col_flow_count.get(best_col, 0)
            col_flow_count[best_col] = row_in_col + 1
            x = start_x + best_col * (NODE_W + COL_GAP)
            y = content_y + row_in_col * (NODE_H + 10)
            nodes[fs["id"]] = {
                "x": x, "y": y,
                "kind": "flowStep",
                "label": fs.get("name", fs["id"]),
            }
            # Arrow: capability → flow
            for cid in fs.get("capabilityIds", []):
                if cid in nodes:
                    arrows_list.append({
                        "from": cid, "to": fs["id"], "label": "", "dashed": True,
                    })

        max_flow_rows = max(col_flow_count.values()) if col_flow_count else 1
        flow_content_h = max_flow_rows * NODE_H + max(0, max_flow_rows - 1) * 10
        layer_configs.append({
            "label": "Process Flows",
            "header_y": header_y,
            "content_h": flow_content_h,
        })

    # ── Actors ──
    if actors:
        y_actor = CANVAS_PAD_TOP
        x_actor = start_x + n_cols * (NODE_W + COL_GAP) + COL_GAP
        for a in actors:
            nodes[a["id"]] = {
                "x": x_actor, "y": y_actor,
                "kind": "actor",
                "label": a.get("name", a["id"]),
            }
            y_actor += NODE_H + 12

    # ── Build layer boxes from configs ──
    layers = []
    for lc in layer_configs:
        hy = lc["header_y"]
        ch = lc["content_h"]
        layers.append({
            "label": lc["label"],
            "header_y": hy,
            "y": hy - LAYER_PAD,
            "h": LAYER_HEADER_H + LAYER_PAD * 2 + ch,
        })

    # Calculate height (add room for legend at bottom)
    legend_h = 180  # space for legend
    max_y = max((n["y"] + NODE_H for n in nodes.values()), default=300)
    height = max_y + LAYER_PAD + 40 + legend_h

    # Width: fit all content + padding, accounting for actors if present
    content_max_x = max(
        max((n["x"] + NODE_W for n in nodes.values()), default=0),
        n_cols * (NODE_W + COL_GAP),
    )
    width = max(600, content_max_x + CANVAS_X * 2 + LAYER_PAD * 2)

    return {
        "nodes": nodes,
        "arrows": arrows_list,
        "layers": layers,
        "width": width,
        "height": height,
        "start_x": start_x,
    }


def _layer_svg(label: str, header_y: int, border_y: int, w: int, h: int) -> str:
    """Layer container: header at header_y, border at border_y wrapping header+content."""
    return (
        f'<g class="layer" id="layer-{_esc(label)}">'
        f'<rect class="layer-header" x="{CANVAS_X}" y="{header_y}" width="{w}" height="{LAYER_HEADER_H}" '
        f'rx="6" fill="{C["layer_header_bg"]}"/>'
        f'<rect class="layer-border" x="{CANVAS_X}" y="{border_y}" width="{w}" height="{h}" '
        f'rx="8" fill="none" stroke="{C["layer_border"]}" stroke-width="1"/>'
        f'<text class="layer-label" x="{CANVAS_X + 16}" y="{header_y + LAYER_HEADER_H // 2 + 4}" '
        f'font-size="12" fill="{C["text_sub"]}" font-family="{FONT}" '
        f'font-weight="600" letter-spacing="0.4">{_esc(label)}</text>'
        f'</g>'
    )


def _title_svg(title: str, subtitle: str, w: int) -> str:
    ty = CANVAS_PAD_TOP - 62
    return (
        f'<g class="title-block">'
        f'<rect x="{CANVAS_X}" y="{ty}" width="{w}" height="52" '
        f'rx="6" fill="{C["canvas"]}" stroke="{C["border"]}" stroke-width="1"/>'
        f'<text x="{CANVAS_X + 16}" y="{ty + 24}" '
        f'font-size="16" fill="{C["text_main"]}" font-family="{FONT}" '
        f'font-weight="700">{_esc(title)}</text>'
        f'<text x="{CANVAS_X + 16}" y="{ty + 42}" '
        f'font-size="11" fill="{C["text_sub"]}" font-family="{FONT_MONO}">'
        f'{_esc(subtitle)}</text>'
        f'</g>'
    )


def _legend_svg(x: int, y: int) -> str:
    """Legend showing node types and arrow meanings (fireworks-tech-graph pattern)."""
    items = [
        ("System", C["sys_fill"], C["sys_stroke"], 4),
        ("Capability", C["cap_fill"], C["cap_stroke"], 8),
        ("Flow Step", C["flow_fill"], C["flow_stroke"], 6),
        ("Actor", C["actor_fill"], C["actor_stroke"], 22),
    ]
    legend_total_h = 30 + len(items) * 22 + 4 + 2 * 22 + 8  # items + gap + arrows + padding
    parts = [
        f'<g class="legend" transform="translate({x}, {y})">',
        f'<rect x="0" y="0" width="130" height="{legend_total_h}" '
        f'rx="6" fill="{C["canvas"]}" stroke="{C["border"]}" stroke-width="1" opacity="0.95"/>',
        f'<text x="12" y="20" font-size="10" fill="{C["text_sub"]}" '
        f'font-family="{FONT}" font-weight="600" letter-spacing="0.3">LEGEND</text>',
    ]
    for i, (label, fill, stroke, rx) in enumerate(items):
        ly = 38 + i * 22
        parts.append(
            f'<rect x="12" y="{ly}" width="18" height="14" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1"/>'
            f'<text x="38" y="{ly + 11}" font-size="9.5" fill="{C["text_sub"]}" '
            f'font-family="{FONT}">{label}</text>'
        )
    # Arrow styles
    arrow_y = 38 + len(items) * 22 + 4
    parts.append(
        f'<line x1="12" y1="{arrow_y}" x2="30" y2="{arrow_y}" '
        f'stroke="{C["arrow"]}" stroke-width="1.5" marker-end="url(#arrow-solid)"/>'
        f'<text x="38" y="{arrow_y + 4}" font-size="9.5" fill="{C["text_sub"]}" '
        f'font-family="{FONT}">supports</text>'
    )
    parts.append(
        f'<line x1="12" y1="{arrow_y + 22}" x2="30" y2="{arrow_y + 22}" '
        f'stroke="{C["arrow_muted"]}" stroke-width="1.5" stroke-dasharray="5,4" '
        f'marker-end="url(#arrow-dashed)"/>'
        f'<text x="38" y="{arrow_y + 26}" font-size="9.5" fill="{C["text_sub"]}" '
        f'font-family="{FONT}">flow-to</text>'
    )
    parts.append('</g>')
    return "\n".join(parts)
    ty = CANVAS_PAD_TOP - 62
    return (
        f'<g class="title-block">'
        f'<rect x="{CANVAS_X}" y="{ty}" width="{w}" height="52" '
        f'rx="6" fill="{C["canvas"]}" stroke="{C["border"]}" stroke-width="1"/>'
        f'<text x="{CANVAS_X + 16}" y="{ty + 24}" '
        f'font-size="16" fill="{C["text_main"]}" font-family="{FONT}" '
        f'font-weight="700">{_esc(title)}</text>'
        f'<text x="{CANVAS_X + 16}" y="{ty + 42}" '
        f'font-size="11" fill="{C["text_sub"]}" font-family="{FONT_MONO}">'
        f'{_esc(subtitle)}</text>'
        f'</g>'
    )


# ─── SVG defs (markers) ──────────────────────────────────────────
def _svg_defs() -> str:
    """SVG marker definitions for arrowheads (fireworks-tech-graph pattern)."""
    return (
        '<defs>'
        f'<marker id="arrow-solid" markerWidth="10" markerHeight="8" '
        f'refX="9" refY="4" orient="auto" markerUnits="userSpaceOnUse">'
        f'<polygon points="0 0, 10 4, 0 8" fill="{C["arrow"]}"/>'
        f'</marker>'
        f'<marker id="arrow-dashed" markerWidth="10" markerHeight="8" '
        f'refX="9" refY="4" orient="auto" markerUnits="userSpaceOnUse">'
        f'<polygon points="0 0, 10 4, 0 8" fill="{C["arrow_muted"]}"/>'
        f'</marker>'
        '</defs>'
    )


# ─── Main export ─────────────────────────────────────────────────
def export_svg(blueprint: dict[str, Any], target: Path) -> None:
    title = blueprint.get("meta", {}).get("title", "Business Blueprint")
    industry = blueprint.get("meta", {}).get("industry", "")
    subtitle = f"Industry: {industry}" if industry else "Application Architecture"

    layout = _layout_architecture(blueprint)
    w, h = layout["width"], layout["height"]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'font-family="{FONT}">',
        _svg_defs(),
        f'<rect width="{w}" height="{h}" fill="{C["bg"]}"/>',
        _title_svg(title, subtitle, w),
    ]

    # Layer backgrounds (z-order: behind arrows and nodes)
    for layer in layout["layers"]:
        parts.append(_layer_svg(layer["label"], layer["header_y"], layer["y"], w - CANVAS_X * 2, layer["h"]))

    # Arrows (z-order: behind nodes, above layer backgrounds)
    # Pass 1: draw all lines
    arrow_labels: list[tuple[int, int, str]] = []
    for arrow in layout["arrows"]:
        src = layout["nodes"].get(arrow["from"])
        tgt = layout["nodes"].get(arrow["to"])
        if not src or not tgt:
            continue
        # Skip arrows between different columns that would cross
        start_x = layout.get("start_x", CANVAS_X + LAYER_PAD)
        src_col = (src["x"] - start_x) // (NODE_W + COL_GAP) if COL_GAP else 0
        tgt_col = (tgt["x"] - start_x) // (NODE_W + COL_GAP) if COL_GAP else 0
        if abs(src_col - tgt_col) > 0 and arrow.get("label") == "supports":
            continue
        sx, sy = _node_center(src)
        tx, ty = _node_center(tgt)
        sx, sy = _edge_point(src, tx, ty)
        tx, ty = _edge_point(tgt, sx, sy)
        parts.append(
            _arrow_line(sx, sy, tx, ty,
                        dashed=arrow.get("dashed", False),
                        color=C["arrow"] if not arrow.get("dashed") else C["arrow_muted"])
        )
        if arrow.get("label"):
            mx = (sx + tx) // 2
            my = (sy + ty) // 2
            arrow_labels.append((mx, my, arrow["label"]))

    # Pass 2: draw all labels on top of arrows (background masks the line)
    for mx, my, label in arrow_labels:
        parts.append(_arrow_label(mx, my, label))

    # Nodes (z-order: on top of arrows)
    for nid, n in layout["nodes"].items():
        parts.append(_node_svg(nid, n["label"], n["x"], n["y"], n["kind"]))

    # Legend (bottom-left, fireworks-tech-graph pattern)
    parts.append(_legend_svg(CANVAS_X + 10, h - 180 - 10))

    parts.append("</svg>")
    target.write_text("\n".join(parts), encoding="utf-8")
