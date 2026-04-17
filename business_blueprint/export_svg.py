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
import re as _re
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape


# ─── Design tokens ───────────────────────────────────────────────

# Light theme (default) — warm, professional, matches DESIGN.md
C_LIGHT = {
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

# Dark theme — deep slate with vibrant accent colors
C_DARK = {
    "bg": "#020617",
    "canvas": "#0F172A",
    "border": "#1E293B",
    "text_main": "#E2E8F0",
    "text_sub": "#94A3B8",
    "layer_header_bg": "#0F172A",
    "layer_border": "#1E293B",
    "cap_fill": "#064E3B",
    "cap_stroke": "#34D399",
    "sys_fill": "#1E3A5F",
    "sys_stroke": "#60A5FA",
    "actor_fill": "#451A03",
    "actor_stroke": "#FB923C",
    "flow_fill": "#422006",
    "flow_stroke": "#FBBF24",
    "arrow": "#34D399",
    "arrow_muted": "#6B7280",
    "arrow_label": "#CBD5E1",
    "arrow_label_bg": "#1E293B",
}

# Backward compatibility alias
C = C_LIGHT


def _resolve_theme(name: str = "light") -> dict:
    """Return the color palette for the given theme."""
    return C_DARK if name == "dark" else C_LIGHT


# ─── Semantic colors by system category ──────────────────────────
# Maps system.category to (fill, stroke) for light and dark themes.
# When a system has no category, falls back to sys_fill/sys_stroke.
SYSTEM_CATEGORY_COLORS: dict[str, dict[str, dict[str, str]]] = {
    "frontend": {
        "light": {"fill": "#ECFEFF", "stroke": "#0891B2"},
        "dark": {"fill": "#0E2A3D", "stroke": "#22D3EE"},
    },
    "backend": {
        "light": {"fill": "#ECFDF5", "stroke": "#10B981"},
        "dark": {"fill": "#0E2E1F", "stroke": "#34D399"},
    },
    "database": {
        "light": {"fill": "#F5F3FF", "stroke": "#8B5CF6"},
        "dark": {"fill": "#1E1535", "stroke": "#A78BFA"},
    },
    "message_bus": {
        "light": {"fill": "#F0FDF4", "stroke": "#22C55E"},
        "dark": {"fill": "#0F2518", "stroke": "#4ADE80"},
    },
    "cloud": {
        "light": {"fill": "#FFFBEB", "stroke": "#F59E0B"},
        "dark": {"fill": "#2A2010", "stroke": "#FBBF24"},
    },
    "security": {
        "light": {"fill": "#FFF1F2", "stroke": "#F43F5E"},
        "dark": {"fill": "#2A1018", "stroke": "#FB7185"},
    },
    "external": {
        "light": {"fill": "#F8FAFC", "stroke": "#64748B"},
        "dark": {"fill": "#1A2030", "stroke": "#94A3B8"},
    },
}

# Category alias mapping: maps common category values to canonical keys
CATEGORY_ALIASES: dict[str, str] = {
    "web": "frontend",
    "mobile": "frontend",
    "ui": "frontend",
    "api": "backend",
    "service": "backend",
    "microservice": "backend",
    "storage": "database",
    "infra": "cloud",
    "infrastructure": "cloud",
    "devops": "cloud",
    "auth": "security",
    "third-party": "external",
    "third_party": "external",
    "saas": "external",
}


def _resolve_system_colors(category: str | None, theme: str) -> tuple[str, str]:
    """Get (fill, stroke) for a system node based on its category."""
    canonical = CATEGORY_ALIASES.get(category, category) if category else None
    palette = SYSTEM_CATEGORY_COLORS.get(canonical)
    if palette:
        colors = palette.get(theme, palette.get("light", {}))
        return colors.get("fill", ""), colors.get("stroke", "")
    return "", ""


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
def _node_svg(nid: str, label: str, x: int, y: int, kind: str,
              colors: dict | None = None, fill_override: str | None = None,
              stroke_override: str | None = None) -> str:
    c = colors if colors is not None else C
    kind_defaults = {
        "capability": (c["cap_fill"], c["cap_stroke"], NODE_RX["capability"]),
        "system": (c["sys_fill"], c["sys_stroke"], NODE_RX["system"]),
        "actor": (c["actor_fill"], c["actor_stroke"], NODE_RX["actor"]),
        "flowStep": (c["flow_fill"], c["flow_stroke"], NODE_RX["flowStep"]),
    }
    if fill_override is not None and stroke_override is not None:
        fill, stroke = fill_override, stroke_override
    else:
        fill, stroke, _ = kind_defaults.get(kind, kind_defaults["capability"])
    rx = NODE_RX.get(kind, 8)
    return (
        f'<g class="node node-{kind}" id="{nid}">'
        f'<rect class="node-rect" x="{x}" y="{y}" width="{NODE_W}" height="{NODE_H}" '
        f'rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        f'<text class="node-label" x="{x + NODE_W // 2}" y="{y + NODE_H // 2 + 5}" '
        f'text-anchor="middle" font-size="12.5" fill="{c["text_main"]}" '
        f'font-family="{FONT}" font-weight="500">{_esc(label)}</text>'
        f'</g>'
    )


# ─── Arrow rendering with SVG markers ────────────────────────────
def _arrow_line(x1: int, y1: int, x2: int, y2: int,
                dashed: bool = False, color: str | None = None,
                colors: dict | None = None) -> str:
    """Draw just the arrow line + marker (no label)."""
    c = colors if colors is not None else C
    if color is None:
        color = c["arrow"] if not dashed else c["arrow_muted"]
    dash = f' stroke-dasharray="5,4"' if dashed else ""
    marker_id = "arrow-solid" if not dashed else "arrow-dashed"
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="{color}" stroke-width="1.5"{dash} '
        f'marker-end="url(#{marker_id})"/>'
    )


def _render_arrow_line(sx: int, sy: int, tx: int, ty: int, arrow: dict, colors: dict) -> str:
    """Draw a straight arrow line with proper style and marker for free-flow layout."""
    if arrow.get("dashed"):
        style = f'stroke="{colors["arrow_muted"]}" stroke-width="1.5" stroke-dasharray="4,4" opacity="0.5"'
        marker = "arrow-dashed"
    else:
        style = f'stroke="{colors["arrow"]}" stroke-width="1.5"'
        marker = "arrow-solid"
    return f'<line x1="{sx}" y1="{sy}" x2="{tx}" y2="{ty}" {style} marker-end="url(#{marker})"/>'


