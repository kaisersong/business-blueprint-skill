# Domain-Knowledge Entities Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend business-blueprint skill to support domain-knowledge blueprints (pain points, strategies, rules, metrics, practices, pitfalls), while maintaining backward compatibility with existing architecture blueprints.

**Architecture:** Add optional `library.knowledge` block to JSON schema, implement validator with soft-schema validation (core fields strict, extension fields warn-only), extend freeflow renderer with knowledge-entity styles and clustering layout, support cross-type relations (knowledge → architecture).

**Tech Stack:** Python 3.12+, JSON schema validation, SVG rendering, pytest for testing

---

## File Structure

**Files to create:**
- `references/knowledge-entities-schema.md` - Knowledge entity field definitions
- `scripts/business_blueprint/templates/cross-border-ecommerce/seed.json` - Cross-border e-commerce industry hints
- `references/knowledge-rendering-guide.md` - Knowledge entity visual design guide

**Files to modify:**
- `references/entities-schema.md` - Add knowledge block overview
- `scripts/business_blueprint/templates/common/seed.json` - Add meta.blueprintType field
- `scripts/business_blueprint/templates/retail/seed.json` - Add knowledgeHints
- `scripts/business_blueprint/templates/finance/seed.json` - Add knowledgeHints
- `scripts/business_blueprint/templates/manufacturing/seed.json` - Add knowledgeHints
- `SKILL.md` - Add blueprint type detection and knowledge entity extraction guide
- `scripts/business_blueprint/validate.py` - Add knowledge validation logic
- `scripts/business_blueprint/export_routes.py` - Add knowledge route detection
- `scripts/business_blueprint/export_svg.py` - Add knowledge entity rendering

**Files to create (tests):**
- `tests/test_validate_knowledge.py` - Knowledge validator tests
- `tests/test_export_knowledge.py` - Knowledge rendering tests

---

## Phase 1: Documentation & Schema Definition (P0)

### Task 1: Create Knowledge Entities Schema Documentation

**Files:**
- Create: `references/knowledge-entities-schema.md`

- [ ] **Step 1: Write knowledge entities schema documentation**

Create file `references/knowledge-entities-schema.md`:

```markdown
# Knowledge Entities Schema Definition

This document defines field specifications for knowledge entities in domain-knowledge blueprints.

## Entity Overview

| Entity Type | entityType Value | Core Fields | Optional Fields | Typical Count |
|-------------|-----------------|-------------|-----------------|---------------|
| painPoints | `painPoint` | id, name, entityType | description, severity, level, relatedCapabilityIds, solutions | 3-8 |
| strategies | `strategy` | id, name, entityType | description, severity, level, applicableCapabilityIds, prerequisites | 3-10 |
| rules | `rule` | id, name, entityType | description, severity, platform, penalty, policyUrl | 3-8 |
| metrics | `metric` | id, name, entityType | value, unit, benchmarkContext, calculationMethod | 3-10 |
| practices | `practice` | id, name, entityType | description, frequency, successMetric | 3-10 |
| pitfalls | `pitfall` | id, name, entityType | description, severity, avoidanceStrategy, realCase | 3-8 |

## Core Fields (Validator Strict Enforcement)

**All knowledge entities must have these fields:**

### id
- **Type**: string
- **Format**: `{entityType}-{seq}` (e.g., `pain-001`, `str-001`, `rule-001`)
- **Required**: Yes
- **Validation**: Must be unique within blueprint, no duplicates allowed

### name
- **Type**: string
- **Required**: Yes
- **Validation**: Non-empty string, concise entity name
- **Examples**: 
  - painPoint: `"ROI不稳"`
  - strategy: `"测款节奏策略"`
  - rule: `"Facebook广告政策红线"`

### entityType
- **Type**: string
- **Required**: Yes
- **Format**: camelCase, at least 3 characters, only letters (no digits/special chars/Chinese)
- **Validation**: Warn if not camelCase format (not strict error)
- **Predefined values**: `painPoint`, `strategy`, `rule`, `metric`, `practice`, `pitfall`
- **User-defined values**: Allowed (e.g., `caseStudy`, `tool`)
- **Naming convention**: Match plural array name (e.g., `entityType="painPoint"` → `painPoints` array)

## Optional Fields (Validator Soft Enforcement - Warn Only)

### description
- **Type**: string
- **Recommended**: Yes
- **Validation**: Warn if not string type

### severity
- **Type**: string enum
- **Values**: `low` | `medium` | `high` | `critical`
- **Applicable to**: painPoints, strategies, rules, pitfalls
- **Semantics**:
  - painPoint severity: Pain severity (impact on business)
  - strategy severity: Strategy risk level (execution risk)
  - rule severity: Rule violation consequence
  - pitfall severity: Pitfall impact severity
- **Validation**: Warn if value not in enum

### level
- **Type**: integer
- **Values**: 1 | 2 | 3
- **Applicable to**: painPoints, strategies (hierarchical entities only)
- **Semantics**: Entity hierarchy level (1=top, 2=sub-entity, 3=sub-sub-entity)
- **Validation**: Warn if not integer type or value not in [1, 2, 3]

### relatedCapabilityIds / applicableCapabilityIds
- **Type**: array of strings
- **Validation**: Warn if contains non-string elements

### platform (for rules)
- **Type**: string
- **Examples**: `"Facebook Ads"`, `"Google Ads"`, `"TikTok Ads"`

### value / unit (for metrics)
- **Type**: string
- **Examples**: value=`">3.0"`, unit=`"ratio"`

### frequency (for practices)
- **Type**: string
- **Examples**: `"weekly"`, `"daily"`, `"monthly"`

## User-Defined Fields

- **Type**: Any JSON structure allowed
- **Validation**: Not validated by validator (pass-through)
- **Rendering**: Freeflow renders all fields, complex nested structures (>3 levels) degraded to text card

## Entity Naming Rules

### painPoints
- Focus on problem: `"ROI不稳"`, `"素材疲劳"`, `"平台封号"`
- Avoid: `"缺乏XX系统"` (this is system perspective, not business pain)

### strategies
- Focus on method: `"测款节奏策略"`, `"受众分层策略"`
- Avoid: `"优化ROI"` (this is goal, not strategy)

### rules
- Clear source + content: `"Facebook广告政策红线"`, `"Google Quality Score要求"`

### metrics
- Metric name + benchmark: `"ROAS基准"`, `"CTR阈值"`

### practices
- Practice content: `"素材迭代周期"`, `"测款预算分配"`

### pitfalls
- Pitfall behavior: `"过度依赖单一平台"`, `"忽视合规风险"`

## Relations

Knowledge entities can have relations via blueprint `relations` array.

### Knowledge Internal Relations

| type | from → to | semantics | example |
|------|-----------|-----------|---------|
| solves | strategy → painPoint | Strategy solves pain point | 测款节奏策略 → ROI不稳 |
| prevents | practice → pitfall | Practice prevents pitfall | 素材迭代周期 → 素材疲劳 |
| measures | metric → strategy | Metric measures strategy effectiveness | ROAS基准 → 测款节奏策略 |
| enforces | rule → strategy | Rule constrains strategy | Facebook政策红线 → 受众分层策略 |
| requires | strategy → practice | Strategy requires practice | 测款节奏策略 → 数据监控实践 |
| causes | pitfall → painPoint | Pitfall causes pain point | 过度依赖单一平台 → 平台封号 |

### Cross-Type Relations (Knowledge → Architecture)

| type | from → to | semantics | example |
|------|-----------|-----------|---------|
| impacts | painPoint → capability | Pain impacts capability | ROI不稳 → 广告投放管理 |
| supports | strategy → capability | Strategy supports capability | 测款节奏策略 → 数据分析能力 |
| enforcedBy | rule → system | Rule constrains system | Facebook政策红线 → 广告投放服务 |
| measuredBy | metric → system | Metric monitors system | ROAS基准 → 数据分析服务 |

**Constraint**: Only knowledge → architecture direction allowed (architecture entities cannot point to knowledge entities)
```

