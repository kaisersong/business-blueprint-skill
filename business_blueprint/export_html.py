"""生成自包含的 HTML 查看器，内嵌 free-flow 架构图 SVG。

默认使用 free-flow 布局引擎，单图输出。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from .export_svg import FONT, FONT_MONO, _resolve_theme


def _get_skill_version() -> str:
    """Read skill version from pyproject.toml (source of truth over installed package)."""
    # Always prefer pyproject.toml in the source tree
    try:
        toml_path = Path(__file__).parent.parent / "pyproject.toml"
        text = toml_path.read_text()
        for line in text.splitlines():
            if line.startswith("version "):
                return line.split('"')[1]
    except Exception:
        pass
    import importlib.metadata
    try:
        return importlib.metadata.version("business-blueprint-skill")
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0"


_SKILL_VERSION = _get_skill_version()


def _esc(s: str) -> str:
    return escape(str(s))


def _build_architecture_svg(blueprint: dict[str, Any], colors: dict, theme: str) -> str:
    """Build architecture SVG for the HTML viewer.

    Uses free-flow L→R data flow layout by default.
    """
    import tempfile
    from .export_svg import export_svg_auto

    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
        tmp_path = Path(f.name)
    export_svg_auto(blueprint, tmp_path, theme=theme)
    result = tmp_path.read_text(encoding="utf-8")
    tmp_path.unlink()
    return result


def export_html_viewer(blueprint: dict[str, Any], target: Path, theme: str = "dark") -> None:
    """Generate a self-contained HTML viewer with inline architecture SVG."""
    colors = _resolve_theme(theme)
    title = blueprint.get("meta", {}).get("title", "Business Blueprint")
    lib = blueprint.get("library", {})
    n_systems = len(lib.get("systems", []))
    n_capabilities = len(lib.get("capabilities", []))
    n_actors = len(lib.get("actors", []))
    n_flow_steps = len(lib.get("flowSteps", []))
    systems_with_caps = sum(1 for s in lib.get("systems", []) if s.get("capabilityIds"))
    sys_coverage = f"{int(systems_with_caps / n_systems * 100)}%" if n_systems else "N/A"

    svg_content = _build_architecture_svg(blueprint, colors, theme)

    bg_color = colors["bg"]
    text_main = colors["text_main"]
    text_sub = colors["text_sub"]
    border = colors["border"]
    cap_stroke = colors["cap_stroke"]
    header_bg = "#020617" if theme == "dark" else "#0F2742"
    header_text = "#E2E8F0" if theme == "dark" else "#fff"
    card_bg = colors["canvas"]
    card_border = colors["border"]

    dark_extras = ""
    if theme == "dark":
        dark_extras = f"""
        .header {{ background: {header_bg}; color: {header_text}; }}
        .header .meta {{ font-size: 13px; color: #94A3B8; }}
        .summary-cards {{ background: linear-gradient(180deg, {colors["layer_header_bg"]}, {bg_color}); }}
        .summary-card {{ background: {card_bg}; border-color: {card_border}; }}
        .summary-card .card-value {{ color: {text_main}; }}
        .summary-card .card-label {{ color: {text_sub}; }}
        body {{ background: linear-gradient(180deg, {colors["bg"]} 0%, #0F172A 100%); }}
        .viewer svg {{ box-shadow: 0 2px 12px rgba(0,0,0,0.4); }}
"""
    else:
        dark_extras = f"""
        .summary-cards {{ background: linear-gradient(180deg, {colors["layer_header_bg"]}, {bg_color}); }}
        .summary-card {{ background: {card_bg}; border-color: {card_border}; }}
        .summary-card .card-value {{ color: {text_main}; }}
        .summary-card .card-label {{ color: {text_sub}; }}
"""

    grid_bg = ""
    if theme == "dark":
        grid_bg = '<div style="position:fixed;top:0;left:0;width:100%;height:100%;background-image:linear-gradient(rgba(255,255,255,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,0.03) 1px,transparent 1px);background-size:40px 40px;pointer-events:none;z-index:0;"></div>'

    safe_json = json.dumps(json.dumps(blueprint, ensure_ascii=False)).replace("</", "<\\/")
    meta = blueprint.get("meta", {})

    # Extract description content from context
    ctx = blueprint.get("context", {})
    goals = ctx.get("goals", [])
    scope = ctx.get("scope", [])
    assumptions = ctx.get("assumptions", [])
    constraints = ctx.get("constraints", [])

    # Extract key decisions from sourceRefs
    key_decisions = []
    for ref in ctx.get("sourceRefs", []):
        excerpt = ref.get("excerpt", "")
        for line in excerpt.split("\n"):
            stripped = line.strip()
            if stripped.startswith("- ") and ("design" in stripped.lower() or "decision" in stripped.lower() or "Design" in stripped):
                key_decisions.append(stripped[2:].strip())

    description_cards = ""
    card_sections = []
    if goals:
        card_sections.append(("Design Goals", "#F59E0B", goals))
    if scope:
        card_sections.append(("Scope", "#34D399", scope))
    if key_decisions:
        card_sections.append(("Key Decisions", "#A78BFA", key_decisions))
    if assumptions:
        card_sections.append(("Assumptions", "#60A5FA", assumptions))
    if constraints:
        card_sections.append(("Constraints", "#FB923C", constraints))

    if card_sections:
        for sec_title, sec_color, items in card_sections:
            items_html = "".join(
                f'<li>{_esc(item)}</li>' for item in items
            )
            description_cards += f"""
        <div class="desc-card">
            <div class="desc-card-title" style="color:{sec_color};">{_esc(sec_title)}</div>
            <ul class="desc-card-list">{items_html}</ul>
        </div>"""
        description_section = f"""
    <div class="description-section">
        <h2 class="description-title">Architecture Description</h2>
        <div class="description-grid">{description_cards}
        </div>
    </div>"""
    else:
        description_section = ""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{_esc(title)}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: {FONT}; background: {bg_color}; color: {text_main}; position: relative; }}
        .header {{ background: {header_bg}; color: {header_text}; padding: 12px 24px; display: flex; justify-content: space-between; align-items: center; position: relative; z-index: 1; }}
        .header h1 {{ font-size: 18px; font-weight: 600; }}
        .header .meta {{ font-size: 13px; color: #94A3B8; }}
        .summary-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; padding: 24px; margin: 0 24px; position: relative; z-index: 1; }}
        .summary-card {{ border-radius: 8px; border: 1px solid {card_border}; padding: 16px 20px; text-align: center; }}
        .summary-card .card-value {{ font-size: 28px; font-weight: 700; font-family: {FONT_MONO}; line-height: 1; }}
        .summary-card .card-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 6px; font-weight: 500; }}
        .viewer {{ padding: 24px; overflow: auto; display: flex; justify-content: center; position: relative; z-index: 1; }}
        .viewer svg {{ max-width: 100%; height: auto; border-radius: 8px; }}
        .download-btn {{ background: transparent; border: 1px solid {border}; color: {text_sub}; padding: 6px 14px; border-radius: 6px; font-size: 12px; cursor: pointer; font-family: {FONT_MONO}; transition: all 0.2s; }}
        .download-btn:hover {{ background: {cap_stroke}; color: {text_main}; border-color: {cap_stroke}; }}
        .description-section {{ padding: 24px 24px 48px; max-width: 1200px; margin: 0 auto; position: relative; z-index: 1; }}
        .description-title {{ font-size: 16px; font-weight: 700; margin-bottom: 16px; color: {text_main}; }}
        .description-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 16px; }}
        .desc-card {{ border-radius: 8px; border: 1px solid {card_border}; padding: 20px 24px; background: {card_bg}; }}
        .desc-card-title {{ font-size: 14px; font-weight: 700; margin-bottom: 12px; letter-spacing: 0.3px; }}
        .desc-card-list {{ list-style: none; padding: 0; margin: 0; }}
        .desc-card-list li {{ font-size: 13px; line-height: 1.7; color: {text_sub}; padding-left: 16px; position: relative; }}
        .desc-card-list li::before {{ content: "\u2022"; position: absolute; left: 0; color: {border}; }}
        {dark_extras}
    </style>
</head>
<body>
    {grid_bg}
    <div class="header">
        <div style="display:flex;align-items:baseline;gap:12px;">
            <h1>{_esc(title)}</h1>
            <span class="meta" style="font-size:11px;color:#64748B;">Business Blueprint v{_SKILL_VERSION}</span>
        </div>
        <div style="display:flex;align-items:center;gap:10px;">
            <button class="download-btn" onclick="downloadSvg()">Download SVG</button>
        </div>
    </div>
    <div class="summary-cards">
        <div class="summary-card">
            <div class="card-value">{n_systems}</div>
            <div class="card-label">Systems</div>
        </div>
        <div class="summary-card">
            <div class="card-value">{n_capabilities}</div>
            <div class="card-label">Capabilities</div>
        </div>
        <div class="summary-card">
            <div class="card-value">{n_actors}</div>
            <div class="card-label">Actors</div>
        </div>
        <div class="summary-card">
            <div class="card-value">{n_flow_steps}</div>
            <div class="card-label">Flow Steps</div>
        </div>
        <div class="summary-card">
            <div class="card-value">{sys_coverage}</div>
            <div class="card-label">Sys Coverage</div>
        </div>
    </div>
    <div class="viewer">{svg_content}</div>{description_section}
    <script>
        const blueprint = JSON.parse({safe_json});
        function downloadSvg() {{
            const svgEl = document.querySelector('.viewer svg');
            if (!svgEl) return;
            const serializer = new XMLSerializer();
            let source = serializer.serializeToString(svgEl);
            source = '<?xml version="1.0" encoding="UTF-8"?>\\n' + source;
            const blob = new Blob([source], {{ type: 'image/svg+xml;charset=utf-8' }});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = '{_esc(title)}.svg';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }}
    </script>
</body>
</html>"""

    target.write_text(html, encoding="utf-8")