def _arrow_label(mx: int, my: int, label: str,
                 colors: dict | None = None) -> str:
    """Draw arrow label with background rect for readability."""
    c = colors if colors is not None else C
    label_w = len(label) * 6 + 12
    return (
        f'<rect x="{mx - label_w // 2}" y="{my - 9}" '
        f'width="{label_w}" height="18" rx="3" '
        f'fill="{c["arrow_label_bg"]}" fill-opacity="0.9"/>'
        f'<text x="{mx}" y="{my + 4}" text-anchor="middle" '
        f'font-size="10" fill="{c["arrow_label"]}" font-family="{FONT}">{_esc(label)}</text>'
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
    # Pass 1: place all nodes with fixed content_y per layer
    # Pass 2: compute border_h from actual content extents
    layer_y = 72  # below title block (y=10, h=52) + 10px gap

    # Phase: layer index for each node
    node_layer: dict[str, int] = {}

    # Layer metadata (filled in pass 2)
    layer_metas: list[dict] = []

    # ── Row 0: Systems ──
    if systems:
        li = len(layer_metas)
        content_y = layer_y + LAYER_HEADER_H + LAYER_PAD
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
                    node_layer[sys_node["id"]] = li
        layer_metas.append({
            "label": "Application Systems",
            "header_y": layer_y,
            "content_y": content_y,
        })
        layer_y = layer_y + LAYER_HEADER_H + LAYER_PAD + NODE_H + LAYER_PAD + LAYER_GAP

    # ── Actors: always placed to the right in 2 columns ──
    if actors:
        first_meta = layer_metas[0] if layer_metas else None
        if first_meta:
            content_y = first_meta["content_y"]
            actor_col_count = 2 if len(actors) > 4 else 1
            actor_gap = 12
            actor_w = NODE_W
            total_actor_w = actor_col_count * actor_w + max(0, actor_col_count - 1) * actor_gap
            x_actor_start = start_x + n_cols * (NODE_W + COL_GAP) + COL_GAP
            y_actor_start = content_y

            for ai, a in enumerate(actors):
                col = ai // actor_col_count
                row = ai % actor_col_count
                nodes[a["id"]] = {
                    "x": int(x_actor_start + row * (actor_w + actor_gap)),
                    "y": y_actor_start + col * (NODE_H + 12),
                    "kind": "actor",
                    "label": a.get("name", a["id"]),
                }
                node_layer[a["id"]] = 0

    # ── Row 1: Capabilities ──
    if capabilities:
        li = len(layer_metas)
        content_y = layer_y + LAYER_HEADER_H + LAYER_PAD
        col_cap_count: dict[int, int] = {}
        for col_idx, col in enumerate(ordered_columns):
            x = start_x + col_idx * (NODE_W + COL_GAP)
            for cid in col["caps"]:
                cap_node = next((c for c in capabilities if c["id"] == cid), None)
                if cap_node:
                    row_in_col = col_cap_count.get(col_idx, 0)
                    col_cap_count[col_idx] = row_in_col + 1
                    nodes[cid] = {
                        "x": x, "y": content_y + row_in_col * (NODE_H + 10),
                        "kind": "capability",
                        "label": cap_node.get("name", cid),
                    }
                    node_layer[cid] = li
                    sid = col["system"]
                    if sid and sid in nodes:
                        arrows_list.append({
                            "from": sid, "to": cid, "label": "supports", "dashed": False,
                        })
        layer_metas.append({
            "label": "Business Capabilities",
            "header_y": layer_y,
            "content_y": content_y,
        })
        max_cap_rows = max(col_cap_count.values(), default=1)
        layer_y = layer_y + LAYER_HEADER_H + LAYER_PAD + max_cap_rows * (NODE_H + 10) + LAYER_GAP

    # ── Row 2: Flow Steps ──
    if flow_steps:
        flow_nodes: list[dict] = list(flow_steps)

        col_flow_count: dict[int, int] = {}
        cap_col_map: dict[str, int] = {}
        for col_idx, col in enumerate(ordered_columns):
            for cid in col["caps"]:
                if cid:
                    cap_col_map[cid] = col_idx

        li = len(layer_metas)
        content_y = layer_y + LAYER_HEADER_H + LAYER_PAD
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
            node_layer[fs["id"]] = li
            for cid in fs.get("capabilityIds", []):
                if cid in nodes:
                    arrows_list.append({
                        "from": cid, "to": fs["id"], "label": "", "dashed": True,
                    })

        layer_metas.append({
            "label": "Process Flows",
            "header_y": layer_y,
            "content_y": content_y,
        })

    # ── Pass 2: compute border_h from actual node extents, reposition nodes ──
    for i, meta in enumerate(layer_metas):
        # Step 2a: compute border_h from current node extents
        content_y = meta["content_y"]
        max_bottom = content_y
        for nid, n in nodes.items():
            if node_layer.get(nid) == i:
                bottom = n["y"] + NODE_H
                if bottom > max_bottom:
                    max_bottom = bottom
        content_h = max_bottom - content_y
        meta["border_h"] = LAYER_HEADER_H + LAYER_PAD + content_h + LAYER_PAD

    # Step 2b: recompute layer positions and reposition all nodes
    current_y = 72
    for i, meta in enumerate(layer_metas):
        meta["border_y"] = current_y
        meta["header_y"] = current_y
        new_content_y = current_y + LAYER_HEADER_H + LAYER_PAD
        # Shift nodes in this layer
        y_delta = new_content_y - meta["content_y"]
        for nid, n in nodes.items():
            if node_layer.get(nid) == i:
                n["y"] += y_delta
        meta["content_y"] = new_content_y
        current_y += meta["border_h"] + LAYER_GAP

    # ── Build layer boxes from layer_metas ──
    layers = []
    for lm in layer_metas:
        layers.append({
            "label": lm["label"],
            "header_y": lm["header_y"],
            "y": lm["border_y"],
            "h": lm["border_h"],
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


def _layer_svg(label: str, header_y: int, border_y: int, w: int, h: int,
               colors: dict | None = None) -> str:
    """Layer: border wraps header + content, header has its own bg color."""
    c = colors if colors is not None else C
    return (
        f'<g class="layer" id="layer-{_esc(label)}">'
        f'<rect class="layer-border" x="{CANVAS_X}" y="{border_y}" width="{w}" height="{h}" '
        f'rx="8" fill="none" stroke="{c["layer_border"]}" stroke-width="1"/>'
        f'<rect class="layer-header" x="{CANVAS_X}" y="{header_y}" width="{w}" height="{LAYER_HEADER_H}" '
        f'fill="{c["layer_header_bg"]}"/>'
        f'<text class="layer-label" x="{CANVAS_X + 16}" y="{header_y + LAYER_HEADER_H // 2 + 4}" '
        f'font-size="12" fill="{c["text_sub"]}" font-family="{FONT}" '
        f'font-weight="600" letter-spacing="0.4">{_esc(label)}</text>'
        f'</g>'
    )


def _title_svg(title: str, subtitle: str, w: int,
               colors: dict | None = None) -> str:
    c = colors if colors is not None else C
    ty = 10
    rect_w = w - CANVAS_X  # rect starts at CANVAS_X, so width = w - CANVAS_X
    return (
        f'<g class="title-block">'
        f'<rect x="{CANVAS_X}" y="{ty}" width="{rect_w}" height="52" '
        f'rx="6" fill="{c["canvas"]}" stroke="{c["border"]}" stroke-width="1"/>'
        f'<text x="{CANVAS_X + 16}" y="{ty + 24}" '
        f'font-size="16" fill="{c["text_main"]}" font-family="{FONT}" '
        f'font-weight="700">{_esc(title)}</text>'
        f'<text x="{CANVAS_X + 16}" y="{ty + 42}" '
        f'font-size="11" fill="{c["text_sub"]}" font-family="{FONT_MONO}">'
        f'{_esc(subtitle)}</text>'
        f'</g>'
    )


def _legend_svg(x: int, y: int, colors: dict | None = None) -> str:
    """Legend showing node types and arrow meanings (fireworks-tech-graph pattern)."""
    c = colors if colors is not None else C
    items = [
        ("系统", c["sys_fill"], c["sys_stroke"], 4),
        ("能力", c["cap_fill"], c["cap_stroke"], 8),
        ("流程步骤", c["flow_fill"], c["flow_stroke"], 6),
        ("角色", c["actor_fill"], c["actor_stroke"], 22),
    ]
    legend_total_h = 30 + len(items) * 22 + 4 + 2 * 22 + 8  # items + gap + arrows + padding
    parts = [
        f'<g class="legend" transform="translate({x}, {y})">',
        f'<rect x="0" y="0" width="130" height="{legend_total_h}" '
        f'rx="6" fill="{c["canvas"]}" stroke="{c["border"]}" stroke-width="1" opacity="0.95"/>',
        f'<text x="12" y="20" font-size="10" fill="{c["text_sub"]}" '
        f'font-family="{FONT}" font-weight="600" letter-spacing="0.3">LEGEND</text>',
    ]
    for i, (label, fill, stroke, rx) in enumerate(items):
        ly = 38 + i * 22
        parts.append(
            f'<rect x="12" y="{ly}" width="18" height="14" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1"/>'
            f'<text x="38" y="{ly + 11}" font-size="9.5" fill="{c["text_sub"]}" '
            f'font-family="{FONT}">{label}</text>'
        )
    # Arrow styles
    arrow_y = 38 + len(items) * 22 + 4
    parts.append(
        f'<line x1="12" y1="{arrow_y}" x2="30" y2="{arrow_y}" '
        f'stroke="{c["arrow"]}" stroke-width="1.5" marker-end="url(#arrow-solid)"/>'
        f'<text x="38" y="{arrow_y + 4}" font-size="9.5" fill="{c["text_sub"]}" '
        f'font-family="{FONT}">supports</text>'
    )
    parts.append(
        f'<line x1="12" y1="{arrow_y + 22}" x2="30" y2="{arrow_y + 22}" '
        f'stroke="{c["arrow_muted"]}" stroke-width="1.5" stroke-dasharray="5,4" '
        f'marker-end="url(#arrow-dashed)"/>'
        f'<text x="38" y="{arrow_y + 26}" font-size="9.5" fill="{c["text_sub"]}" '
        f'font-family="{FONT}">flow-to</text>'
    )
    parts.append('</g>')
    return "\n".join(parts)


# ─── SVG defs (markers) ──────────────────────────────────────────
def _svg_defs(colors: dict | None = None, theme: str = "light") -> str:
    """SVG marker definitions for arrowheads.

    For dark theme, also includes a grid pattern definition.
    """
    c = colors if colors is not None else C
    grid_pattern = ""
    if theme == "dark":
        grid_pattern = (
            f'<pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">'
            f'<path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1E293B" stroke-width="0.5"/>'
            f'</pattern>'
        )
    return (
        '<defs>'
        f'{grid_pattern}'
        f'<marker id="arrow-solid" markerWidth="8" markerHeight="6" '
        f'refX="4" refY="3" orient="auto" markerUnits="userSpaceOnUse">'
        f'<polygon points="0 0, 8 3, 0 6" fill="{c["arrow"]}"/>'
        f'</marker>'
        f'<marker id="arrow-dashed" markerWidth="8" markerHeight="6" '
        f'refX="4" refY="3" orient="auto" markerUnits="userSpaceOnUse">'
        f'<polygon points="0 0, 8 3, 0 6" fill="{c["arrow_muted"]}"/>'
        f'</marker>'
        '</defs>'
    )


# ─── Main export ─────────────────────────────────────────────────
def export_svg(blueprint: dict[str, Any], target: Path, theme: str = "light") -> None:
    """Export architecture diagram to SVG.

    Args:
        blueprint: The canonical blueprint JSON.
        target: Output file path.
        theme: Color theme — "light" (default) or "dark".
    """
    colors = _resolve_theme(theme)
    title = blueprint.get("meta", {}).get("title", "Business Blueprint")
    industry = blueprint.get("meta", {}).get("industry", "")
    subtitle = f"行业：{industry}" if industry else "应用架构"

    layout = _layout_architecture(blueprint)
    w, h = layout["width"], layout["height"]

    # Background: solid for light, grid for dark
    if theme == "dark":
        bg_rect = (
            f'<rect width="{w}" height="{h}" fill="{colors["bg"]}"/>'
            f'<rect width="{w}" height="{h}" fill="url(#grid)"/>'
        )
    else:
        bg_rect = f'<rect width="{w}" height="{h}" fill="{colors["bg"]}"/>'

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" '
        f'font-family="{FONT}">',
        _svg_defs(colors=colors, theme=theme),
        bg_rect,
        _title_svg(title, subtitle, w, colors=colors),
    ]

    # Layer backgrounds (z-order: behind arrows and nodes)
    for layer in layout["layers"]:
        parts.append(_layer_svg(
            layer["label"], layer["header_y"], layer["y"],
            w - CANVAS_X * 2, layer["h"], colors=colors
        ))

    # Build semantic color lookup for systems
    systems_by_id = {}
    for s in blueprint.get("library", {}).get("systems", []):
        systems_by_id[s["id"]] = s

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
                        dashed=arrow.get("dashed", False), colors=colors)
        )
        if arrow.get("label"):
            mx = (sx + tx) // 2
            my = (sy + ty) // 2
            arrow_labels.append((mx, my, arrow["label"]))

    # Pass 2: draw all labels on top of arrows (background masks the line)
    for mx, my, label in arrow_labels:
        parts.append(_arrow_label(mx, my, label, colors=colors))

    # Nodes (z-order: on top of arrows)
    for nid, n in layout["nodes"].items():
        kind = n["kind"]
        # Apply semantic colors for system nodes
        fill_ov, stroke_ov = None, None
        if kind == "system":
            sys_data = systems_by_id.get(nid, {})
            category = sys_data.get("category", "")
            if category:
                fill_ov, stroke_ov = _resolve_system_colors(category, theme)
        parts.append(_node_svg(
            nid, n["label"], n["x"], n["y"], kind,
            colors=colors, fill_override=fill_ov, stroke_override=stroke_ov
        ))

    # Legend (bottom-left, fireworks-tech-graph pattern)
    parts.append(_legend_svg(CANVAS_X + 10, h - 180 - 10, colors=colors))

    # Summary cards (bottom-center)
    lib_summary = blueprint.get("library", {})
    n_systems = len(lib_summary.get("systems", []))
    n_capabilities = len(lib_summary.get("capabilities", []))
    n_actors = len(lib_summary.get("actors", []))
    n_flow_steps = len(lib_summary.get("flowSteps", []))
    systems_with_caps = sum(1 for s in lib_summary.get("systems", []) if s.get("capabilityIds"))
    sys_coverage = f"{int(systems_with_caps / n_systems * 100)}%" if n_systems else "N/A"

    card_y = h - 50
    card_data = [
        ("系统", str(n_systems)),
        ("能力", str(n_capabilities)),
        ("角色", str(n_actors)),
        ("流程", str(n_flow_steps)),
        ("覆盖率", sys_coverage),
    ]
    card_w = 110
    card_h = 38
    total_cards_w = len(card_data) * card_w + (len(card_data) - 1) * 12
    cards_start_x = (w - total_cards_w) / 2
    for ci, (label, value) in enumerate(card_data):
        cx = cards_start_x + ci * (card_w + 12)
        parts.append(
            f'<g class="summary-card">'
            f'<rect x="{cx}" y="{card_y}" width="{card_w}" height="{card_h}" '
            f'rx="6" fill="{colors["canvas"]}" stroke="{colors["border"]}" stroke-width="1"/>'
            f'<text x="{cx + card_w / 2}" y="{card_y + 17}" text-anchor="middle" '
            f'font-size="13" fill="{colors["text_main"]}" font-family="{FONT_MONO}" '
            f'font-weight="700">{value}</text>'
            f'<text x="{cx + card_w / 2}" y="{card_y + 32}" text-anchor="middle" '
            f'font-size="7.5" fill="{colors["text_sub"]}" font-family="{FONT}" '
            f'letter-spacing="0.3">{label}</text>'
            f'</g>'
        )

    parts.append("</svg>")
    target.write_text("\n".join(parts), encoding="utf-8")


# ─── Free-flow L→R layout engine ─────────────────────────────────

# Layout columns for L→R data flow
_FREE_FLOW_COLS = [
    {"label": "Entry", "x": 80, "systems": []},
    {"label": "Frontend/Cloud", "x": 310, "categories": ["cloud", "frontend"]},
    {"label": "Backend/Compute", "x": 530, "categories": ["backend", "message_bus"]},
    {"label": "Database/Storage", "x": 750, "categories": ["database"]},
    {"label": "Support", "x": 750, "categories": ["security", "external"]},
]

# Default row positions
_FREE_FLOW_ROWS = {
    "main": {"y": 230, "h": 80},
    "top": {"y": 130, "h": 44},
    "bottom": {"y": 360, "h": 80},
    "infra": {"y": 480, "h": 80},
}


def _categorize_system(sys_obj: dict) -> str:
    """Determine system category from properties, aliases, or name heuristics."""
    cat = sys_obj.get("category", "").lower()
    if cat:
        return cat
    name = sys_obj.get("name", "").lower()
    # Generic keyword → category heuristics (language-agnostic)
    if any(k in name for k in ("gateway", "cdn", "proxy", "load balancer", "ingress")):
        return "cloud"
    if any(k in name for k in ("database", "db", "sql", "nosql", "storage", "cache",
                                "数据库", "缓存", "存储")):
        return "database"
    if any(k in name for k in ("auth", "identity", "permission", "rbac", "token", "oauth",
                                "认证", "权限", "身份")):
        return "security"
    if any(k in name for k in ("queue", "event", "message", "bus", "kafka", "mq",
                                "队列", "消息", "事件")):
        return "message_bus"
    if any(k in name for k in ("lambda", "function", "compute", "serverless",
                                "计算", "函数")):
        return "backend"
    if any(k in name for k in ("monitor", "logging", "tracing", "metric", "alarm",
                                "监控", "日志", "告警")):
        return "cloud"
    if any(k in name for k in ("deploy", "infra", "pipeline", "ci/cd", "terraform",
                                "部署", "基础设施")):
        return "external"
    props = sys_obj.get("properties", {})
    svc = props.get("service", "").lower()
    if svc:
        # Map known service types to categories
        _SVC_MAP = {
            "serverless": "backend", "compute": "backend",
            "cdn": "cloud", "gateway": "cloud", "proxy": "cloud",
            "database": "database", "cache": "database",
            "auth": "security", "iam": "security",
            "queue": "message_bus", "event": "message_bus",
        }
        for key, mapped in _SVC_MAP.items():
            if key in svc:
                return mapped
    return "backend"