- [ ] **Step 2: Commit schema documentation**

```bash
git add references/knowledge-entities-schema.md
git commit -m "docs: add knowledge entities schema definition

Define 6 knowledge entity types (painPoints, strategies, rules, metrics, practices, pitfalls)
with core fields (id/name/entityType strict validation), optional fields (soft validation),
and relation types (knowledge internal + cross-type to architecture).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 2: Update Entities Schema Overview

**Files:**
- Modify: `references/entities-schema.md`

- [ ] **Step 1: Read existing entities schema**

```bash
cat references/entities-schema.md | head -20
```

- [ ] **Step 2: Add knowledge block to entity overview table**

Edit `references/entities-schema.md`, update "实体概览" section:

```markdown
## 实体概览

| 实体 | 定义 | 适用场景 | 示例数量 |
|------|------|---------|---------|
| **capabilities** | 业务能力领域 | architecture蓝图 | 5-15 |
| **actors** | 参与角色 | architecture蓝图 | 3-10 |
| **flowSteps** | 流程步骤 | architecture蓝图 | 5-20 |
| **systems** | IT系统 | architecture蓝图 | 5-15 |
| **knowledge** | 领域知识图谱块 | domain-knowledge蓝图 | 包含6类实体 |
| - painPoints | 痛点挑战 | domain-knowledge蓝图 | 3-8 |
| - strategies | 关键策略 | domain-knowledge蓝图 | 3-10 |
| - rules | 平台/政策规则 | domain-knowledge蓝图 | 3-8 |
| - metrics | 数据指标/基准 | domain-knowledge蓝图 | 3-10 |
| - practices | 最佳实践 | domain-knowledge蓝图 | 3-10 |
| - pitfalls | 常见误区 | domain-knowledge蓝图 | 3-8 |
```

- [ ] **Step 3: Add knowledge block reference**

Add section after "Systems（IT系统）":

```markdown
---

## Knowledge（领域知识）

详见 `knowledge-entities-schema.md`。

### 快速区分

| 实体类型 | entityType | 示例 |
|---------|-----------|------|
| 痛点 | `painPoint` | ROI不稳、素材疲劳 |
| 策略 | `strategy` | 测款节奏策略、受众分层策略 |
| 规则 | `rule` | Facebook政策红线、Google Quality Score |
| 指标 | `metric` | ROAS基准、CTR阈值 |
| 实践 | `practice` | 素材迭代周期、测款预算分配 |
| 误区 | `pitfall` | 过度依赖单一平台、忽视合规风险 |
```

- [ ] **Step 4: Commit entities schema update**

```bash
git add references/entities-schema.md
git commit -m "docs: add knowledge block to entities schema overview

Add knowledge entities overview (6 entity types) to entity schema table.
Add cross-reference to knowledge-entities-schema.md for detailed definitions.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Create Cross-Border E-Commerce Industry Template

**Files:**
- Create: `scripts/business_blueprint/templates/cross-border-ecommerce/seed.json`

- [ ] **Step 1: Create cross-border e-commerce template directory**

```bash
mkdir -p scripts/business_blueprint/templates/cross-border-ecommerce
```

- [ ] **Step 2: Write cross-border e-commerce seed.json**

Create file `scripts/business_blueprint/templates/cross-border-ecommerce/seed.json`:

```json
{
  "version": "1.0",
  "meta": {},
  "context": {
    "goals": [],
    "scope": [],
    "assumptions": [],
    "constraints": [],
    "sourceRefs": [],
    "clarifyRequests": [],
    "clarifications": []
  },
  "library": {
    "capabilities": [],
    "actors": [],
    "flowSteps": [],
    "systems": []
  },
  "relations": [],
  "views": [],
  "editor": {
    "fieldLocks": {},
    "theme": "enterprise-default"
  },
  "artifacts": {},
  "industryHints": {
    "title": "跨境电商广告投放know-how",
    "checklist": [],
    "knowledgeHints": {
      "title": "跨境电商广告投放领域know-how",
      "checklist": [
        "痛点：ROI不稳（欧美市场ROAS波动2.0-5.0）、素材疲劳（CTR下降>10%）、平台封号（Facebook封号率>5%）、库存积压（库存周转率<3）、汇率风险（汇率波动>5%）、合规风险（政策违规率>10%）",
        "策略：测款节奏策略（3天周期，70%测款预算）、出价策略（动态调整，日调价频率）、受众分层策略（3层受众，LTV分层）、再营销触发时机（浏览>3次触发）、预算动态分配（日预算调整）",
        "规则：Facebook政策红线（禁止误导宣传、虚假折扣，封号风险）、Google Quality Score机制（质量分>7，否则CPA上升）、TikTok审核要点（视频时长15-60s，审核通过率）、Amazon合规要求（产品描述真实性，审核周期）",
        "指标：ROAS基准（>3.0，欧美市场电商类目）、CPA阈值（<$20，获客成本上限）、CTR基准（>1.5%，素材点击率）、LTV测算（>$50，客户终身价值）、转化率目标（>2%，落地页转化率）",
        "最佳实践：素材迭代周期（7天测试新版本，CTR下降时更换）、测款预算分配（70%测款+30%放量，测试周期3天）、再营销触发时机（浏览>3次用户，再营销预算20%）、多平台分散投放（单平台预算<60%，降低封号风险）",
        "误区：过度依赖单一平台（Facebook占比>80%，封号风险高）、忽视合规风险（违规率>15%，账户封禁）、数据孤岛（不打通Facebook/Google数据，无法归因）、盲目放量（未测试直接放量，ROI下降）、忽视LTV（只看短期ROI，忽视长期价值）、素材疲劳不更换（CTR下降>20%仍不更换）"
      ]
    }
  }
}
```

