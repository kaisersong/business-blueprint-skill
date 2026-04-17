# Architecture Diagram Design System

本文件定义 Agent 生成架构图时使用的完整设计系统。所有颜色、字体、间距、布局规则必须严格遵循。

## 1. 主题

### 暗黑模式（默认）

| Token | 值 | 用途 |
|-------|-----|------|
| `bg` | `#020617` | 页面背景（Slate-950） |
| `canvas` | `#0F172A` | 卡片表面（Slate-900） |
| `text_main` | `#E2E8F0` | 主文字 |
| `text_sub` | `#94A3B8` | 副文字 |
| `border` | `#1E293B` | 边框 |
| `grid` | `#1E293B` | 网格线（40px pattern） |

### 亮色模式

| Token | 值 | 用途 |
|-------|-----|------|
| `bg` | `#F8FAFC` | 页面背景 |
| `canvas` | `#FFFFFF` | 卡片表面 |
| `text_main` | `#0F172A` | 主文字 |
| `text_sub` | `#64748B` | 副文字 |
| `border` | `#CBD5E1` | 边框 |

## 2. 字体

- 主字体：`'JetBrains Mono', 'Fira Code', monospace`（Google Fonts CDN 引入）
- 回退字体：`system-ui, -apple-system, sans-serif`

| 层级 | 字号 | 字重 | 用途 |
|------|------|------|------|
| 标题 | 20px | 700 | SVG 主标题 |
| 副标题 | 13px | 400 | 副标题/注解 |
| 组件名 | 14px | 600 | 节点名称 |
| 副标签 | 11px | 400 | 节点描述 |
| 注解 | 9-10px | 400 | 标签、Legend |
| Region 标签 | 12px | 600 | Region 名称 |

## 3. 语义色

7 种系统类别，每种定义 fill + stroke（暗黑模式值）：

| 类别 | 填充色 | 描边色 | 用途 |
|------|--------|--------|------|
| `frontend` | `rgba(8,51,68,0.4)` | `#22d3ee` | Web、移动端、UI |
| `backend` | `rgba(6,78,59,0.4)` | `#34d399` | Lambda、API、服务 |
| `database` | `rgba(76,29,149,0.4)` | `#a78bfa` | DynamoDB、RDS |
| `cloud` | `rgba(120,53,15,0.3)` | `#fbbf24` | Region 框、CloudFront |
| `security` | `rgba(136,19,55,0.4)` | `#fb7185` | Security Group、WAF |
| `message_bus` | `rgba(251,146,60,0.3)` | `#fb923c` | SQS、SNS、EventBridge |
| `external` | `rgba(30,41,59,0.5)` | `#94a3b8` | 第三方 API、SaaS |

无类别时回退到：fill `#1E293B`，stroke `#94A3B8`。

## 4. 布局规则

### 4.1 L→R 数据流

```
Clients(左) → Frontend → Backend → Database(右)
```

- Clients 通常放在 Region 框外左侧
- 其他组件按 `flowSteps[].seqIndex` 排序，从左到右排列
- 水平间距 40-60px，垂直居中对齐

### 4.2 组件尺寸

根据 capabilities 数量决定：

| 能力数 | 宽度 | 高度 | 用途 |
|--------|------|------|------|
| 0-1 | 140px | 44px | 简单组件（SQS 等） |
| 2-4 | 150px | 80px | 中等组件（Lambda、S3） |
| 5+ | 160px | 80px | 大组件（API Gateway、DynamoDB） |

所有组件：`rx="8"` 圆角，`stroke-width="2"` 描边。

### 4.3 Region 边界

- 矩形框：`rx="16"`, `stroke-dasharray="8,4"`, 琥珀色 `#F59E0B`, `opacity="0.4"`
- Region 标签放在框外上方（x=Region左边界+20, y=Region上边界-10）
- 填充：`none`（仅描边）

### 4.4 Summary Cards

放在架构图底部，3 组卡片，响应式网格布局：

| 卡片 | 颜色 | 内容 |
|------|------|------|
| Infrastructure | 琥珀色 `#F59E0B` | 基础设施列表 |
| Compute | 翠绿色 `#34D399` | 计算资源描述 |
| Data | 紫色 `#A78BFA` | 数据存储描述 |

每张卡片：`rx="10"`, fill `#0F172A`, stroke `#1E293B`, 宽 340-370px, 高 130px。

## 5. 视觉元素

### 5.1 箭头

```svg
<marker id="arrow-solid" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">
  <polygon points="0 0, 10 4, 0 8" fill="#64748B"/>
</marker>
```

- 实线箭头：`stroke="#64748B"`, `stroke-width="2"`, `marker-end="url(#arrow-solid)"`
- 虚线箭头（可选）：`stroke-dasharray="4,3"`, `stroke="#475569"`

### 5.2 网格 Pattern

```svg
<pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
  <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1E293B" stroke-width="0.5"/>
</pattern>
```

### 5.3 节点结构

```svg
<g class="node">
  <rect x="..." y="..." width="..." height="..." rx="8" fill="..." stroke="..." stroke-width="2"/>
  <text x="..." y="..." text-anchor="middle" font-size="14" fill="#F8FAFC" font-weight="600">名称</text>
  <text x="..." y="..." text-anchor="middle" font-size="11" fill="#94A3B8">副标签</text>
</g>
```

## 6. Z 序

1. 背景（`#020617` rect）
2. 网格 pattern
3. 标题文字
4. Region 框
5. 箭头
6. 节点（rect + text）
7. Legend
8. Summary Cards
9. Footer

## 7. Blueprint 字段映射

| 视觉概念 | Blueprint 字段 | 推导逻辑 |
|---------|---------------|---------|
| 组件色 | `systems[].category` | 直接映射到语义色 |
| L→R 顺序 | `flowSteps[].seqIndex` | 按 seqIndex 排序 |
| Region 框 | `systems[].properties.type` | `type == "aws"` → Region |
| 组件大小 | `capabilities` 数量 | 0-1=小, 2-4=中, 5+=大 |
| 副标签 | `systems[].description` | 取前 2-3 个特征 |
| 箭头 | `flowSteps[].nextStepIds` | 从 nextStepIds 推导连接 |