def _get_subtitle(sys_obj: dict) -> list[str]:
    """Extract 2-3 subtitle lines from system properties."""
    props = sys_obj.get("properties", {})
    features = props.get("features", [])
    desc = sys_obj.get("description", "")
    lines: list[str] = []
    if desc:
        # Take first meaningful phrase
        parts = desc.replace("，", ",").replace("、", ",").split(",")
        if parts and parts[0].strip():
            lines.append(parts[0].strip()[:40])
    for f in features[:2]:
        lines.append(str(f)[:18])
    # Truncate long subtitles to prevent overflow (node w≈140px, usable≈110px)
    # CJK ~8px/char, ASCII ~6px/char → max ~14 chars for mixed, ~18 for ASCII
    truncated = []
    for line in lines:
        px = sum(8 if ord(c) > 127 else 6 for c in line)
        if px > 110:
            # Truncate to fit ~110px
            chars = 0
            total_px = 0
            for c in line:
                char_px = 8 if ord(c) > 127 else 6
                if total_px + char_px > 110:
                    break
                chars += 1
                total_px += char_px
            truncated.append(line[:chars] + "…")
        else:
            truncated.append(line)
    return truncated[:3] or [""]


def _layout_layered(blueprint: dict[str, Any]) -> dict[str, Any]:
    """Layout systems by layer field into L→R columns.

    When systems have a ``layer`` field, group them into columns (one column per
    unique layer value).  Layers are ordered by their first appearance in the
    ``systems`` array.  Relations drive the arrows.
    """
    lib = blueprint.get("library", {})
    systems = lib.get("systems", [])
    actors = lib.get("actors", [])
    relations = blueprint.get("relations", [])

    # ── Group systems by layer ──
    layer_order: list[str] = []
    layer_systems: dict[str, list[dict]] = {}
    for s in systems:
        layer = s.get("layer", "")
        if not layer:
            continue
        if layer not in layer_systems:
            layer_order.append(layer)
            layer_systems[layer] = []
        layer_systems[layer].append(s)

    if not layer_order:
        # No layers → fall back to free-flow
        return _layout_free_flow(blueprint)

    # ── Layout constants ──
    NODE_W = 150
    NODE_H_BASE = 60
    NODE_H_FEATURED = 76  # systems with features get taller
    COL_GAP = 60          # horizontal gap between layer columns
    ROW_GAP = 20          # vertical gap between nodes in same column
    PAD_X = 80            # left padding
    PAD_Y = 140           # top padding (below title + summary)
    ACTOR_COL_W = 160     # width reserved for actor entry node

    has_actors = bool(actors)
    col_x_start = PAD_X + (ACTOR_COL_W + COL_GAP) if has_actors else PAD_X

    # ── Layer → category mapping: cycle through distinct categories ──
    _LAYER_CATEGORIES = ["frontend", "cloud", "backend", "message_bus", "database", "security"]
    layer_categories = {
        layer: _LAYER_CATEGORIES[li % len(_LAYER_CATEGORIES)]
        for li, layer in enumerate(layer_order)
    }

    # ── Calculate column widths (max node width in each layer) ──
    col_widths: list[int] = []
    for layer in layer_order:
        max_w = 0
        for s in layer_systems[layer]:
            label = s.get("name", "")
            label_px = sum(8 if ord(c) > 127 else 6 for c in label)
            feats = s.get("features", [])
            w = max(NODE_W, label_px + 24, 120)
            if feats:
                feat_text = " / ".join(feats)
                feat_px = sum(7 if ord(c) > 127 else 5 for c in feat_text)
                w = max(w, feat_px + 20)
                w = min(w, 220)  # cap
            max_w = max(max_w, w)
        col_widths.append(max_w)

    # ── Place nodes ──
    nodes: dict[str, dict] = {}

    # Actor entry node
    if has_actors:
        actor_names = [a.get("name", "User") for a in actors]
        if len(actor_names) > 1:
            clients_label = " / ".join(actor_names[:2]) + ("..." if len(actor_names) > 2 else "")
        else:
            clients_label = actor_names[0]
        label_px = sum(8 if ord(c) > 127 else 6 for c in clients_label)
        label_w = min(max(140, label_px + 24), 200)
        nodes["clients"] = {
            "x": PAD_X, "y": PAD_Y + 60, "w": label_w, "h": 80,
            "label": clients_label,
            "category": "external",
            "subtitles": [a.get("name", "") for a in actors[:3]],
            "sys": {"id": "clients", "name": clients_label},
        }

    # Systems per layer column
    x_cursor = col_x_start
    for li, layer in enumerate(layer_order):
        col_w = col_widths[li]
        y_cursor = PAD_Y
        for si, s in enumerate(layer_systems[layer]):
            sid = s["id"]
            feats = s.get("features", [])
            h = NODE_H_FEATURED if feats else NODE_H_BASE
            # Adjust height for features text
            if feats:
                needed = 14 + 8 + min(len(feats), 3) * 13
                h = max(h, needed)

            nodes[sid] = {
                "x": x_cursor, "y": y_cursor, "w": col_w, "h": h,
                "label": s.get("name", sid),
                "category": layer_categories[layer],
                "subtitles": feats[:3] if feats else [],
                "sys": s,
                "layer": layer,
            }
            y_cursor += h + ROW_GAP
        x_cursor += col_w + COL_GAP

    # ── Build arrows from relations ──
    arrows: list[dict] = []
    seen_pairs: set[tuple[str, str]] = set()

    def _add_arrow(from_id: str, to_id: str, label: str, dashed: bool) -> None:
        key = (from_id, to_id)
        if key in seen_pairs:
            return
        seen_pairs.add(key)
        if from_id in nodes and to_id in nodes:
            arrows.append({"from": from_id, "to": to_id, "dashed": dashed, "label": label})

    for rel in relations:
        src_id = rel.get("from", "")
        tgt_id = rel.get("to", "")
        rel_type = rel.get("type", "data")
        label = rel.get("label", "")
        dashed = rel_type in ("support", "uses")
        _add_arrow(src_id, tgt_id, label, dashed)

    # Actor → first layer systems
    if has_actors:
        first_layer = layer_order[0] if layer_order else ""
        for s in layer_systems.get(first_layer, []):
            _add_arrow("clients", s["id"], "", False)

    # ── Calculate canvas ──
    if nodes:
        max_x = max(n["x"] + n["w"] for n in nodes.values())
        max_y = max(n["y"] + n["h"] for n in nodes.values())
        min_y = min(n["y"] for n in nodes.values())
    else:
        max_x, max_y, min_y = 400, 300, 100

    canvas_w = max_x + 120
    canvas_h = max_y - min_y + 160

    return {
        "nodes": nodes,
        "arrows": arrows,
        "width": canvas_w,
        "height": canvas_h,
        "min_y": min_y,
        "layer_order": layer_order,
        "layer_columns": {
            layer: col_widths[li]
            for li, layer in enumerate(layer_order)
        },
    }