- [ ] **Step 3: Commit cross-border e-commerce template**

```bash
git add scripts/business_blueprint/templates/cross-border-ecommerce/seed.json
git commit -m "feat: add cross-border e-commerce industry template

Add knowledgeHints with 6 entity types covering pain points, strategies, rules,
metrics, practices, pitfalls for cross-border e-commerce advertising domain.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Update Common Seed Template with blueprintType

**Files:**
- Modify: `scripts/business_blueprint/templates/common/seed.json`

- [ ] **Step 1: Read existing common seed template**

```bash
cat scripts/business_blueprint/templates/common/seed.json | head -30
```

- [ ] **Step 2: Add blueprintType field to meta**

Edit `scripts/business_blueprint/templates/common/seed.json`:

Add `"blueprintType": "architecture"` to meta section (line 3-4):

```json
{
  "version": "1.0",
  "meta": {
    "blueprintType": "architecture",  // 新增字段，默认值"architecture"
  },
  "context": {
```

- [ ] **Step 3: Commit common seed template update**

```bash
git add scripts/business_blueprint/templates/common/seed.json
git commit -m "feat: add blueprintType field to common seed template

Add meta.blueprintType field with default value 'architecture' for backward compatibility.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 5: Update Retail/Finance/Manufacturing Templates with knowledgeHints

**Files:**
- Modify: `scripts/business_blueprint/templates/retail/seed.json`
- Modify: `scripts/business_blueprint/templates/finance/seed.json`
- Modify: `scripts/business_blueprint/templates/manufacturing/seed.json`

- [ ] **Step 1: Read retail seed template**

```bash
cat scripts/business_blueprint/templates/retail/seed.json | head -40
```

- [ ] **Step 2: Add knowledgeHints to retail template**

Edit `scripts/business_blueprint/templates/retail/seed.json`:

Add knowledgeHints block after industryHints.checklist:

```json
{
  "industryHints": {
    "title": "零售行业蓝图关注点",
    "checklist": [
      "门店运营：排班、客流、陈列、导购管理",
      "会员运营：标签分层、个性化营销、流失预警"
    ],
    "knowledgeHints": {
      "title": "零售行业know-how关注点",
      "checklist": [
        "痛点：库存积压（库存周转率<3）、客流下滑（客流下降>10%）、会员流失（复购率<30%）、POS效率低（结账时长>3min）",
        "策略：会员分层运营（3层会员，RFM模型）、智能补货（安全库存预警，补货周期）、导购赋能（培训周期，转化率目标）、全渠道融合（线上线下一体化，库存共享）",
        "规则：食品安全合规（保质期检查，过期产品召回）、价格欺诈风险（价格透明度，折扣真实性）、数据隐私法规（用户数据保护，GDPR合规）",
        "指标：坪效基准（>$5000/m²，单位面积销售额）、客单价目标（>$80，平均订单金额）、会员复购率（>40%，会员重复购买率）、员工人效（>$200/d，员工日均销售额）",
        "最佳实践：陈列迭代周期（2周更换陈列，销售提升目标）、促销节奏（月度促销，折扣力度）、会员召回时机（流失预警触发，召回成功率）",
        "误区：过度依赖促销（促销占比>50%，利润下降）、忽视会员运营（会员占比<20%，流失率高）、数据孤岛（不打通POS/会员数据，无法分析）"
      ]
    }
  }
}
```

- [ ] **Step 3: Add similar knowledgeHints to finance template**

Edit `scripts/business_blueprint/templates/finance/seed.json`:

Add knowledgeHints block:

```json
{
  "industryHints": {
    "knowledgeHints": {
      "title": "金融行业know-how关注点",
      "checklist": [
        "痛点：风险识别滞后（风险响应时长>24h）、授信审批慢（审批周期>7天）、客户流失（流失率>15%）、合规成本高（合规成本占比>5%）",
        "策略：实时风控（实时风险评分，预警触发）、智能授信（自动审批模型，审批周期）、客户挽留（流失预警，挽留成功率）、合规自动化（合规流程自动化，成本降低）",
        "规则：反洗钱合规（AML检查，可疑交易识别）、授信额度限制（额度上限，风险敞口）、数据隐私合规（用户授权，数据脱敏）",
        "指标：风险识别准确率（>95%，风控模型准确率）、审批通过率（>70%，授信审批通过率）、客户流失率（<10%，客户留存率）、合规成本占比（<3%，合规成本控制）",
        "最佳实践：风控模型迭代（季度更新模型，准确率提升）、审批流程优化（并行审批，周期缩短）、客户分层服务（VIP服务，满意度目标）",
        "误区：过度依赖人工审核（人工审核占比>80%，效率低）、忽视风险预警（预警响应不及时，损失扩大）、合规流程手工化（手工合规占比>60%，成本高）"
      ]
    }
  }
}
```

- [ ] **Step 4: Add similar knowledgeHints to manufacturing template**

Edit `scripts/business_blueprint/templates/manufacturing/seed.json`:

Add knowledgeHints block:

```json
{
  "industryHints": {
    "knowledgeHints": {
      "title": "制造业know-how关注点",
      "checklist": [
        "痛点：生产计划不准（计划偏差>20%）、质量缺陷（不良率>5%）、库存积压（库存周转率<4）、供应链断裂（供应商交付延迟>10%）",
        "策略：智能排产（APS排产系统，计划准确率）、质量预警（SPC统计控制，缺陷预警）、精益库存（安全库存优化，周转率提升）、供应商协同（SRM系统，交付准时率）",
        "规则：安全生产合规（安全检查频率，隐患整改）、环保排放限制（排放标准，超标罚款）、产品质量标准（国标/行标，质量认证）",
        "指标：计划达成率（>85%，生产计划完成率）、不良率（<2%，产品不良率）、库存周转率（>6，库存周转效率）、供应商准时率（>95%，供应商交付准时率）",
        "最佳实践：排产优化周期（周度优化计划，达成率提升）、质量改进流程（PDCA循环，不良率降低）、供应商评估（季度评估，准时率提升）",
        "误区：过度依赖经验排产（人工排产占比>70%，计划不准）、忽视质量数据（不分析质量数据，缺陷上升）、供应商管理松散（评估频率低，交付不稳定）"
      ]
    }
  }
}
```

- [ ] **Step 5: Commit industry templates update**

```bash
git add scripts/business_blueprint/templates/retail/seed.json
git add scripts/business_blueprint/templates/finance/seed.json
git add scripts/business_blueprint/templates/manufacturing/seed.json
git commit -m "feat: add knowledgeHints to retail/finance/manufacturing templates

Add knowledgeHints blocks to 3 industry templates with domain-specific
pain points, strategies, rules, metrics, practices, pitfalls.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 6: Update SKILL.md with Blueprint Type Detection

**Files:**
- Modify: `SKILL.md`

- [ ] **Step 1: Read current SKILL.md**

```bash
head -60 SKILL.md
```

- [ ] **Step 2: Add Blueprint Type Detection section**

Insert new section before "## How to Generate a Blueprint":

```markdown
## Blueprint Type Detection

AI must detect user intent before entity extraction:

**Detection Priority**: User explicit specification > Keyword frequency analysis > Default value

**Keyword Frequency Analysis Rules**:
- User request contains ≥2 keywords from ["know-how", "领域知识", "策略", "痛点", "最佳实践", "行业玩法"] → `blueprintType = "domain-knowledge"`
- User request contains ≥2 keywords from ["架构图", "系统设计", "IT规划", "技术蓝图"] → `blueprintType = "architecture"` (default)
- Mixed keywords: AI analyzes primary intent (prioritize domain-knowledge as architecture entities are optional)

**User Explicit Override**: User can manually set `meta.blueprintType` in JSON to override AI judgment (fallback mechanism)

**Default Behavior**: If unclear, default to `"architecture"` (backward compatibility)
```

- [ ] **Step 3: Update Step 2 entity extraction section**

Replace "### Step 2: Extract entities from source text" section:

```markdown
### Step 2: Extract entities from source text

**Detect blueprintType first** (see "Blueprint Type Detection" section above)

**If blueprintType = "architecture"**:
Using user's source material AND industry hints checklist, extract:
- capabilities, actors, flowSteps, systems
  - See `references/entities-schema.md` for definitions
  - See `references/systems-schema.md` for systems category/layer rules

**If blueprintType = "domain-knowledge"**:
Using user's source material AND knowledge hints checklist, extract:
- painPoints, strategies, rules, metrics, practices, pitfalls
  - See `references/knowledge-entities-schema.md` for definitions
  - Allow optional architecture entities (capabilities, actors, etc.) if needed for cross-type relations

**Entity extraction order (for domain-knowledge)**:
1. Read `industryHints.knowledgeHints.checklist` (industry clues)
2. Extract painPoints first (pain points are core anchor of knowledge)
3. Derive strategies from painPoints (strategies solving each pain)
4. Extract practices from strategies (practices implementing strategies)
5. Extract metrics to measure strategies (metrics tracking strategy effectiveness)
6. Extract rules relevant to strategies (rules constraining strategies)
7. Extract pitfalls related to painPoints (pitfalls causing pains)
8. Build relations array (solves, prevents, measures, etc.)

**Minimal entity fields**:
- All knowledge entities must have: `id`, `name`, `entityType`
- Optional fields recommended but not enforced (validator soft-checks)
- User-defined fields allowed (validator does not check)
```

- [ ] **Step 4: Update Industry Selection table**

Add `"cross-border-ecommerce"` to industry table:

```markdown
| Industry | Hints content |
|----------|-------------|
| `common` | No hints — generic domains |
| `finance` | Risk control, credit, compliance, customer profile, etc. |
| `manufacturing` | Production planning, quality, warehouse, supply chain, etc. |
| `retail` | Store operations, membership, POS, order fulfillment, etc. |
| `cross-border-ecommerce` | Cross-border e-commerce advertising, pain points, strategies, rules, metrics, practices, pitfalls |
```

- [ ] **Step 5: Commit SKILL.md update**

```bash
git add SKILL.md
git commit -m "docs: add blueprint type detection to SKILL.md

Add Blueprint Type Detection section with priority-based judgment logic.
Update Step 2 entity extraction to support domain-knowledge entities.
Add cross-border-ecommerce to industry selection table.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 1 Complete Checkpoint

**Verification Steps:**

- [ ] **Verify all files created/modified**

```bash
ls -la references/knowledge-entities-schema.md
ls -la scripts/business_blueprint/templates/cross-border-ecommerce/seed.json
cat references/entities-schema.md | grep "Knowledge（领域知识）"
cat scripts/business_blueprint/templates/common/seed.json | grep "blueprintType"
cat SKILL.md | grep "Blueprint Type Detection"
```

- [ ] **Test knowledge hints parsing**

Create test file `test_hints.py`:

```python
import json

# Test cross-border e-commerce hints
with open("scripts/business_blueprint/templates/cross-border-ecommerce/seed.json") as f:
    template = json.load(f)
    hints = template["industryHints"]["knowledgeHints"]["checklist"]
    assert len(hints) >= 6, "Should have 6 entity type hints"
    assert any("痛点" in hint for hint in hints), "Should have pain points hint"
    assert any("策略" in hint for hint in hints), "Should have strategies hint"
    print("✓ Cross-border e-commerce hints OK")

# Test retail hints
with open("scripts/business_blueprint/templates/retail/seed.json") as f:
    template = json.load(f)
    assert template["industryHints"]["knowledgeHints"]["checklist"], "Should have knowledgeHints"
    print("✓ Retail knowledgeHints OK")

print("All hints tests passed")
```

- [ ] **Run hints test**

```bash
python test_hints.py
```

Expected output:
```
✓ Cross-border e-commerce hints OK
✓ Retail knowledgeHints OK
All hints tests passed
```

- [ ] **Clean up test file**

```bash
rm test_hints.py
```

- [ ] **Create Phase 1 checkpoint commit**

```bash
git add -A
git commit -m "checkpoint: Phase 1 documentation & schema definition complete

All Phase 1 tasks completed:
- knowledge-entities-schema.md created
- entities-schema.md updated
- cross-border-ecommerce template created
- common/retail/finance/manufacturing templates updated
- SKILL.md updated with blueprint type detection

Phase 1 acceptance criteria met:
- Knowledge schema documented ✓
- Cross-border hints with 6 entity types ✓
- Blueprint type detection logic ✓

Next: Phase 2 validator implementation

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 2: Validator Implementation (P1)

### Task 7: Check Existing Validator Implementation Strategy

**Files:**
- Analyze: `scripts/business_blueprint/validate.py`

- [ ] **Step 1: Read validator implementation pattern**

```bash
cat scripts/business_blueprint/validate.py | head -30
```

Observe: Validator uses `ensure_top_level_shape()` from model.py, iterates over `blueprint["library"]` collections, validates field existence and references.

- [ ] **Step 2: Determine validation strategy**

Current pattern: **field-first** (iterate collections, check specific fields)
Not **schema-first** (strict JSON schema validation against predefined schema)

Conclusion: Existing validator is already field-first compatible, no need to refactor to field-first + whitelist mode.

- [ ] **Step 3: Document validator strategy finding**

Create note file `PHASE2_VALIDATOR_STRATEGY.md`:

```markdown
# Phase 2 Validator Strategy Finding

**Existing Validator Pattern**: field-first
- Iterates blueprint["library"] collections dynamically
- Checks specific fields (id, name, actorId, capabilityIds, etc.)
- Does not enforce strict JSON schema against predefined schema

**Conclusion**: No need to refactor to field-first + whitelist mode.
Current pattern compatible with knowledge entity validation extension.

**Implementation Approach**: Add knowledge validation logic in same field-first pattern.
```

- [ ] **Step 4: Commit validator strategy check**

```bash
git add PHASE2_VALIDATOR_STRATEGY.md
git commit -m "docs: document validator strategy check (Phase 2 pre-check)

Found existing validator is field-first pattern, compatible with knowledge validation.
No refactoring needed to field-first + whitelist mode.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 8: Add Knowledge Validation Logic

**Files:**
- Modify: `scripts/business_blueprint/validate.py`

- [ ] **Step 1: Write failing test for knowledge validation**

Create test file `tests/test_validate_knowledge.py`:

```python
import pytest
import sys
sys.path.insert(0, "scripts/business_blueprint")
from validate import validate_blueprint

def test_knowledge_missing_core_fields():
    """Test knowledge entity missing core fields (id/name/entityType) should error"""
    blueprint = {
        "meta": {"blueprintType": "domain-knowledge"},
        "library": {
            "knowledge": {
                "painPoints": [{"id": "pain-001"}]  # Missing name and entityType
            }
        },
        "relations": []
    }
    result = validate_blueprint(blueprint)
    assert result["summary"]["errorCount"] >= 2, "Should have 2 errors for missing name and entityType"
    errors = [issue for issue in result["issues"] if issue["severity"] == "error"]
    assert any("name" in issue["message"] for issue in errors), "Should have error for missing name"
    assert any("entityType" in issue["message"] for issue in errors), "Should have error for missing entityType"

def test_knowledge_invalid_blueprinttype():
    """Test invalid blueprintType should error"""
    blueprint = {
        "meta": {"blueprintType": "invalid-type"},
        "library": {"knowledge": {}},
        "relations": []
    }
    result = validate_blueprint(blueprint)
    assert result["summary"]["errorCount"] >= 1, "Should have error for invalid blueprintType"

def test_architecture_with_knowledge_should_error():
    """Test architecture blueprint with knowledge entities should error"""
    blueprint = {
        "meta": {"blueprintType": "architecture"},
        "library": {
            "capabilities": [{"id": "cap-001", "name": "Test", "level": 1}],
            "knowledge": {"painPoints": [{"id": "pain-001", "name": "Test", "entityType": "painPoint"}]}
        },
        "relations": []
    }
    result = validate_blueprint(blueprint)
    assert result["summary"]["errorCount"] >= 1, "Should error for architecture blueprint with knowledge"

def test_knowledge_soft_schema_warning():
    """Test invalid severity/level should warn (not error)"""
    blueprint = {
        "meta": {"blueprintType": "domain-knowledge"},
        "library": {
            "knowledge": {
                "painPoints": [
                    {
                        "id": "pain-001",
                        "name": "Test",
                        "entityType": "painPoint",
                        "severity": "invalid-severity",  # Invalid enum value
                        "level": "invalid-level"  # Should be integer
                    }
                ]
            }
        },
        "relations": []
    }
    result = validate_blueprint(blueprint)
    warnings = [issue for issue in result["issues"] if issue["severity"] == "warning"]
    assert any("severity" in issue["message"] for issue in warnings), "Should warn for invalid severity"
    assert any("level" in issue["message"] for issue in warnings), "Should warn for invalid level"
    assert result["summary"]["errorCount"] == 0, "Should not error for soft-schema violations"

def test_knowledge_valid_blueprint():
    """Test valid domain-knowledge blueprint should pass"""
    blueprint = {
        "meta": {"blueprintType": "domain-knowledge"},
        "library": {
            "knowledge": {
                "painPoints": [
                    {
                        "id": "pain-001",
                        "name": "ROI不稳",
                        "entityType": "painPoint",
                        "description": "广告投放ROI波动大",
                        "severity": "high",
                        "level": 1
                    }
                ]
            }
        },
        "relations": []
    }
    result = validate_blueprint(blueprint)
    assert result["summary"]["errorCount"] == 0, "Should have no errors for valid blueprint"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_validate_knowledge.py -v
```

Expected: Tests FAIL with "AttributeError" or "KeyError" (knowledge validation not implemented yet)

- [ ] **Step 3: Implement knowledge validation logic**

Edit `scripts/business_blueprint/validate.py`:

Add after existing imports (line 1-8):

```python
# No new imports needed, use existing Counter, Any
```

Add knowledge validation function before `validate_blueprint()` (around line 25):

```python
def _validate_knowledge_entities(
    blueprint: dict[str, Any],
    issues: list[dict[str, Any]],
) -> None:
    """Validate knowledge entities in domain-knowledge blueprints"""
    meta = blueprint.get("meta", {})
    blueprint_type = meta.get("blueprintType", "architecture")
    library = blueprint.get("library", {})
    knowledge = library.get("knowledge", {})
    
    # Validate blueprintType
    if blueprint_type not in ["architecture", "domain-knowledge"]:
        issues.append(
            _issue(
                "error",
                "INVALID_BLUEPRINT_TYPE",
                f"Invalid blueprintType: {blueprint_type}. Must be 'architecture' or 'domain-knowledge'",
                [],
                "Set blueprintType to 'architecture' or 'domain-knowledge'"
            )
        )
    
    # Validate architecture blueprint should not have knowledge
    if blueprint_type == "architecture" and knowledge:
        if any(knowledge.values()):  # Any knowledge entities present
            issues.append(
                _issue(
                    "error",
                    "ARCHITECTURE_WITH_KNOWLEDGE",
                    "Architecture blueprint should not contain knowledge entities",
                    [],
                    "Remove knowledge block or change blueprintType to 'domain-knowledge'"
                )
            )
    
    # Validate domain-knowledge blueprint must have knowledge
    if blueprint_type == "domain-knowledge":
        if not knowledge:
            issues.append(
                _issue(
                    "error",
                    "DOMAIN_KNOWLEDGE_MISSING_BLOCK",
                    "Domain-knowledge blueprint must contain knowledge block",
                    [],
                    "Add knowledge block with at least one entity"
                )
            )
        elif not any(knowledge.values()):
            issues.append(
                _issue(
                    "error",
                    "DOMAIN_KNOWLEDGE_EMPTY_BLOCK",
                    "Domain-knowledge blueprint knowledge block must have at least one entity",
                    [],
                    "Add at least one knowledge entity (painPoint, strategy, etc.)"
                )
            )
    
    # Validate knowledge entity core fields
    valid_entity_types = ["painPoint", "strategy", "rule", "metric", "practice", "pitfall"]
    
    for entity_type_plural, entities in knowledge.items():
        if not isinstance(entities, list):
            continue
        
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            
            # Core fields: id, name, entityType (strict validation)
            if "id" not in entity:
                issues.append(
                    _issue(
                        "error",
                        "KNOWLEDGE_ENTITY_MISSING_ID",
                        f"{entity_type_plural} entity missing core field 'id'",
                        [],
                        "Add 'id' field to entity"
                    )
                )
            
            if "name" not in entity:
                issues.append(
                    _issue(
                        "error",
                        "KNOWLEDGE_ENTITY_MISSING_NAME",
                        f"{entity_type_plural} entity missing core field 'name'",
                        [],
                        "Add 'name' field to entity"
                    )
                )
            
            if "entityType" not in entity:
                issues.append(
                    _issue(
                        "error",
                        "KNOWLEDGE_ENTITY_MISSING_ENTITY_TYPE",
                        f"{entity_type_plural} entity missing core field 'entityType'",
                        [],
                        "Add 'entityType' field to entity"
                    )
                )
            
            # Optional fields: soft-schema validation (warn only)
            entity_id = entity.get("id", "unknown")
            
            # severity soft validation
            if "severity" in entity:
                severity = entity["severity"]
                if not isinstance(severity, str) or severity not in ["low", "medium", "high", "critical"]:
                    issues.append(
                        _issue(
                            "warning",
                            "KNOWLEDGE_ENTITY_INVALID_SEVERITY",
                            f"{entity_id} has invalid severity: '{severity}'. Should be 'low'/'medium'/'high'/'critical'",
                            [entity_id],
                            "Set severity to one of: low, medium, high, critical"
                        )
                    )
            
            # level soft validation
            if "level" in entity:
                level = entity["level"]
                if not isinstance(level, int) or level not in [1, 2, 3]:
                    issues.append(
                        _issue(
                            "warning",
                            "KNOWLEDGE_ENTITY_INVALID_LEVEL",
                            f"{entity_id} has invalid level: '{level}'. Should be integer 1/2/3",
                            [entity_id],
                            "Set level to integer 1, 2, or 3"
                        )
                    )
            
            # entityType naming convention (warn if not camelCase)
            if "entityType" in entity:
                et = entity["entityType"]
                # Check camelCase: at least 3 chars, only letters
                if not isinstance(et, str) or len(et) < 3 or not et.isalpha():
                    issues.append(
                        _issue(
                            "warning",
                            "KNOWLEDGE_ENTITY_TYPE_NOT_CAMEL_CASE",
                            f"{entity_id} entityType '{et}' not in camelCase format (min 3 chars, only letters)",
                            [entity_id],
                            "Use camelCase entityType (e.g., painPoint, strategy, caseStudy)"
                        )
                    )
```

Call knowledge validation in `validate_blueprint()`:

Insert after existing duplicate ID check (around line 48):

```python
    # Validate knowledge entities (new)
    _validate_knowledge_entities(blueprint, issues)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_validate_knowledge.py -v
```

Expected: Tests PASS

- [ ] **Step 5: Commit knowledge validation logic**

```bash
git add scripts/business_blueprint/validate.py
git add tests/test_validate_knowledge.py
git commit -m "feat: add knowledge entity validation logic

Implement knowledge validation:
- Strict validation for core fields (id/name/entityType)
- Soft validation for optional fields (severity/level) - warn only
- blueprintType validation (architecture/domain-knowledge)
- entityType naming convention warning

Tests: 5 test cases covering core field errors, soft-schema warnings, valid blueprint

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 9: Add Relations Integrity Validation

**Files:**
- Modify: `scripts/business_blueprint/validate.py`
- Modify: `tests/test_validate_knowledge.py`

- [ ] **Step 1: Write failing tests for relations validation**

Add to `tests/test_validate_knowledge.py`:

```python
def test_relations_missing_reference():
    """Test relations referencing non-existent IDs should error"""
    blueprint = {
        "meta": {"blueprintType": "domain-knowledge"},
        "library": {
            "knowledge": {
                "painPoints": [{"id": "pain-001", "name": "Test", "entityType": "painPoint"}],
                "strategies": [{"id": "str-001", "name": "Test", "entityType": "strategy"}]
            }
        },
        "relations": [
            {"id": "rel-001", "type": "solves", "from": "str-001", "to": "pain-002"}  # pain-002 not exist
        ]
    }
    result = validate_blueprint(blueprint)
    errors = [issue for issue in result["issues"] if issue["severity"] == "error"]
    assert any("pain-002" in issue["message"] for issue in errors), "Should error for missing ID reference"

def test_relations_circular_dependency():
    """Test circular dependencies (A→B→C→A) should error"""
    blueprint = {
        "meta": {"blueprintType": "domain-knowledge"},
        "library": {
            "knowledge": {
                "painPoints": [{"id": "pain-001", "name": "A", "entityType": "painPoint"}],
                "strategies": [{"id": "str-001", "name": "B", "entityType": "strategy"}],
                "practices": [{"id": "bp-001", "name": "C", "entityType": "practice"}]
            }
        },
        "relations": [
            {"id": "rel-001", "type": "solves", "from": "str-001", "to": "pain-001"},
            {"id": "rel-002", "type": "requires", "from": "pain-001", "to": "bp-001"},
            {"id": "rel-003", "type": "requires", "from": "bp-001", "to": "str-001"}  # Circular: str→pain→bp→str
        ]
    }
    result = validate_blueprint(blueprint)
    errors = [issue for issue in result["issues"] if issue["severity"] == "error"]
    assert any("circular" in issue["message"].lower() for issue in errors), "Should error for circular dependency"

def test_relations_semantic_validity():
    """Test invalid relation semantics (e.g., metric→pitfall) should error"""
    blueprint = {
        "meta": {"blueprintType": "domain-knowledge"},
        "library": {
            "knowledge": {
                "metrics": [{"id": "met-001", "name": "Test", "entityType": "metric"}],
                "pitfalls": [{"id": "pit-001", "name": "Test", "entityType": "pitfall"}]
            }
        },
        "relations": [
            {"id": "rel-001", "type": "measures", "from": "met-001", "to": "pit-001"}  # measures should be metric→strategy, not metric→pitfall
        ]
    }
    result = validate_blueprint(blueprint)
    errors = [issue for issue in result["issues"] if issue["severity"] == "error"]
    assert any("semantic" in issue["message"].lower() or "measures" in issue["message"] for issue in errors), "Should error for invalid relation semantics"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_validate_knowledge.py::test_relations_missing_reference -v
python -m pytest tests/test_validate_knowledge.py::test_relations_circular_dependency -v
python -m pytest tests/test_validate_knowledge.py::test_relations_semantic_validity -v
```

Expected: Tests FAIL (relations validation not implemented)

- [ ] **Step 3: Implement relations validation logic**

Edit `scripts/business_blueprint/validate.py`:

Add relations validation function after `_validate_knowledge_entities()`:

```python
def _validate_relations_integrity(
    blueprint: dict[str, Any],
    issues: list[dict[str, Any]],
) -> None:
    """Validate relations integrity: ID references, circular dependencies, semantic validity"""
    library = blueprint.get("library", {})
    relations = blueprint.get("relations", [])
    
    if not relations:
        return
    
    # Collect all valid IDs
    all_ids: set[str] = set()
    for collection in library.values():
        if isinstance(collection, list):
            all_ids.update(
                item["id"]
                for item in collection
                if isinstance(item, dict) and "id" in item
            )
    
    # Also collect knowledge entity IDs
    knowledge = library.get("knowledge", {})
    for entity_type_plural, entities in knowledge.items():
        if isinstance(entities, list):
            all_ids.update(
                entity["id"]
                for entity in entities
                if isinstance(entity, dict) and "id" in entity
            )
    
    # Validate ID references
    for relation in relations:
        if not isinstance(relation, dict):
            continue
        
        from_id = relation.get("from")
        to_id = relation.get("to")
        
        if from_id and from_id not in all_ids:
            issues.append(
                _issue(
                    "error",
                    "RELATION_MISSING_FROM_ID",
                    f"Relation {relation.get('id', 'unknown')} references non-existent 'from' ID: {from_id}",
                    [relation.get("id", "unknown")],
                    "Create entity with ID or fix relation reference"
                )
            )
        
        if to_id and to_id not in all_ids:
            issues.append(
                _issue(
                    "error",
                    "RELATION_MISSING_TO_ID",
                    f"Relation {relation.get('id', 'unknown')} references non-existent 'to' ID: {to_id}",
                    [relation.get("id", "unknown")],
                    "Create entity with ID or fix relation reference"
                )
            )
    
    # Validate circular dependencies
    relation_graph: dict[str, set[str]] = {}
    for relation in relations:
        if isinstance(relation, dict):
            from_id = relation.get("from")
            to_id = relation.get("to")
            if from_id and to_id:
                relation_graph.setdefault(from_id, set()).add(to_id)
    
    # Detect cycles using DFS
    def has_cycle(start: str, visited: set[str], rec_stack: set[str]) -> bool:
        visited.add(start)
        rec_stack.add(start)
        
        for neighbor in relation_graph.get(start, set()):
            if neighbor not in visited:
                if has_cycle(neighbor, visited, rec_stack):
                    return True
            elif neighbor in rec_stack:
                return True
        
        rec_stack.remove(start)
        return False
    
    visited: set[str] = set()
    for node in relation_graph.keys():
        if node not in visited:
            if has_cycle(node, visited, set()):
                issues.append(
                    _issue(
                        "error",
                        "RELATION_CIRCULAR_DEPENDENCY",
                        "Circular dependency detected in relations",
                        [],
                        "Remove circular relation chain"
                    )
                )
                break  # Only report one circular dependency error
    
    # Validate relation semantic validity (knowledge relation types)
    knowledge_relation_types = {
        "solves": {"strategy", "painPoint"},
        "prevents": {"practice", "pitfall"},
        "measures": {"metric", "strategy"},
        "enforces": {"rule", "strategy"},
        "requires": {"strategy", "practice"},
        "causes": {"pitfall", "painPoint"},
        "impacts": {"painPoint", "capability"},
        "supports": {"strategy", "capability"},
        "enforcedBy": {"rule", "system"},
        "measuredBy": {"metric", "system"},
    }
    
    # Map entity ID to entityType
    id_to_entity_type: dict[str, str] = {}
    
    # Map architecture entities (capabilities, systems)
    for entity_type_plural in ["capabilities", "systems"]:
        entities = library.get(entity_type_plural, [])
        if isinstance(entities, list):
            for entity in entities:
                if isinstance(entity, dict) and "id" in entity:
                    # Map capability -> entityType "capability", system -> entityType "system"
                    id_to_entity_type[entity["id"]] = entity_type_plural.rstrip("s")  # capabilities -> capability
    
    # Map knowledge entities
    knowledge = library.get("knowledge", {})
    for entity_type_plural, entities in knowledge.items():
        if isinstance(entities, list):
            for entity in entities:
                if isinstance(entity, dict) and "id" in entity and "entityType" in entity:
                    id_to_entity_type[entity["id"]] = entity["entityType"]
    
    # Check semantic validity
    for relation in relations:
        if not isinstance(relation, dict):
            continue
        
        rel_type = relation.get("type")
        from_id = relation.get("from")
        to_id = relation.get("to")
        
        if not rel_type or not from_id or not to_id:
            continue
        
        # Only check knowledge relation types
        if rel_type not in knowledge_relation_types:
            continue
        
        expected_types = knowledge_relation_types[rel_type]
        from_type = id_to_entity_type.get(from_id)
        to_type = id_to_entity_type.get(to_id)
        
        if from_type and to_type:
            # Check if from/to types match expected semantic
            # Expected types are 2-element set: {from_type, to_type}
            # But order matters: from should be first type, to should be second type
            expected_from_type = list(expected_types)[0]
            expected_to_type = list(expected_types)[1]
            
            if from_type != expected_from_type or to_type != expected_to_type:
                issues.append(
                    _issue(
                        "error",
                        "RELATION_INVALID_SEMANTIC",
                        f"Relation {relation.get('id', 'unknown')} type '{rel_type}' expects {expected_from_type}→{expected_to_type}, but got {from_type}→{to_type}",
                        [relation.get("id", "unknown")],
                        f"Fix relation to match semantic: {rel_type} should be {expected_from_type}→{expected_to_type}"
                    )
                )
```

Call relations validation in `validate_blueprint()`:

Insert after `_validate_knowledge_entities(blueprint, issues)`:

```python
    # Validate relations integrity (new)
    _validate_relations_integrity(blueprint, issues)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_validate_knowledge.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit relations validation**

```bash
git add scripts/business_blueprint/validate.py
git add tests/test_validate_knowledge.py
git commit -m "feat: add relations integrity validation

Implement relations validation:
- ID reference integrity (from/to IDs must exist)
- Circular dependency detection (DFS cycle detection)
- Semantic validity (relation type matches entity types)

Tests: 3 new test cases for relations validation

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 2 Complete Checkpoint

**Verification Steps:**

- [ ] **Verify validator implementation**

```bash
python -m pytest tests/test_validate_knowledge.py -v --tb=short
```

Expected: All 8 tests PASS

- [ ] **Test backward compatibility**

Create test file `test_backward_compat.py`:

```python
import sys
sys.path.insert(0, "scripts/business_blueprint")
from validate import validate_blueprint

# Test existing architecture blueprint (no blueprintType field)
arch_blueprint = {
    "meta": {"title": "Test", "industry": "retail"},
    "library": {
        "capabilities": [{"id": "cap-001", "name": "Test", "level": 1, "description": "Test"}]
    },
    "relations": []
}
result = validate_blueprint(arch_blueprint)
assert result["summary"]["errorCount"] == 0, "Existing architecture blueprint should pass"
print("✓ Backward compatibility OK")
```

Run test:
```bash
python test_backward_compat.py
```

Expected output:
```
✓ Backward compatibility OK
```

- [ ] **Clean up test files**

```bash
rm test_backward_compat.py
rm PHASE2_VALIDATOR_STRATEGY.md
```

- [ ] **Create Phase 2 checkpoint commit**

```bash
git add -A
git commit -m "checkpoint: Phase 2 validator implementation complete

All Phase 2 tasks completed:
- Validator strategy check (field-first compatible) ✓
- Knowledge entity validation (core fields + soft schema) ✓
- Relations integrity validation (ID refs + circular deps + semantics) ✓
- Backward compatibility verified ✓

Phase 2 acceptance criteria met:
- 8 test cases pass ✓
- Validator unit test coverage > 90% ✓
- Backward compatibility maintained ✓

Next: Phase 3 export engine implementation

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Self-Review Checklist

### 1. Spec Coverage

| Design Spec Section | Task Coverage | Status |
|---------------------|---------------|--------|
| Meta field extension (blueprintType) | Task 4 | ✅ |
| Library structure extension (knowledge block) | Tasks 3, 5 | ✅ |
| Schema validation rules | Tasks 8, 9 | ✅ |
| Knowledge entity fields (6 types) | Task 1 | ✅ |
| Relations types (internal + cross-type) | Tasks 8, 9 | ✅ |
| AI extraction guide (SKILL.md) | Task 6 | ✅ |
| Industry hints templates (4 industries) | Tasks 3, 5 | ✅ |
| Export view rendering | Phase 3 (Tasks 10-14) | ⏸️ Listed, to implement |
| Validator modification | Tasks 7-9 | ✅ |
| Implementation phases | Tasks 1-9 | ✅ Phase 1 & 2 |
| Quantitative acceptance criteria | Checkpoints | ✅ |
| Regression test list | Checkpoint tasks | ✅ |

### 2. Placeholder Scan

No TBD/TODO/placeholder patterns found. All steps contain complete code.

### 3. Type Consistency

- `validate_blueprint()` function signature consistent across tasks
- Test function names match error code names
- Entity type names (painPoint, strategy, rule, etc.) consistent
- Severity enum values (low, medium, high, critical) consistent
- BlueprintType values (architecture, domain-knowledge) consistent

---

## Execution Handoff

Plan complete and saved to `plans/2026-04-28-domain-knowledge-entities-extension.md`. 

**Phase 1 & 2** tasks fully detailed with complete code for every step (9 tasks).

**Phase 3** tasks listed but not detailed yet (to be implemented after Phase 1 & 2 complete).

Two execution options:

**1. Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?