def _layout_free_flow(blueprint: dict[str, Any]) -> dict[str, Any]:
    """Layout systems in L→R data flow columns.

    Strategy: place main flow systems on a horizontal center row,
    then scatter supporting systems across different columns above/below
    their related main flow position (not all stacked in one column).

    Row layout:
      y=130: support row — security, cloud, messaging above main
      y=230: main flow — primary data flow chain left-to-right
      y=360: data row — databases and auxiliary systems below main
      y=460: infra row — deployment and infrastructure at bottom
    """
    lib = blueprint.get("library", {})
    systems = lib.get("systems", [])
    flow_steps = lib.get("flowSteps", [])
    actors = lib.get("actors", [])

    systems_by_id = {s["id"]: s for s in systems}
    steps_by_id = {s["id"]: s for s in flow_steps}

    # ── Step 1: Find the main flow chain ──
    process_groups: dict[str, list[dict]] = {}
    for step in flow_steps:
        proc = step.get("processName", "default")
        process_groups.setdefault(proc, []).append(step)
    main_chain_steps = max(process_groups.values(), key=len) if process_groups else []
    main_chain_steps.sort(key=lambda s: s.get("seqIndex", 0))

    main_flow_sys_ids: set[str] = set()
    for step in main_chain_steps:
        for sid in step.get("systemIds", []):
            main_flow_sys_ids.add(sid)

    # ── Step 2: Build main flow order (unique systems, preserving seqIndex order) ──
    main_flow_ordered: list[str] = []
    seen_main: set[str] = set()
    for step in main_chain_steps:
        for sid in step.get("systemIds", []):
            if sid not in seen_main:
                main_flow_ordered.append(sid)
                seen_main.add(sid)

    # ── Step 4: Define layout positions ──
    has_actors = bool(actors)
    MAIN_COLS = [80, 310, 500, 720, 930, 1150]

    # Row Y positions — generic row semantics (not AWS-specific)
    ROW_SUPPORT = 130   # supporting systems above main (auth, security, messaging)
    MAIN_Y = 230        # main data flow
    ROW_DATA = 360      # data/auxiliary layer below main
    ROW_INFRA = 460     # infrastructure at bottom

    nodes: dict[str, dict] = {}

    # Helper: node height from capabilities and subtitle content
    def node_h(s: dict) -> int:
        caps = len(s.get("capabilityIds", []))
        base_h = 80 if caps >= 2 else 60
        # Ensure height fits subtitle content (title 14px + gap 8 + subs 14px each)
        subs = _get_subtitle(s)
        needed_h = 14 + 8 + len(subs) * 14
        return max(base_h, needed_h)

    def node_w(s: dict) -> int:
        caps = len(s.get("capabilityIds", []))
        return 160 if caps >= 5 else 150 if caps >= 2 else 140

    # ── Step 4b: Create entry node if blueprint has actors ──
    if has_actors:
        actor_names = [a.get("name", "Client") for a in actors]
        if len(actor_names) > 1:
            clients_label = " / ".join(actor_names[:2]) + ("..." if len(actor_names) > 2 else "")
        else:
            clients_label = actor_names[0]
        # Auto-size width to fit label, capped to avoid overlap with next column
        label_px = sum(8 if ord(c) > 127 else 6 for c in clients_label)
        label_w = min(max(140, label_px + 24), 200)
        nodes["clients"] = {
            "x": 80, "y": MAIN_Y, "w": label_w, "h": 80,
            "label": clients_label,
            "category": "external",
            "subtitles": [a.get("name", "") for a in actors[:2]],
            "sys": {"id": "clients", "name": clients_label},
        }

    # ── Step 5: Place main flow systems on center row ──
    # If there are actors, shift main flow right by 1 column
    col_offset = 1 if has_actors else 0
    main_col_idx = col_offset
    main_sys_positions: dict[str, int] = {}  # sys_id → column index for related alignment

    for sid in main_flow_ordered:
        s = systems_by_id[sid]
        col_x = MAIN_COLS[main_col_idx] if main_col_idx < len(MAIN_COLS) else 310 + main_col_idx * 220
        main_sys_positions[sid] = main_col_idx
        nodes[sid] = {
            "x": col_x, "y": MAIN_Y, "w": node_w(s), "h": node_h(s),
            "label": s["name"],
            "category": _categorize_system(s),
            "subtitles": _get_subtitle(s),
            "sys": s,
        }
        main_col_idx += 1

    # Center-align all main flow nodes: compute max height, adjust y so centers match
    if main_flow_ordered:
        max_h = max(nodes[sid]["h"] for sid in main_flow_ordered)
        target_center = MAIN_Y + max_h // 2
        for sid in main_flow_ordered:
            n = nodes[sid]
            n["y"] = target_center - n["h"] // 2

    # ── Step 6: Place non-main-flow systems by category ──
    # Generic category → row mapping (no hardcoded product keywords).
    # _categorize_system() determines category from system properties.
    # Row placement: security/cloud/messaging above main, data below, infra at bottom.
    for s in systems:
        sid = s["id"]
        if sid in nodes:
            continue

        cat = _categorize_system(s)
        rel_col = _find_related_column_idx(sid, systems_by_id, steps_by_id, main_flow_ordered, main_sys_positions)
        col_x = MAIN_COLS[min(rel_col, len(MAIN_COLS) - 1)]

        if cat in ("security", "cloud", "message_bus"):
            row_y = ROW_SUPPORT
        elif cat in ("database",):
            row_y = ROW_DATA
        elif cat in ("frontend",):
            row_y = ROW_SUPPORT
        else:
            row_y = ROW_DATA

        nodes[sid] = {
            "x": col_x, "y": row_y, "w": node_w(s), "h": node_h(s),
            "label": s["name"],
            "category": cat,
            "subtitles": _get_subtitle(s),
            "sys": s,
        }

    # ── Step 7: Resolve overlaps — grid-based push-down ──
    # Group nodes by approximate column (x position), then ensure vertical gaps
    COL_BUCKET = 80  # group nodes within 80px x-range as same column
    col_buckets: dict[int, list[str]] = {}
    for sid, n in nodes.items():
        bucket = round(n["x"] / COL_BUCKET)
        col_buckets.setdefault(bucket, []).append(sid)

    MIN_V_GAP = 16  # minimum vertical gap between nodes in same column
    for bucket, sids in col_buckets.items():
        sids.sort(key=lambda sid: nodes[sid]["y"])
        for i in range(1, len(sids)):
            prev = nodes[sids[i - 1]]
            curr = nodes[sids[i]]
            prev_bottom = prev["y"] + prev["h"]
            required_y = prev_bottom + MIN_V_GAP
            if curr["y"] < required_y:
                curr["y"] = required_y

    # ── Step 7b: Horizontal alignment — align nodes in same row to common center ──
    ROW_BUCKET = 40  # group nodes within 40px y-range as same row
    row_buckets: dict[int, list[str]] = {}
    for sid, n in nodes.items():
        bucket = round(n["y"] / ROW_BUCKET)
        row_buckets.setdefault(bucket, []).append(sid)

    for bucket, sids in row_buckets.items():
        if len(sids) <= 1:
            continue
        # Align vertical centers of all nodes in this row
        max_h = max(nodes[sid]["h"] for sid in sids)
        target_center = min(nodes[sid]["y"] + nodes[sid]["h"] // 2 for sid in sids)
        # Use the center of the tallest node as the anchor
        for sid in sids:
            n = nodes[sid]
            n["y"] = target_center - n["h"] // 2

    # ── Step 8: Build arrows from flowSteps ──
    arrows: list[dict] = []
    for step in flow_steps:
        for next_id in step.get("nextStepIds", []):
            next_step = steps_by_id.get(next_id)
            if not next_step:
                continue
            src_ids = step.get("systemIds", [])
            tgt_ids = next_step.get("systemIds", [])
            for src_sid in src_ids:
                for tgt_sid in tgt_ids:
                    if src_sid in nodes and tgt_sid in nodes and src_sid != tgt_sid:
                        arrows.append({"from": src_sid, "to": tgt_sid, "dashed": False, "label": step.get("name", "")})

    # Add synthetic Clients → first main flow system arrow
    if has_actors and main_flow_ordered:
        first_main_sid = main_flow_ordered[0]
        # If first system is an auth-type placed in AUTH_Y, arrow to it
        # Otherwise arrow to the first main flow system on MAIN_Y
        arrows.append({"from": "clients", "to": first_main_sid, "dashed": False, "label": ""})

    # Deduplicate arrows
    seen_pairs: set[tuple[str, str]] = set()
    unique_arrows = []
    for a in arrows:
        key = (a["from"], a["to"])
        if key not in seen_pairs:
            seen_pairs.add(key)
            unique_arrows.append(a)
    arrows = unique_arrows

    # ── Step 9b: Add dashed support arrows from non-main-flow to main flow ──
    # Generic: link auxiliary systems to their related main-flow systems
    # based on shared capabilities and flow step associations
    for s in systems:
        sid = s["id"]
        if sid in main_sys_positions:
            continue  # skip main flow systems
        if sid not in nodes:
            continue
        # Find main flow systems sharing at least one capability
        linked = False
        for cap_id in s.get("capabilityIds", []):
            for main_sid in main_flow_ordered:
                ms = systems_by_id.get(main_sid)
                if ms and cap_id in ms.get("capabilityIds", []):
                    arrows.append({"from": sid, "to": main_sid, "dashed": True, "label": ""})
                    linked = True
        if not linked:
            # Find via flow step co-participation
            for step in flow_steps:
                if sid in step.get("systemIds", []):
                    for main_sid in step.get("systemIds", []):
                        if main_sid in main_sys_positions and main_sid != sid:
                            arrows.append({"from": sid, "to": main_sid, "dashed": True, "label": ""})
                            linked = True
                            break
                if linked:
                    break
        if not linked:
            # Last resort: connect to nearest main flow system
            n = nodes[sid]
            best_sid = min(main_flow_ordered, key=lambda ms: abs(nodes[ms]["x"] - n["x"])) if main_flow_ordered else None
            if best_sid and best_sid in nodes:
                arrows.append({"from": sid, "to": best_sid, "dashed": True, "label": ""})

    # ── Step 9: Calculate canvas size ──
    if nodes:
        max_x = max(n["x"] + n["w"] for n in nodes.values())
        max_y = max(n["y"] + n["h"] for n in nodes.values())
        min_y = min(n["y"] for n in nodes.values())
    else:
        max_x, max_y, min_y = 400, 300, 100
    canvas_w = max_x + 120  # extra padding
    canvas_h = max_y - min_y + 140  # extra bottom padding for legend + footer

    return {
        "nodes": nodes,
        "arrows": arrows,
        "width": canvas_w,
        "height": canvas_h,
        "min_y": min_y,
    }


def _find_related_column_idx(
    sid: str,
    systems_by_id: dict[str, dict],
    steps_by_id: dict[str, dict],
    main_flow_ordered: list[str],
    main_sys_positions: dict[str, int],
) -> int:
    """Find the main flow column index most related to a supporting system."""
    # Find which flow steps reference this system
    for step in steps_by_id.values():
        if sid in step.get("systemIds", []):
            # Check next steps for main flow systems
            for next_id in step.get("nextStepIds", []):
                next_step = steps_by_id.get(next_id)
                if next_step:
                    for main_sid in next_step.get("systemIds", []):
                        if main_sid in main_sys_positions:
                            return main_sys_positions[main_sid]
            # Check previous steps
            for other_step in steps_by_id.values():
                for next_id in other_step.get("nextStepIds", []):
                    if next_id in steps_by_id and sid in steps_by_id[next_id].get("systemIds", []):
                        for main_sid in other_step.get("systemIds", []):
                            if main_sid in main_sys_positions:
                                return main_sys_positions[main_sid]
            # If in same step as main flow systems, use those
            for main_sid in step.get("systemIds", []):
                if main_sid in main_sys_positions:
                    return main_sys_positions[main_sid]
    # Fallback: check which capabilities this system supports,
    # then find flow steps using those capabilities
    sys_caps = set(systems_by_id[sid].get("capabilityIds", []))
    if sys_caps:
        for step in steps_by_id.values():
            if sys_caps & set(step.get("capabilityIds", [])):
                for main_sid in step.get("systemIds", []):
                    if main_sid in main_sys_positions:
                        return main_sys_positions[main_sid]
    # Default to column 2 (middle)
    return 2


def _check_layout_quality(layout: dict[str, Any], blueprint: dict[str, Any]) -> list[str]:
    """Run quality checks on the layout and return a list of issues."""
    issues: list[str] = []
    nodes = layout["nodes"]
    systems = blueprint.get("library", {}).get("systems", [])
    actors = blueprint.get("library", {}).get("actors", [])

    # 1. All systems have nodes
    sys_ids = {s["id"] for s in systems}
    node_ids = set(nodes.keys())
    missing = sys_ids - node_ids
    if missing:
        issues.append(f"Missing nodes for systems: {', '.join(missing)}")

    # 1b. Entry node: if blueprint has actors, should have an entry node
    if actors and not any("client" in sid.lower() or "entry" in sid.lower() for sid in node_ids):
        issues.append("No entry node despite having actors in blueprint")

    # 2. Overlap check — include vertical proximity
    node_list = list(nodes.items())
    for i, (sid_a, a) in enumerate(node_list):
        for sid_b, b in node_list[i + 1:]:
            a_right = a["x"] + a["w"]
            a_bottom = a["y"] + a["h"]
            b_right = b["x"] + b["w"]
            b_bottom = b["y"] + b["h"]
            # Check if rectangles overlap or are too close (< 10px gap)
            h_overlap = not (a_right + 10 < b["x"] or b_right + 10 < a["x"])
            v_overlap = not (a_bottom + 10 < b["y"] or b_bottom + 10 < a["y"])
            if h_overlap and v_overlap:
                issues.append(f"Nodes too close: {sid_a} and {sid_b}")

    # 3. Text overflow check
    for sid, n in nodes.items():
        label = n.get("label", "")
        # Estimate: CJK ~8px, ASCII ~6px
        label_px = sum(8 if ord(c) > 127 else 6 for c in label)
        if label_px > n["w"] * 0.85:
            issues.append(f"Label tight: {sid} '{label}' (~{label_px}px) in width={n['w']}px")
        for i_sub, sub in enumerate(n.get("subtitles", [])):
            sub_px = sum(8 if ord(c) > 127 else 5 for c in sub)
            if sub_px > n["w"] * 0.9:
                issues.append(f"Subtitle tight: {sid} line {i_sub} '{sub}' (~{sub_px}px) in width={n['w']}px")

    # 4. Title coverage check
    title_bottom = 62
    for sid, n in nodes.items():
        if n["y"] < title_bottom + 10:
            issues.append(f"Node {sid} near title: y={n['y']} < {title_bottom + 10}")

    # 5. Canvas size
    if layout["width"] < 1000:
        issues.append(f"Canvas too narrow: {layout['width']}px < 1000px")

    # 6. Arrow completeness
    flow_steps = blueprint.get("library", {}).get("flowSteps", [])
    expected = 0
    actual_pairs = {(a["from"], a["to"]) for a in layout["arrows"]}
    steps_by_id = {s["id"]: s for s in flow_steps}
    for step in flow_steps:
        for next_id in step.get("nextStepIds", []):
            src_ids = step.get("systemIds", [])
            tgt_ids = steps_by_id.get(next_id, {}).get("systemIds", [])
            for sid in src_ids:
                for tid in tgt_ids:
                    if sid != tid:
                        expected += 1
    actual_count = len(actual_pairs)
    if actual_count < expected:
        issues.append(f"Missing arrows: {actual_count} actual vs {expected} expected")

    # 7. Same-column stacking check — only flag if nodes in same column are on same row
    col_stacks: dict[int, list[tuple[str, int, int]]] = {}
    for sid, n in nodes.items():
        col_stacks.setdefault(n["x"], []).append((sid, n["y"], n["h"]))
    for col_x, stack in col_stacks.items():
        stack.sort(key=lambda x: x[1])  # sort by y
        for i, (sid_a, y_a, h_a) in enumerate(stack):
            for sid_b, y_b, h_b in stack[i + 1:]:
                # If vertically adjacent nodes are < 30px apart, flag it
                gap = y_b - (y_a + h_a)
                if 0 < gap < 8:
                    issues.append(f"Column {col_x}: {sid_a} and {sid_b} overlap (gap={gap}px)")

    return issues


def _render_free_flow_svg(
    layout: dict[str, Any],
    title: str,
    subtitle: str,
    theme: str = "dark",
    blueprint: dict[str, Any] | None = None,
) -> str:
    """Render a free-flow layout dict into an SVG string."""
    if blueprint is None:
        blueprint = {}
    colors = _resolve_theme(theme)
    nodes = layout["nodes"]
    arrows = layout["arrows"]
    w, h = layout["width"], layout["height"]
    min_y = layout.get("min_y", 0)
    y_offset = -min_y + 95  # shift everything down so top nodes clear title (y=62) with padding

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" font-family="{FONT}">',
        _svg_defs(colors=colors, theme=theme),
    ]

    # Background
    if theme == "dark":
        parts.append(f'<rect width="{w}" height="{h}" fill="{colors["bg"]}"/>')
        parts.append(f'<rect width="{w}" height="{h}" fill="url(#grid)"/>')
    else:
        parts.append(f'<rect width="{w}" height="{h}" fill="{colors["bg"]}"/>')

    # Title
    parts.append(_title_svg(title, subtitle, w, colors=colors))

    # Layer column headers (if present)
    layer_order = layout.get("layer_order", [])
    if layer_order:
        for layer in layer_order:
            layer_nodes = [n for n in nodes.values() if n.get("layer") == layer]
            if not layer_nodes:
                continue
            lx = min(n["x"] for n in layer_nodes)
            ly = min(n["y"] for n in layer_nodes) + y_offset - 20
            lw = max(n["x"] + n["w"] for n in layer_nodes) - lx
            parts.append(
                f'<text x="{lx + lw // 2}" y="{ly}" text-anchor="middle" '
                f'font-size="11" fill="{colors["text_sub"]}" font-weight="600" '
                f'letter-spacing="0.3">{_esc(layer)}</text>'
            )

    # Detect boundary box for non-external systems
    inner_nodes = [n for n in nodes.values() if n.get("category") != "external"]
    region_rect_idx = None
    if inner_nodes:
        min_x = min(n["x"] for n in inner_nodes) - 40
        region_min_y = max(min(n["y"] for n in inner_nodes) - 30 + y_offset, 72)
        max_x = max(n["x"] + n["w"] for n in inner_nodes) + 40
        region_max_y = max(n["y"] + n["h"] for n in inner_nodes) + 60 + y_offset
        region_rect_idx = len(parts)
        parts.append(
            f'<rect x="{min_x}" y="{region_min_y}" width="{max_x-min_x}" height="{region_max_y-region_min_y}" '
            f'rx="16" fill="none" stroke="#F59E0B" stroke-width="1.5" '
            f'stroke-dasharray="8,4" opacity="0.4"/>'
        )
        # Generic region label
        region_label = "系统边界"
        parts.append(
            f'<text x="{min_x+20}" y="{max(region_min_y - 10, 85)}" font-size="12" '
            f'fill="#F59E0B" font-weight="600">{region_label}</text>'
        )

    # Record insertion point: legend will be inserted here (behind arrows & nodes)
    legend_insert_idx = len(parts)

    # Arrows
    arrow_labels: list[tuple[int, int, str]] = []

    # ── Pre-compute anti-overlap: spread attachment points for converging arrows ──
    incoming_by_target: dict[str, list[int]] = {}  # target_id → [arrow indices]
    for ai, arrow in enumerate(arrows):
        tgt_id = arrow["to"]
        incoming_by_target.setdefault(tgt_id, []).append(ai)

    # For each target with multiple incoming arrows:
    #  1. Spread attachment x-positions across the node edge
    #  2. Stagger mid_y so horizontal segments don't overlap
    SPREAD_GAP = 14  # pixels between attachment points
    MID_Y_STEP = 10  # pixels between staggered horizontal levels
    target_attach_x: dict[tuple[str, int], int] = {}  # (target_id, arrow_index) → x
    target_mid_y_offset: dict[tuple[str, int], int] = {}  # (target_id, arrow_index) → y offset
    for tgt_id, arrow_indices in incoming_by_target.items():
        n = len(arrow_indices)
        tgt = nodes.get(tgt_id)
        if not tgt or n <= 1:
            for ai in arrow_indices:
                target_attach_x[(tgt_id, ai)] = tgt["x"] + tgt["w"] // 2 if tgt else 0
                target_mid_y_offset[(tgt_id, ai)] = 0
        else:
            # Sort by source x so leftmost arrow gets lowest mid_y
            sorted_indices = sorted(arrow_indices, key=lambda ai: nodes.get(arrows[ai]["from"], {}).get("x", 0))
            cx = tgt["x"] + tgt["w"] // 2
            total_spread = (n - 1) * SPREAD_GAP
            start_x = cx - total_spread // 2
            for i, ai in enumerate(sorted_indices):
                target_attach_x[(tgt_id, ai)] = start_x + i * SPREAD_GAP
                target_mid_y_offset[(tgt_id, ai)] = int((i - (n - 1) / 2) * MID_Y_STEP)

    for ai, arrow in enumerate(arrows):
        src = nodes.get(arrow["from"])
        tgt = nodes.get(arrow["to"])
        if not src or not tgt:
            continue

        same_col = abs(src["x"] - tgt["x"]) < 50
        same_row = abs(src["y"] - tgt["y"]) < 80  # 增大阈值，同行节点用侧边直连

        # Use spread x for target attachment if available
        spread_tx = target_attach_x.get((arrow["to"], ai), tgt["x"] + tgt["w"] // 2)

        # If spread shifts the target x, it's no longer a simple same_col vertical
        truly_vertical = same_col and abs(spread_tx - (src["x"] + src["w"] // 2)) < 8

        if truly_vertical:
            # Vertical: bottom of upper node → top of lower node
            # 强制对齐 x 坐标，避免轻微倾斜
            center_x = (src["x"] + src["w"] // 2 + spread_tx) // 2
            if src["y"] < tgt["y"]:
                sx = center_x
                sy = src["y"] + src["h"] + y_offset
                tx = center_x
                ty = tgt["y"] + y_offset
            else:
                sx = center_x
                sy = src["y"] + y_offset
                tx = center_x
                ty = tgt["y"] + tgt["h"] + y_offset
            if arrow.get("dashed"):
                parts.append(f'<line x1="{sx}" y1="{sy}" x2="{tx}" y2="{ty}" stroke="{colors["arrow_muted"]}" stroke-width="1.5" stroke-dasharray="4,4" opacity="0.5" marker-end="url(#arrow-dashed)"/>')
            else:
                parts.append(_render_arrow_line(sx, sy, tx, ty, arrow, colors))
            if arrow.get("label"):
                arrow_labels.append(((sx + tx) // 2, (sy + ty) // 2, arrow["label"]))
        elif same_row:
            # Horizontal: source right edge → target left edge
            # 使用相同的 y 坐标，确保完全水平（不因节点高度差异产生斜线）
            avg_h = (src["h"] + tgt["h"]) // 2
            sy = src["y"] + avg_h // 2 + y_offset
            sx = src["x"] + src["w"]
            tx = tgt["x"]
            ty = sy  # 强制水平
            parts.append(_render_arrow_line(sx, sy, tx, ty, arrow, colors))
            if arrow.get("label"):
                arrow_labels.append(((sx + tx) // 2, sy, arrow["label"]))
        else:
            # Cross-row: elbow path routing
            if src["y"] > tgt["y"]:
                sx = src["x"] + src["w"] // 2
                sy = src["y"] + y_offset
                tx = spread_tx
                ty = tgt["y"] + tgt["h"] + y_offset
            else:
                sx = src["x"] + src["w"] // 2
                sy = src["y"] + src["h"] + y_offset
                tx = spread_tx
                ty = tgt["y"] + y_offset

            # Stagger mid_y so converging arrows have separate horizontal levels
            mid_y_offset = target_mid_y_offset.get((arrow["to"], ai), 0)
            # 基础 mid_y：在起点和终点之外，避免穿过节点
            if src["y"] < tgt["y"]:
                # 起点在上方，终点在下方 → mid_y 在终点下方
                base_mid_y = tgt["y"] + tgt["h"] + y_offset + 40
            else:
                # 起点在下方，终点在上方 → mid_y 在起点下方
                base_mid_y = src["y"] + src["h"] + y_offset + 40
            mid_y = base_mid_y + mid_y_offset

            # Collision avoidance: 确保 mid_y 不与任何节点边缘粘连
            # 策略：找最近的"安全"位置（不在任何节点边缘附近）
            h_min_x = min(sx, tx)
            h_max_x = max(sx, tx)
            MIN_GAP = 8  # 最小间距（不能太大，否则两个紧挨节点之间没空间）

            # 收集所有在 x 范围内的节点边缘
            blocked_ranges = []
            for nid, nd in nodes.items():
                if nid == arrow["from"] or nid == arrow["to"]:
                    continue
                nd_left = nd["x"]
                nd_right = nd["x"] + nd["w"]
                if nd_right > h_min_x and nd_left < h_max_x:
                    nd_top = nd["y"] + y_offset
                    nd_bot = nd["y"] + nd["h"] + y_offset
                    # 节点占据的 y 范围（加安全间距）
                    blocked_ranges.append((nd_top - MIN_GAP, nd_bot + MIN_GAP))

            # 检查 mid_y 是否在 blocked 范围内
            for blocked_top, blocked_bot in blocked_ranges:
                if blocked_top <= mid_y <= blocked_bot:
                    # 尝试向上或向下推到最近的 block 边缘
                    candidates = []
                    if blocked_top > max(sy, ty) + MIN_GAP or blocked_top < min(sy, ty) - MIN_GAP:
                        candidates.append(blocked_top)
                    candidates.append(blocked_bot)
                    # 选择距离当前 mid_y 最近的候选位置
                    if candidates:
                        mid_y = min(candidates, key=lambda c: abs(c - mid_y))
                    break

            if arrow.get("dashed"):
                style = f'stroke="{colors["arrow_muted"]}" stroke-width="1.5" stroke-dasharray="4,4" opacity="0.5" fill="none"'
                marker = "arrow-dashed"
            else:
                style = f'stroke="{colors["arrow"]}" stroke-width="1.5" fill="none"'
                marker = "arrow-solid"

            if abs(sx - tx) < 8:
                parts.append(f'<line x1="{sx}" y1="{sy}" x2="{tx}" y2="{ty}" {style} marker-end="url(#{marker})"/>')
            else:
                path_d = f"M {sx} {sy} L {sx} {mid_y} L {tx} {mid_y} L {tx} {ty}"
                parts.append(f'<path d="{path_d}" {style} marker-end="url(#{marker})"/>')

            if arrow.get("label"):
                arrow_labels.append((max(sx, tx) + 4, mid_y, arrow["label"]))
    for mx, my, label in arrow_labels:
        parts.append(_arrow_label(mx, my, label, colors=colors))

    # Update region rect to contain all arrow paths
    if region_rect_idx is not None:
        max_arrow_y = 0
        for ai, arrow in enumerate(arrows):
            src = nodes.get(arrow["from"])
            tgt = nodes.get(arrow["to"])
            if not src or not tgt:
                continue
            if abs(src["y"] - tgt["y"]) < 80:
                continue  # same_row, no elbow
            if src["y"] > tgt["y"]:
                mid_y_base = src["y"] + src["h"] + y_offset + 40
            else:
                mid_y_base = tgt["y"] + tgt["h"] + y_offset + 40
            mid_y_off = target_mid_y_offset.get((arrow["to"], ai), 0)
            max_arrow_y = max(max_arrow_y, mid_y_base + mid_y_off + 10)
        old_rect = parts[region_rect_idx]
        m = _re.search(r'y="(\d+)" width="(\d+)" height="(\d+)"', old_rect)
        if m and max_arrow_y > 0:
            old_y = int(m.group(1))
            old_h = int(m.group(3))
            new_bottom = max(old_y + old_h, max_arrow_y)
            new_h = new_bottom - old_y
            parts[region_rect_idx] = old_rect.replace(f'height="{old_h}"', f'height="{new_h}"')

        # Extend SVG canvas if region rect exceeds it
        # Reserve 160px at bottom for legend + footer so they don't overlap arrows
        LEGEND_FOOTER_RESERVE = 160
        min_canvas_bottom = max_arrow_y + LEGEND_FOOTER_RESERVE if max_arrow_y > 0 else h
        if min_canvas_bottom > h:
            h = min_canvas_bottom
            parts[0] = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" font-family="{FONT}">'




    # Nodes with semantic colors
    for nid, n in nodes.items():
        cat = n.get("category", "external")
        fill, stroke = _resolve_system_colors(cat, theme)
        rx = 8
        ny = n["y"] + y_offset
        parts.append(f'<g class="node" id="{nid}">')
        parts.append(f'<rect x="{n["x"]}" y="{ny}" width="{n["w"]}" height="{n["h"]}" '
                     f'rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
        # Label
        subs = n.get("subtitles", [])
        label_y = ny + n["h"] // 2 - (len(subs) + 1) * 7
        parts.append(
            f'<text x="{n["x"]+n["w"]//2}" y="{label_y+10}" '
            f'text-anchor="middle" font-size="14" fill="{colors["text_main"]}" '
            f'font-weight="600">{_esc(n["label"])}</text>'
        )
        for i, sub in enumerate(subs):
            c = stroke if i == len(subs) - 1 else colors["text_sub"]
            parts.append(
                f'<text x="{n["x"]+n["w"]//2}" y="{label_y+24+i*14}" '
                f'text-anchor="middle" font-size="10" fill="{c}">{_esc(sub)}</text>'
            )
        parts.append('</g>')


    # Legend — show categories actually used in the diagram
    # Render BEFORE arrows & nodes (z-order: legend behind content)
    _CAT_LABELS = {
        "frontend": "前端/入口",
        "cloud": "网关/网络",
        "backend": "计算/核心",
        "message_bus": "消息/集成",
        "database": "数据/存储",
        "security": "安全/权限",
        "external": "外部/入口",
    }
    used_cats = list(dict.fromkeys(
        n.get("category", "external") for n in nodes.values()
    ))
    cat_samples = [(c, _CAT_LABELS.get(c, c)) for c in used_cats if c != "external"]
    ROW_H = 18
    legend_w = 160
    legend_h = 20 + len(cat_samples) * ROW_H + 6 + 2 * ROW_H + 10
    legend_x, legend_y = 40, h - legend_h - 12

    legend_parts = [
        f'<g class="legend" transform="translate({legend_x}, {legend_y})">',
        f'<rect x="0" y="0" width="{legend_w}" height="{legend_h}" '
        f'rx="6" fill="{colors["canvas"]}" stroke="{colors["border"]}" stroke-width="1" opacity="0.95"/>',
        f'<text x="12" y="16" font-size="11" fill="{colors["text_main"]}" '
        f'font-weight="600" letter-spacing="0.3">图 例</text>',
    ]
    for ci, (cat, label) in enumerate(cat_samples):
        fill, stroke = _resolve_system_colors(cat, theme)
        if not fill:
            fill, stroke = colors["sys_fill"], colors["sys_stroke"]
        cy = 28 + ci * ROW_H
        legend_parts.append(
            f'<rect x="12" y="{cy}" width="12" height="12" rx="3" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1"/>'
            f'<text x="30" y="{cy+10}" font-size="9" fill="{colors["text_sub"]}">{label}</text>'
        )
    arrow_base_y = 28 + len(cat_samples) * ROW_H + 6
    legend_parts.append(
        f'<line x1="12" y1="{arrow_base_y+6}" x2="30" y2="{arrow_base_y+6}" '
        f'stroke="{colors["arrow"]}" stroke-width="1.5"/>'
        f'<text x="38" y="{arrow_base_y+10}" font-size="9" fill="{colors["text_sub"]}">数据流</text>'
    )
    legend_parts.append(
        f'<line x1="12" y1="{arrow_base_y+ROW_H+6}" x2="30" y2="{arrow_base_y+ROW_H+6}" '
        f'stroke="{colors["arrow_muted"]}" stroke-width="1.5" stroke-dasharray="4,4" opacity="0.5" '
        f'marker-end="url(#arrow-dashed)"/>'
        f'<text x="38" y="{arrow_base_y+ROW_H+10}" font-size="9" fill="{colors["text_sub"]}">支撑 / 依赖</text>'
    )
    legend_parts.append('</g>')
    # Insert legend at the recorded position (behind arrows & nodes)
    for i, lp in enumerate(legend_parts):
        parts.insert(legend_insert_idx + i, lp)
    legend_insert_idx += len(legend_parts)  # update for subsequent inserts

    # Footer
    parts.append(
        f'<text x="{w//2}" y="{h-15}" text-anchor="middle" '
        f'font-size="10" fill="{colors["text_sub"]}" letter-spacing="0.5">'
        f'{_esc(title)} • 自由流布局</text>'
    )

    parts.append("</svg>")
    return "\n".join(parts)


def export_svg_auto(blueprint: dict[str, Any], target: Path, theme: str = "dark") -> None:
    """Export using free-flow L→R data flow layout.

    This is the default export: positions systems by category in columns
    (Cloud → Backend → Database) with semantic colors and arrows.
    When systems have ``layer`` fields, uses _layout_layered instead.
    """
    title = blueprint.get("meta", {}).get("title", "Business Blueprint")
    industry = blueprint.get("meta", {}).get("industry", "")
    subtitle = f"行业：{industry}" if industry else "架构"

    # Detect layer-based layout
    systems = blueprint.get("library", {}).get("systems", [])
    has_layers = any(s.get("layer") for s in systems)

    if has_layers:
        layout = _layout_layered(blueprint)
    else:
        layout = _layout_free_flow(blueprint)
    # Run quality validation
    issues = _check_layout_quality(layout, blueprint)
    if issues:
        print(f"  Layout quality issues ({len(issues)}):")
        for iss in issues:
            print(f"    - {iss}")
    svg = _render_free_flow_svg(layout, title, subtitle, theme=theme, blueprint=blueprint)
    target.write_text(svg, encoding="utf-8")


# ─── Export: Product Tree / Genealogy ────────────────────────────
def export_product_tree_svg(blueprint: dict[str, Any], target: Path, theme: str = "light") -> None:
    """Product family tree: root → market segments → products with capability badges."""
    colors = _resolve_theme(theme)
    title = blueprint.get("meta", {}).get("title", "Product Family")
    lib = blueprint.get("library", {})
    systems = lib.get("systems", [])
    capabilities = lib.get("capabilities", [])
    relations = blueprint.get("relations", [])

    cap_by_id = {c["id"]: c for c in capabilities}
    sys_by_id = {s["id"]: s for s in systems}

    # Build evolution map: from_id → to_id
    evolve_map: dict[str, list[str]] = {}
    platform_powers: dict[str, list[str]] = {}
    for r in relations:
        if r["type"] == "powers":
            platform_powers.setdefault(r["from"], []).append(r["to"])
        elif r["type"] == "evolves-to" or r["label"] == "演进":
            evolve_map.setdefault(r["from"], []).append(r["to"])

    # Market segments — derive from blueprint data
    # Use views.productTree.segments or group by system properties
    _views = blueprint.get("views")
    if isinstance(_views, dict):
        segments = _views.get("productTree", {}).get("segments", [])
    else:
        segments = []
    if not segments:
        # Auto-derive: group systems by their "segment" property
        seg_map: dict[str, list[str]] = {}
        for s in systems:
            seg_label = s.get("properties", {}).get("segment", s.get("segment", ""))
            if seg_label:
                seg_map.setdefault(seg_label, []).append(s["id"])
        segments = [{"label": label, "ids": ids} for label, ids in seg_map.items()]

    # Filter to actual systems
    active_segments: list[dict] = []
    for seg in segments:
        matched = [s for s in systems if s["id"] in seg["ids"]]
        if matched:
            active_segments.append({"label": seg["label"], "sys_ids": [s["id"] for s in matched]})

    # Fallback: all systems in one group
    if not active_segments and systems:
        active_segments = [{"label": "Products", "sys_ids": [s["id"] for s in systems]}]

    PAD_X = 50
    PAD_Y = 30
    NODE_H = 44
    CAP_H = 20
    COL_W = 220
    SEG_GAP = 16  # gap between segment group boxes
    SEG_INNER_PAD = 18  # inside group box
    ROOT_W = 160
    ROOT_H = 44

    # Color palette — auto-assign distinct colors per segment
    _SEG_PALETTE = [
        ("#4338CA", "#EEF2FF"),
        ("#0B6E6E", "#E8F5F5"),
        ("#0F7B6C", "#E8F5F5"),
        ("#059669", "#ECFDF5"),
        ("#D97706", "#FEFCE8"),
        ("#7C3AED", "#F5F3FF"),
        ("#DC2626", "#FEF2F2"),
    ]
    seg_colors: dict[str, tuple[str, str]] = {}
    for i, seg in enumerate(active_segments):
        seg_colors[seg["label"]] = _SEG_PALETTE[i % len(_SEG_PALETTE)]

    # Pass 1: compute layout
    max_cols = 0
    total_seg_h = 0
    seg_layouts: list[dict] = []
    for seg in active_segments:
        n_cols = len(seg["sys_ids"])
        max_cols = max(max_cols, n_cols)
        # Compute max badge count across systems in this segment
        max_badges = 0
        for sid in seg["sys_ids"]:
            sys = sys_by_id.get(sid)
            if sys:
                max_badges = max(max_badges, len(sys.get("capabilityIds", [])))
        # Segment group height = label + pad + node row + badges
        seg_h = 24 + SEG_INNER_PAD + NODE_H + max(0, max_badges) * (CAP_H + 4) + 4
        total_seg_h += seg_h + SEG_GAP
        seg_layouts.append({"label": seg["label"], "sys_ids": seg["sys_ids"], "h": seg_h})

    canvas_w = PAD_X * 2 + max_cols * COL_W + (max_cols - 1) * 20
    root_y = PAD_Y + 92
    seg_y = root_y + ROOT_H + SEG_GAP + 30  # arrow space + gap

    parts: list[str] = []  # will prepend svg header after layout

    # Title block
    parts.append(
        f'<g class="title-block">'
        f'<rect x="{PAD_X}" y="{PAD_Y}" width="{canvas_w - PAD_X * 2}" height="52" '
        f'rx="6" fill="{colors["canvas"]}" stroke="{colors["border"]}" stroke-width="1"/>'
        f'<text x="{PAD_X + 16}" y="{PAD_Y + 24}" '
        f'font-size="16" fill="{colors["text_main"]}" font-family="{FONT}" '
        f'font-weight="700">{_esc(title)} — 产品谱系</text>'
        f'<text x="{PAD_X + 16}" y="{PAD_Y + 42}" '
        f'font-size="11" fill="{colors["text_sub"]}" font-family="{FONT_MONO}">'
        f'{_esc(title)}</text></g>'
    )

    cx = canvas_w / 2

    # Root node — use blueprint title
    root_label = title.split("—")[0].strip() if "—" in title else title.split("-")[0].strip()
    parts.append(
        f'<rect class="node-rect" x="{cx - ROOT_W / 2}" y="{root_y}" width="{ROOT_W}" height="{ROOT_H}" '
        f'rx="8" fill="#1E293B" stroke="#0F172A" stroke-width="1.5"/>'
        f'<text class="node-label" x="{cx}" y="{root_y + ROOT_H / 2 + 5}" '
        f'text-anchor="middle" font-size="15" fill="#FFFFFF" '
        f'font-weight="700">{_esc(root_label)}</text>'
    )

    node_positions: dict[str, tuple[int, int]] = {}
    seg_top_y: dict[str, int] = {}  # for arrows

    current_y = seg_y
    for sl in seg_layouts:
        seg_label = sl["label"]
        stroke, fill = seg_colors.get(seg_label, ("#64748B", "#F8FAFC"))
        sys_ids = sl["sys_ids"]
        n = len(sys_ids)
        seg_w = n * COL_W + max(0, n - 1) * 20
        seg_start_x = cx - seg_w / 2

        seg_top_y[seg_label] = current_y

        # Segment group bg
        parts.append(
            f'<rect x="{seg_start_x - SEG_INNER_PAD}" y="{current_y}" '
            f'width="{seg_w + SEG_INNER_PAD * 2}" height="{sl["h"]}" '
            f'rx="10" fill="{fill}" stroke="{stroke}" stroke-width="1" opacity="0.6"/>'
        )
        # Segment label
        parts.append(
            f'<text x="{cx}" y="{current_y + 16}" text-anchor="middle" '
            f'font-size="11" fill="{stroke}" font-weight="600" letter-spacing="0.5">'
            f'{_esc(seg_label)}</text>'
        )

        ny = current_y + 28
        for ci, sid in enumerate(sys_ids):
            sys = sys_by_id.get(sid)
            if not sys:
                continue
            nx = int(seg_start_x + ci * (COL_W + 20))
            node_positions[sid] = (nx + COL_W // 2, ny + NODE_H // 2)

            parts.append(
                f'<rect class="node-rect" x="{nx}" y="{ny}" width="{COL_W}" height="{NODE_H}" '
                f'rx="6" fill="{colors["canvas"]}" stroke="{stroke}" stroke-width="1.5"/>'
                f'<text class="node-label" x="{nx + COL_W // 2}" y="{ny + NODE_H // 2 + 5}" '
                f'text-anchor="middle" font-size="12" fill="{colors["text_main"]}" '
                f'font-weight="600">{_esc(sys["name"])}</text>'
            )

            # Capability badges
            cap_ids = sys.get("capabilityIds", [])
            badge_y = ny + NODE_H + 6
            for j, cid in enumerate(cap_ids[:4]):
                cap = cap_by_id.get(cid, {})
                cap_name = cap.get("name", cid)
                bw = max(len(cap_name) * 7 + 12, 50)
                bx = nx + COL_W // 2 - bw // 2
                parts.append(
                    f'<rect x="{bx}" y="{badge_y + j * (CAP_H + 4)}" width="{bw}" height="{CAP_H}" '
                    f'rx="3" fill="{stroke}" opacity="0.15"/>'
                    f'<text x="{bx + bw // 2}" y="{badge_y + j * (CAP_H + 4) + CAP_H // 2 + 5}" '
                    f'text-anchor="middle" font-size="9" fill="{stroke}">{_esc(cap_name)}</text>'
                )

        current_y += sl["h"] + SEG_GAP

    canvas_h = current_y + PAD_Y  # bottom padding after last segment

    # Prepend SVG header
    header = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" height="{canvas_h}" '
        f'font-family="{FONT}">',
        _svg_defs(colors=colors, theme=theme),
        f'<rect width="{canvas_w}" height="{canvas_h}" fill="{colors["bg"]}"/>',
    ]
    if theme == "dark":
        header.append(f'<rect width="{canvas_w}" height="{canvas_h}" fill="url(#grid)"/>')
    parts[0:0] = header

    # Arrows: root to each segment group
    for seg in active_segments:
        ry2 = seg_top_y[seg["label"]] + 14
        parts.append(
            f'<line x1="{cx}" y1="{root_y + ROOT_H}" x2="{cx}" y2="{ry2}" '
            f'stroke="{colors["arrow_muted"]}" stroke-width="1" stroke-dasharray="4,3" '
            f'marker-end="url(#arrow-dashed)"/>'
        )

    # Evolution arrows (EAS → 星瀚, etc.)
    for from_id, to_ids in evolve_map.items():
        for to_id in to_ids:
            if from_id in node_positions and to_id in node_positions:
                fx, fy = node_positions[from_id]
                tx, ty = node_positions[to_id]
                if abs(tx - fx) > 30:  # not in same column
                    dy = (fy + ty) / 2
                    parts.append(
                        f'<path d="M{fx},{fy} C{fx},{dy} {tx},{dy} {tx},{ty}" '
                        f'fill="none" stroke="#DC2626" stroke-width="1.5" stroke-dasharray="6,3" '
                        f'marker-end="url(#arrow-dashed)" opacity="0.6"/>'
                    )
                    # Label
                    mx, my = (fx + tx) // 2, dy
                    parts.append(
                        f'<rect x="{mx - 22}" y="{my - 8}" width="44" height="16" '
                        f'rx="3" fill="{colors["arrow_label_bg"]}"/>'
                        f'<text x="{mx}" y="{my + 4}" text-anchor="middle" '
                        f'font-size="9" fill="#DC2626" font-weight="500">演进</text>'
                    )

    # Platform arrows (苍穹 → 星瀚)
    for plat_id, targets in platform_powers.items():
        if plat_id in node_positions:
            px, py = node_positions[plat_id]
            for tgt_id in targets:
                if tgt_id in node_positions:
                    tx, ty = node_positions[tgt_id]
                    dy = (py + ty) / 2
                    parts.append(
                        f'<path d="M{px},{py + 22} C{px},{dy} {tx},{dy} {tx},{ty - 22}" '
                        f'fill="none" stroke="#4338CA" stroke-width="2" '
                        f'marker-end="url(#arrow-solid)" opacity="0.7"/>'
                    )
                    mx = (px + tx) // 2
                    my = dy
                    parts.append(
                        f'<rect x="{mx - 22}" y="{my - 8}" width="44" height="16" '
                        f'rx="3" fill="{colors["arrow_label_bg"]}"/>'
                        f'<text x="{mx}" y="{my + 4}" text-anchor="middle" '
                        f'font-size="9" fill="#4338CA" font-weight="500">支撑</text>'
                    )

    parts.append("</svg>")
    target.write_text("\n".join(parts), encoding="utf-8")


# ─── Export: Capability Matrix ───────────────────────────────────
def export_matrix_svg(blueprint: dict[str, Any], target: Path, theme: str = "light") -> None:
    colors = _resolve_theme(theme)
    """Matrix view: products as rows, capabilities as columns, coverage as cells."""
    title = blueprint.get("meta", {}).get("title", "Product Family")
    lib = blueprint.get("library", {})
    systems = lib.get("systems", [])
    capabilities = lib.get("capabilities", [])

    # Market segments — derive from blueprint data
    _views = blueprint.get("views")
    if isinstance(_views, dict):
        segments = _views.get("productTree", {}).get("segments", [])
    else:
        segments = []
    if not segments:
        seg_map: dict[str, list[str]] = {}
        for s in systems:
            seg_label = s.get("properties", {}).get("segment", s.get("segment", ""))
            if seg_label:
                seg_map.setdefault(seg_label, []).append(s["id"])
        segments = [{"label": label, "ids": ids} for label, ids in seg_map.items()]

    cap_by_id = {c["id"]: c for c in capabilities}
    sys_by_id = {s["id"]: s for s in systems}
    cap_ids = [c["id"] for c in capabilities]
    n_cols = len(cap_ids)

    # Build ordered product list grouped by segment
    ordered_products: list[tuple[str, str | None]] = []
    for seg in segments:
        for sid in seg["ids"]:
            if sid in sys_by_id:
                ordered_products.append((sid, seg["label"]))
    # Fallback: all systems in one group
    if not ordered_products and systems:
        ordered_products = [(s["id"], None) for s in systems]

    PAD_X = 40
    PAD_Y = 30
    SEG_LABEL_W = 80
    PROD_NAME_W = 110
    CAP_COL_W = 100
    ROW_H = 40
    HEADER_H = 44
    ROW_GAP = 1
    n_rows = len(ordered_products)

    canvas_w = PAD_X * 2 + SEG_LABEL_W + PROD_NAME_W + n_cols * CAP_COL_W
    canvas_h = PAD_Y * 2 + HEADER_H + n_rows * ROW_H + (n_rows - 1) * ROW_GAP + 80

    _SEG_STROKE_PALETTE = ["#4338CA", "#0B6E6E", "#0F7B6C", "#059669", "#D97706", "#7C3AED", "#DC2626"]
    seg_colors: dict[str, str] = {}
    for i, seg in enumerate(segments):
        seg_colors[seg["label"]] = _SEG_STROKE_PALETTE[i % len(_SEG_STROKE_PALETTE)]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" height="{canvas_h}" '
        f'font-family="{FONT}">',
        _svg_defs(colors=colors, theme=theme),
        f'<rect width="{canvas_w}" height="{canvas_h}" fill="{colors["bg"]}"/>',
    ]

    # Title
    parts.append(
        f'<g class="title-block">'
        f'<rect x="{PAD_X}" y="{PAD_Y}" width="{canvas_w - PAD_X * 2}" height="52" '
        f'rx="6" fill="{colors["canvas"]}" stroke="{colors["border"]}" stroke-width="1"/>'
        f'<text x="{PAD_X + 16}" y="{PAD_Y + 24}" '
        f'font-size="16" fill="{colors["text_main"]}" font-family="{FONT}" '
        f'font-weight="700">{_esc(title)} — 能力矩阵</text>'
        f'<text x="{PAD_X + 16}" y="{PAD_Y + 42}" '
        f'font-size="11" fill="{colors["text_sub"]}" font-family="{FONT_MONO}">'
        f'Capability Coverage Matrix</text></g>'
    )

    base_y = PAD_Y + 100
    left_w = SEG_LABEL_W + PROD_NAME_W

    # Header row
    parts.append(
        f'<rect x="{PAD_X}" y="{base_y}" width="{left_w}" height="{HEADER_H}" '
        f'rx="6" fill="{colors["canvas"]}" stroke="{colors["border"]}" stroke-width="1"/>'
    )
    parts.append(
        f'<text x="{PAD_X + left_w // 2}" y="{base_y + HEADER_H // 2 + 5}" '
        f'text-anchor="middle" font-size="13" fill="{colors["text_main"]}" '
        f'font-weight="600">产品 / 能力</text>'
    )

    for ci, cid in enumerate(cap_ids):
        cap = cap_by_id[cid]
        cx = PAD_X + left_w + ci * CAP_COL_W
        parts.append(
            f'<rect x="{cx}" y="{base_y}" width="{CAP_COL_W}" height="{HEADER_H}" '
            f'rx="0" fill="{colors["canvas"]}" stroke="{colors["border"]}" stroke-width="1"/>'
            f'<text x="{cx + CAP_COL_W // 2}" y="{base_y + HEADER_H // 2 + 5}" '
            f'text-anchor="middle" font-size="11" fill="{colors["text_main"]}" '
            f'font-weight="500">{_esc(cap["name"])}</text>'
        )

    # Data rows
    prev_seg: str | None = None
    for ri, (sid, seg_label) in enumerate(ordered_products):
        sys = sys_by_id[sid]
        row_y = base_y + HEADER_H + ri * (ROW_H + ROW_GAP)
        sys_cap_ids = set(sys.get("capabilityIds", []))

        stroke = seg_colors.get(seg_label or "", "#64748B")

        # Row bg
        parts.append(
            f'<rect x="{PAD_X}" y="{row_y}" width="{canvas_w - PAD_X * 2}" height="{ROW_H}" '
            f'rx="0" fill="{colors["canvas"]}" stroke="{colors["border"]}" stroke-width="0.5"/>'
        )

        # Segment label (first row of each group)
        if seg_label != prev_seg:
            parts.append(
                f'<text x="{PAD_X + 8}" y="{row_y + ROW_H // 2 + 5}" '
                f'font-size="10" fill="{stroke}" font-weight="600" '
                f'transform="rotate(-45, {PAD_X + 8}, {row_y + ROW_H // 2 + 5})">'
                f'{_esc(seg_label or "")}</text>'
            )
            prev_seg = seg_label

        # Product name
        parts.append(
            f'<text x="{PAD_X + SEG_LABEL_W + 8}" y="{row_y + ROW_H // 2 + 5}" '
            f'font-size="12" fill="{colors["text_main"]}" font-weight="500">'
            f'{_esc(sys["name"])}</text>'
        )

        # Capability cells
        for ci, cid in enumerate(cap_ids):
            cx = PAD_X + left_w + ci * CAP_COL_W
            if cid in sys_cap_ids:
                parts.append(
                    f'<rect x="{cx + 2}" y="{row_y + 2}" width="{CAP_COL_W - 4}" height="{ROW_H - 4}" '
                    f'rx="4" fill="{stroke}" opacity="0.2"/>'
                    f'<text x="{cx + CAP_COL_W // 2}" y="{row_y + ROW_H // 2 + 5}" '
                    f'text-anchor="middle" font-size="14" fill="{stroke}">✓</text>'
                )
            else:
                parts.append(
                    f'<text x="{cx + CAP_COL_W // 2}" y="{row_y + ROW_H // 2 + 5}" '
                    f'text-anchor="middle" font-size="14" fill="#E2E8F0">—</text>'
                )

    # Legend
    legend_y = base_y + HEADER_H + n_rows * (ROW_H + ROW_GAP) + 30
    parts.append(
        f'<text x="{PAD_X}" y="{legend_y}" font-size="10" fill="{colors["text_sub"]}">'
        f'■ 覆盖  — 未覆盖  | 颜色 = 市场分层</text>'
    )

    parts.append("</svg>")
    target.write_text("\n".join(parts), encoding="utf-8")


# ─── Export: Capability Map ──────────────────────────────────────
def export_capability_map_svg(blueprint: dict[str, Any], target: Path, theme: str = "light") -> None:
    colors = _resolve_theme(theme)
    """Capability map: grouped cards showing business capabilities and their supporting systems."""
    title = blueprint.get("meta", {}).get("title", "Business Blueprint")
    industry = blueprint.get("meta", {}).get("industry", "")
    lib = blueprint.get("library", {})
    capabilities = lib.get("capabilities", [])
    systems = lib.get("systems", [])
    actors = lib.get("actors", [])

    sys_by_id = {s["id"]: s for s in systems}
    actor_by_id = {a["id"]: a for a in actors}

    PAD_X = 50
    PAD_Y = 30
    CARD_W = 200
    CARD_H = 80
    CARD_GAP = 16

    # Dynamic grid calculation: adjust columns based on capability count
    n = len(capabilities)
    if n <= 4:
        COLS = min(n, 2)
    elif n <= 9:
        COLS = 3
    elif n <= 16:
        COLS = 4
    elif n <= 25:
        COLS = 5
    else:
        COLS = 6

    COL_W = CARD_W + CARD_GAP
    canvas_w = PAD_X * 2 + COLS * COL_W - CARD_GAP

    parts: list[str] = []

    # Title block
    subtitle = f"行业：{industry}" if industry else "能力地图"
    parts.extend([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" height="0" '
        f'font-family="{FONT}">',
        _svg_defs(colors=colors, theme=theme),
        f'<rect width="{canvas_w}" height="0" fill="{colors["bg"]}"/>',
    ])

    parts.append(
        f'<g class="title-block">'
        f'<rect x="{PAD_X}" y="{PAD_Y}" width="{canvas_w - PAD_X * 2}" height="52" '
        f'rx="6" fill="{colors["canvas"]}" stroke="{colors["border"]}" stroke-width="1"/>'
        f'<text x="{PAD_X + 16}" y="{PAD_Y + 24}" '
        f'font-size="16" fill="{colors["text_main"]}" font-family="{FONT}" '
        f'font-weight="700">{_esc(title)} — 能力地图</text>'
        f'<text x="{PAD_X + 16}" y="{PAD_Y + 42}" '
        f'font-size="11" fill="{colors["text_sub"]}" font-family="{FONT_MONO}">'
        f'{_esc(subtitle)}</text></g>'
    )

    # Color palette for capability levels
    level_colors = {
        0: ("#1E293B", "#F1F5F9"),
        1: ("#0B6E6E", "#E8F5F5"),
        2: ("#059669", "#ECFDF5"),
    }

    # Group capabilities by level
    by_level: dict[int, list[dict]] = {}
    for cap in capabilities:
        lvl = cap.get("level", 1)
        by_level.setdefault(lvl, []).append(cap)

    current_y = PAD_Y + 72
    canvas_h = current_y

    level_labels = {0: "战略层", 1: "核心层", 2: "支撑层"}

    for lvl in sorted(by_level.keys()):
        caps = by_level[lvl]
        stroke, fill = level_colors.get(lvl, ("#64748B", "#F8FAFC"))
        level_label = level_labels.get(lvl, f"L{lvl}")

        # Level header
        parts.append(
            f'<text x="{PAD_X}" y="{current_y}" font-size="13" fill="{stroke}" '
            f'font-weight="700" font-family="{FONT}">{level_label} ({len(caps)})</text>'
        )
        current_y += 14

        # Cards in grid
        n = len(caps)
        n_rows = math.ceil(n / COLS) if COLS > 0 else n
        card_block_h = n_rows * CARD_H + max(0, n_rows - 1) * CARD_GAP

        for i, cap in enumerate(caps):
            col = i % COLS
            row = i // COLS
            cx = PAD_X + col * COL_W
            cy = current_y + row * (CARD_H + CARD_GAP)

            sys_names = []
            for sid in cap.get("supportingSystemIds", []):
                s = sys_by_id.get(sid)
                if s:
                    sys_names.append(s["name"])

            parts.append(
                f'<rect x="{cx}" y="{cy}" width="{CARD_W}" height="{CARD_H}" '
                f'rx="6" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
                f'<text x="{cx + 12}" y="{cy + 20}" font-size="12" fill="{stroke}" '
                f'font-weight="600">{_esc(cap["name"])}</text>'
            )

            # Description (truncated)
            desc = cap.get("description", "")[:40]
            if desc:
                parts.append(
                    f'<text x="{cx + 12}" y="{cy + 36}" font-size="9" fill="{colors["text_sub"]}">'
                    f'{_esc(desc)}</text>'
                )

            # Supporting systems
            for j, sname in enumerate(sys_names[:3]):
                parts.append(
                    f'<rect x="{cx + 12}" y="{cy + 46 + j * 16}" width="{CARD_W - 24}" height="14" '
                    f'rx="3" fill="{colors["canvas"]}"/>'
                    f'<text x="{cx + 18}" y="{cy + 57 + j * 16}" font-size="8.5" fill="{colors["text_main"]}">'
                    f'{_esc(sname)}</text>'
                )

        current_y += card_block_h + 24
        canvas_h = current_y

    canvas_h += PAD_Y
    # Fix SVG header with computed height
    parts[0] = f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" height="{canvas_h}" font-family="{FONT}">'
    parts[2] = f'<rect width="{canvas_w}" height="{canvas_h}" fill="{colors["bg"]}"/>'

    parts.append("</svg>")
    target.write_text("\n".join(parts), encoding="utf-8")


# ─── Export: Swimlane Flow ───────────────────────────────────────
def export_swimlane_flow_svg(blueprint: dict[str, Any], target: Path, theme: str = "light") -> None:
    colors = _resolve_theme(theme)
    """Swimlane flow diagram: actors as lanes, flow steps as connected cards."""
    title = blueprint.get("meta", {}).get("title", "Business Blueprint")
    industry = blueprint.get("meta", {}).get("industry", "")
    lib = blueprint.get("library", {})
    actors = lib.get("actors", [])
    flow_steps = lib.get("flowSteps", [])
    capabilities = lib.get("capabilities", [])

    cap_by_id = {c["id"]: c for c in capabilities}
    actor_by_id = {a["id"]: a for a in actors}

    PAD_X = 50
    PAD_Y = 30
    LANE_HEADER_H = 36
    LANE_GAP = 16
    STEP_W = 160
    STEP_H = 40
    STEP_GAP = 14
    ARROW_GAP = 12

    # Group flow steps by actor
    steps_by_actor: dict[str, list[dict]] = {}
    for step in flow_steps:
        aid = step.get("actorId", "")
        steps_by_actor.setdefault(aid, []).append(step)

    actor_order: list[str] = [a["id"] for a in actors]

    canvas_w = 900
    content_w = canvas_w - PAD_X * 2

    parts: list[str] = []

    subtitle = f"行业：{industry}" if industry else "泳道流程"
    parts.extend([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" height="0" '
        f'font-family="{FONT}">',
        _svg_defs(colors=colors, theme=theme),
        f'<rect width="{canvas_w}" height="0" fill="{colors["bg"]}"/>',
    ])

    parts.append(
        f'<g class="title-block">'
        f'<rect x="{PAD_X}" y="{PAD_Y}" width="{content_w}" height="52" '
        f'rx="6" fill="{colors["canvas"]}" stroke="{colors["border"]}" stroke-width="1"/>'
        f'<text x="{PAD_X + 16}" y="{PAD_Y + 24}" '
        f'font-size="16" fill="{colors["text_main"]}" font-family="{FONT}" '
        f'font-weight="700">{_esc(title)} — 泳道流程</text>'
        f'<text x="{PAD_X + 16}" y="{PAD_Y + 42}" '
        f'font-size="11" fill="{colors["text_sub"]}" font-family="{FONT_MONO}">'
        f'{_esc(subtitle)}</text></g>'
    )

    lane_palette = [
        ("#0B6E6E", "#E8F5F5"),
        ("#059669", "#ECFDF5"),
        ("#4338CA", "#EEF2FF"),
        ("#D97706", "#FEFCE8"),
        ("#DC2626", "#FEF2F2"),
        ("#7C3AED", "#F5F3FF"),
        ("#0891B2", "#ECFEFF"),
        ("#65A30D", "#F7FEE7"),
        ("#C2410C", "#FFF7ED"),
        ("#475569", "#F8FAFC"),
        ("#9333EA", "#FAF5FF"),
    ]

    # First pass: compute lane heights and step positions for arrow drawing
    lane_positions: dict[str, dict] = {}  # actor_id → {"y": top_y, "steps": {step_id: (cx, cy)}}
    current_y = PAD_Y + 72

    for lane_idx, actor_id in enumerate(actor_order):
        actor = actor_by_id.get(actor_id)
        if not actor:
            continue
        stroke, fill = lane_palette[lane_idx % len(lane_palette)]
        steps = steps_by_actor.get(actor_id, [])
        lane_h = LANE_HEADER_H + LANE_GAP + len(steps) * (STEP_H + STEP_GAP) + LANE_GAP

        lane_positions[actor_id] = {
            "y": current_y,
            "h": lane_h,
            "stroke": stroke,
            "fill": fill,
            "steps": {},
        }

        step_y = current_y + LANE_HEADER_H + LANE_GAP
        for si, step in enumerate(steps):
            cx = PAD_X + 14 + STEP_W // 2
            cy = step_y + si * (STEP_H + STEP_GAP) + STEP_H // 2
            lane_positions[actor_id]["steps"][step["id"]] = (cx, cy)

        current_y += lane_h + LANE_GAP

    # Arrows layer (drawn before cards)
    arrow_parts: list[str] = []
    # Intra-lane arrows (sequential flow within same actor)
    for actor_id, steps in steps_by_actor.items():
        pos_data = lane_positions.get(actor_id)
        if not pos_data:
            continue
        stroke = pos_data["stroke"]
        for i in range(len(steps) - 1):
            _, from_cy = pos_data["steps"][steps[i]["id"]]
            to_cx, to_cy = pos_data["steps"][steps[i + 1]["id"]]
            from_y = from_cy + STEP_H // 2 + 4
            to_y = to_cy - STEP_H // 2 - 2

            if from_y < to_y:
                mid_y = (from_y + to_y) / 2
                arrow_parts.append(
                    f'<path d="M{PAD_X + 14 + STEP_W // 2},{from_y} '
                    f'C{PAD_X + 14 + STEP_W // 2},{mid_y} {to_cx},{mid_y} {to_cx},{to_y}" '
                    f'fill="none" stroke="{stroke}" stroke-width="1.5" opacity="0.4" '
                    f'marker-end="url(#arrow-solid)"/>'
                )

    # Cross-lane arrows: capability overlap implies connection
    for i, aid1 in enumerate(steps_by_actor):
        for j, aid2 in enumerate(steps_by_actor):
            if j <= i:
                continue
            p1 = lane_positions.get(aid1)
            p2 = lane_positions.get(aid2)
            if not p1 or not p2:
                continue
            s1 = steps_by_actor[aid1]
            s2 = steps_by_actor[aid2]
            # Connect first step of each lane
            if s1 and s2 and s1[0]["id"] in p1["steps"] and s2[0]["id"] in p2["steps"]:
                _, cy1 = p1["steps"][s1[0]["id"]]
                _, cy2 = p2["steps"][s2[0]["id"]]
                x1 = PAD_X + 14 + STEP_W + 4
                x2 = PAD_X + 14 + STEP_W + 4
                my = (cy1 + cy2) / 2
                arrow_parts.append(
                    f'<path d="M{x1},{cy1} C{x1 + 30},{my} {x2 + 30},{my} {x2},{cy2}" '
                    f'fill="none" stroke="#94A3B8" stroke-width="1" stroke-dasharray="4,3" opacity="0.3" '
                    f'marker-end="url(#arrow-dashed)"/>'
                )

    # Second pass: render lanes and cards
    current_y = PAD_Y + 72
    for lane_idx, actor_id in enumerate(actor_order):
        actor = actor_by_id.get(actor_id)
        if not actor:
            continue
        stroke, fill = lane_palette[lane_idx % len(lane_palette)]

        steps = steps_by_actor.get(actor_id, [])
        lane_h = LANE_HEADER_H + LANE_GAP + len(steps) * (STEP_H + STEP_GAP) + LANE_GAP

        # Lane background
        parts.append(
            f'<rect x="{PAD_X}" y="{current_y}" width="{content_w}" height="{lane_h}" '
            f'rx="6" fill="{fill}" stroke="{stroke}" stroke-width="0.5" opacity="0.5"/>'
        )
        # Lane label with step count
        parts.append(
            f'<text x="{PAD_X + 14}" y="{current_y + LANE_HEADER_H // 2 + 5}" '
            f'font-size="12" fill="{stroke}" font-weight="600">{_esc(actor["name"])} '
            f'<tspan font-size="10" fill="{colors["text_sub"]}">({len(steps)}步)</tspan></text>'
        )
        # Right side: capability tags summary
        all_caps = set()
        for s in steps:
            for cid in s.get("capabilityIds", []):
                all_caps.add(cid)
        cap_x = PAD_X + content_w - 14
        for ci, cid in enumerate(list(all_caps)[:4]):
            cap = cap_by_id.get(cid, {})
            tag_w = len(cap.get("name", "")) * 7 + 10
            tx = cap_x - ci * (tag_w + 4) - tag_w
            parts.append(
                f'<rect x="{tx}" y="{current_y + 8}" width="{tag_w}" height="18" '
                f'rx="3" fill="{stroke}" opacity="0.15"/>'
                f'<text x="{tx + tag_w // 2}" y="{current_y + 21}" '
                f'text-anchor="middle" font-size="8" fill="{stroke}">'
                f'{_esc(cap.get("name", ""))}</text>'
            )

        step_y = current_y + LANE_HEADER_H + LANE_GAP
        for si, step in enumerate(steps):
            sx = PAD_X + 14
            sy = step_y + si * (STEP_H + STEP_GAP)

            # Step number badge
            step_num = si + 1
            parts.append(
                f'<rect x="{sx}" y="{sy}" width="{STEP_W}" height="{STEP_H}" '
                f'rx="5" fill="{colors["canvas"]}" stroke="{stroke}" stroke-width="1.5"/>'
                f'<rect x="{sx + 2}" y="{sy + 2}" width="22" height="{STEP_H - 4}" '
                f'rx="4" fill="{stroke}" opacity="0.12"/>'
                f'<text x="{sx + 13}" y="{sy + STEP_H // 2 + 5}" '
                f'text-anchor="middle" font-size="12" fill="{stroke}" font-weight="700">{step_num}</text>'
                f'<text x="{sx + 32}" y="{sy + STEP_H // 2 + 5}" '
                f'font-size="11" fill="{colors["text_main"]}" font-weight="500">'
                f'{_esc(step["name"])}</text>'
            )

            # Capability tags
            cap_ids = step.get("capabilityIds", [])
            for j, cid in enumerate(cap_ids[:2]):
                cap = cap_by_id.get(cid, {})
                tag_x = sx + STEP_W + 8 + j * 80
                cap_name = cap.get("name", "")
                if cap_name:
                    tw = len(cap_name) * 7 + 10
                    parts.append(
                        f'<rect x="{tag_x}" y="{sy + 10}" width="{tw}" height="18" '
                        f'rx="3" fill="{stroke}" opacity="0.15"/>'
                        f'<text x="{tag_x + tw // 2}" y="{sy + 23}" '
                        f'text-anchor="middle" font-size="8" fill="{stroke}">'
                        f'{_esc(cap_name)}</text>'
                    )

        current_y += lane_h + LANE_GAP

    # Insert arrows before the card elements
    parts[3:3] = arrow_parts

    canvas_h = current_y + PAD_Y
    parts[0] = f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" height="{canvas_h}" font-family="{FONT}">'
    parts[2] = f'<rect width="{canvas_w}" height="{canvas_h}" fill="{colors["bg"]}"/>'

    parts.append("</svg>")
    target.write_text("\n".join(parts), encoding="utf-8")
