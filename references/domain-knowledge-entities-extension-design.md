# Business Blueprint Skill: Domain-Knowledge实体扩展设计

**日期**: 2026-04-28
**设计者**: Claude Code Session
**目标**: 扩展business-blueprint skill实体定义，支持domain-knowledge蓝图（痛点、策略、规则、指标、实践、误区），保持向后兼容，确保IR质量和灵活性。

---

## 问题诊断

### 现状
business-blueprint skill当前实体定义固化在architecture视角：
- 实体类型：`capabilities`（能力）、`actors`（角色）、`flowSteps`（流程）、`systems`（系统）
- 输出形式：架构分层图、泳道流程图、系统支撑关系图
- 适用场景：售前方案设计、IT系统规划、业务流程梳理

### 缺失
用户需要domain-knowledge知识图谱，用于展示业务洞察：
- 痛点挑战、关键策略、平台规则、数据指标、最佳实践、常见误区
- 用于pitch客户时展示"我们懂这个领域"的专业度
- 实体类型固化导致AI只能提取系统架构视角内容

### 根本原因
skill设计时将"业务蓝图"等同于"系统架构蓝图"，实体定义固化在IT系统视角，缺失业务洞察实体。

---

## 设计决策记录

### 决策1：蓝图类型分离方式
**选择**: 方案A - 同一JSON schema，AI自动判断填充哪些实体块
**理由**: 保持IR-First Pipeline设计哲学（一个canonical JSON），AI自动判断意图符合渐进式披露原则，向后兼容无需用户显式参数。

### 决策2：实体关联关系方式
**选择**: 方案A - 显式relations数组
**理由**: 保持IR一致性（所有关系都在relations数组），下游工具只需一套关系处理逻辑。

### 决策3：跨类型关联约束
**选择**: 方案C - 单向关联（knowledge可引用architecture，反之不行）
**补充**: 根据实际业务场景来，如果不需要architecture，也不要强加上
**理由**: knowledge实体通常描述"如何优化现有架构"，单向关联符合业务语义，不强加关联体现实用主义。

### 决策4：层级字段设计
**选择**: 方案B - 仅painPoints和strategies有level字段
**理由**: 保留必要层级表达（痛点、策略可能有父子关系），其他实体（规则、指标、实践、误区）原子化无需层级。

### 决策5：分级字段统一
**选择**: 方案A - 统一为severity字段
**理由**: 简化schema和AI理解，"严重程度"本质是同一个概念。

### 决策6：导出视图策略
**选择**: 方案A - freeflow为默认视图
**理由**: freeflow足够灵活，只需定义视觉样式，无需开发独立knowledge-graph视图模板，最小化实现成本。

### 决策7：行业hints组织
**选择**: 方案A - 独立knowledgeHints块，复用checklist结构
**理由**: 最简化扩展，AI从checklist的"痛点：..."描述中自动解析实体类型线索。

### 决策8：实现路径
**选择**: 路径2 - schema扩展 + validator改造
**理由**: 从最终效果和质量出发，schema强约束确保IR质量，validator作为质量闸门，下游工具统一处理，长期演进能力强。

### 决策9：schema约束强度
**选择**: 强核心 + 弱扩展
**理由**: 方便降级（用户只需填id/name/entityType），灵活扩展（允许任意额外字段），内容布局好（freeflow读取所有字段渲染）。

---

## 设计规范

### 一、JSON Schema扩展

#### 1. meta字段扩展

新增可选的`blueprintType`标识：

```json
{
  "meta": {
    "title": "跨境电商广告投放领域know-how大图",
    "industry": "cross-border-ecommerce",
    "blueprintType": "domain-knowledge",  // 新增可选字段
    // 默认值："architecture"（向后兼容）
    // 枚举值：architecture | domain-knowledge
    "revisionId": "rev-20260428-01",
    "lastModifiedAt": "2026-04-28T10:00:00Z",
    "lastModifiedBy": "ai"
  }
}
```

**字段规范**：
- 字段名：`blueprintType`
- 可选性：可选，默认值 `"architecture"`（向后兼容）
- 枚举值：`"architecture"` | `"domain-knowledge"`
- 互斥性：两种类型互斥，不设计hybrid（避免复杂度）

**AI判断逻辑**：
- 用户需求包含"know-how"、"领域知识"、"策略"、"痛点" → `blueprintType = "domain-knowledge"`
- 用户需求包含"架构图"、"系统设计" → `blueprintType = "architecture"`（默认）
- 混合需求 → AI选择主需求方向（优先domain-knowledge，因为architecture实体可选关联）

#### 2. library结构扩展

新增可选的`knowledge`块：

```json
{
  "library": {
    // 现有实体保持不变
    "capabilities": [],
    "actors": [],
    "flowSteps": [],
    "systems": [],

    // 新增可选块
    "knowledge": {
      "painPoints": [],     // 痛点挑战
      "strategies": [],     // 关键策略
      "rules": [],          // 平台/政策规则
      "metrics": [],        // 数据指标/基准
      "practices": [],      // 最佳实践
      "pitfalls": [],       // 常见误区
      // 允许用户自定义实体类型数组
      "caseStudies": [],    // 用户自定义
      "tools": []           // 用户自定义
    }
  }
}
```

**设计要点**：
- `knowledge`块可选（architecture蓝图不填充此块）
- 当`blueprintType="domain-knowledge"`时，`knowledge`块必须存在且至少包含1个实体
- 6类预定义实体数组均可选（根据行业hints决定填充哪些）
- 允许用户自定义实体类型数组（validator不校验数组名称）

#### 3. schema校验规则

**validator校验逻辑**：
- 如果`blueprintType="architecture"`：`knowledge`块必须为空或不存在
- 如果`blueprintType="domain-knowledge"`：`knowledge`块必须存在且至少1个实体
- 所有knowledge实体必须包含核心字段：`id`、`name`、`entityType`
- 扩展字段不校验，允许任意JSON结构

---

### 二、Knowledge实体字段定义

#### 核心设计原则：强核心 + 弱扩展

**强核心**（validator必须校验）：
- `id`：唯一标识
- `name`：实体名称
- `entityType`：实体类型标识

**弱扩展**（validator不校验，直接放行）：
- 所有其他字段（description、severity、solutions等）
- 用户自定义字段
- 允许任意JSON结构

#### 实体类型定义

| 实体类型 | entityType值 | 层级字段 | 分级字段 | 典型数量 |
|---------|-------------|---------|---------|---------|
| painPoints | `"painPoint"` | level（可选） | severity（可选） | 3-8 |
| strategies | `"strategy"` | level（可选） | - | 3-10 |
| rules | `"rule"` | - | severity（可选） | 3-8 |
| metrics | `"metric"` | - | - | 3-10 |
| practices | `"practice"` | - | - | 3-10 |
| pitfalls | `"pitfall"` | - | severity（可选） | 3-8 |

#### 实体字段规范

##### PainPoints（痛点挑战）

**核心字段**：
```json
{
  "id": "pain-001",           // 必填，格式 pain-{seq}
  "name": "ROI不稳",          // 必填，痛点名称
  "entityType": "painPoint"   // 必填，实体类型标识
}
```

**可选字段**（推荐但不强制）：
```json
{
  "description": "广告投放ROI波动大，缺乏稳定增长路径",
  "severity": "high",         // 枚举：low | medium | high | critical
  "level": 1,                 // 层级：1=顶层痛点，2=子痛点
  "relatedCapabilityIds": ["cap-004"],  // 关联能力（可选）
  "solutions": ["测款节奏", "数据监控"],  // 用户自定义字段
  "impactArea": "Revenue"     // 用户自定义字段
}
```

**命名规则**：
- 以问题为核心：`"ROI不稳"`、`"素材疲劳"`、`"平台封号"`
- 避免：`"缺乏XX系统"`（这是系统视角，不是业务痛点）

##### Strategies（关键策略）

**核心字段**：
```json
{
  "id": "str-001",
  "name": "测款节奏策略",
  "entityType": "strategy"
}
```

**可选字段**：
```json
{
  "description": "3天测款周期，预算分配70%测款+30%放量",
  "level": 1,
  "applicableCapabilityIds": ["cap-004"],
  "prerequisites": ["数据分析能力"],
  "successRate": "80%"        // 用户自定义字段
}
```

**命名规则**：
- 以策略方法为核心：`"测款节奏策略"`、`"受众分层策略"`
- 避免：`"优化ROI"`（这是目标，不是策略）

##### Rules（平台/政策规则）

**核心字段**：
```json
{
  "id": "rule-001",
  "name": "Facebook广告政策红线",
  "entityType": "rule"
}
```

**可选字段**：
```json
{
  "description": "禁止误导性宣传、过度夸大效果、虚假折扣",
  "severity": "critical",
  "platform": "Facebook Ads",
  "penalty": "账户封禁",
  "policyUrl": "https://..."   // 用户自定义字段
}
```

**命名规则**：
- 明确规则来源+内容：`"Facebook广告政策红线"`、`"Google Quality Score要求"`

##### Metrics（数据指标）

**核心字段**：
```json
{
  "id": "met-001",
  "name": "ROAS基准",
  "entityType": "metric"
}
```

**可选字段**：
```json
{
  "value": ">3.0",
  "unit": "ratio",
  "benchmarkContext": "欧美市场，电商类目",
  "calculationMethod": "GMV / Ad Spend",
  "targetAudience": "Growth team"  // 用户自定义字段
}
```

**命名规则**：
- 指标名称+基准：`"ROAS基准"`、`"CTR阈值"`

##### Practices（最佳实践）

**核心字段**：
```json
{
  "id": "bp-001",
  "name": "素材迭代周期",
  "entityType": "practice"
}
```

**可选字段**：
```json
{
  "description": "每7天测试新素材版本，CTR下降10%时立即更换",
  "frequency": "weekly",
  "successMetric": "CTR提升15%",
  "difficulty": "Medium"      // 用户自定义字段
}
```

**命名规则**：
- 实践内容为核心：`"素材迭代周期"`、`"测款预算分配"`

##### Pitfalls（常见误区）

**核心字段**：
```json
{
  "id": "pit-001",
  "name": "过度依赖单一平台",
  "entityType": "pitfall"
}
```

**可选字段**：
```json
{
  "description": "只投放Facebook，平台封号后业务瘫痪",
  "severity": "critical",
  "avoidanceStrategy": "多平台分散投放，预算占比不超过60%",
  "realCase": "XX公司案例"   // 用户自定义字段
}
```

**命名规则**：
- 误区行为为核心：`"过度依赖单一平台"`、`"忽视合规风险"`

---

### 三、Relations关系类型定义

#### 知识实体内部关系

新增关系类型（用于knowledge实体之间的关联）：

| type | from → to | 说明 | 示例 |
|------|-----------|------|------|
| `solves` | strategy → painPoint | 策略解决痛点 | 测款节奏策略 → ROI不稳 |
| `prevents` | practice → pitfall | 实践规避误区 | 素材迭代周期 → 素材疲劳 |
| `measures` | metric → strategy | 指标衡量策略效果 | ROAS基准 → 测款节奏策略 |
| `enforces` | rule → strategy | 规则约束策略 | Facebook政策红线 → 受众分层策略 |
| `requires` | strategy → practice | 策略依赖实践 | 测款节奏策略 → 数据监控实践 |
| `causes` | pitfall → painPoint | 误区导致痛点 | 过度依赖单一平台 → 平台封号 |

#### 跨类型关系（单向：knowledge → architecture）

| type | from → to | 说明 | 示例 |
|------|-----------|------|------|
| `impacts` | painPoint → capability | 痛点影响能力 | ROI不稳 → 广告投放管理 |
| `supports` | strategy → capability | 策略支撑能力 | 测款节奏策略 → 数据分析能力 |
| `enforcedBy` | rule → system | 规则约束系统 | Facebook政策红线 → 广告投放服务 |
| `measuredBy` | metric → system | 指标监控系统 | ROAS基准 → 数据分析服务 |

**约束**：
- 跨类型关系只允许knowledge实体指向architecture实体
- architecture实体不能指向knowledge实体（保持architecture实体的纯粹性）
- 根据实际业务场景决定是否建立跨类型关联，不强加

---

### 四、AI提取指南（SKILL.md改造）

#### 1. 蓝图类型检测

在SKILL.md开头新增章节：

```markdown
## Blueprint Type Detection

AI must detect user intent before entity extraction:

**Detection logic**:
- 用户需求包含"know-how"、"领域知识"、"策略"、"痛点"、"最佳实践"、"行业玩法" → `blueprintType = "domain-knowledge"`
- 用户需求包含"架构图"、"系统设计"、"IT规划"、"技术蓝图" → `blueprintType = "architecture"`（默认）
- 混合需求 → AI选择主需求方向（优先domain-knowledge）

**Default behavior**:
- If unclear, default to `architecture`（向后兼容）
- If industryHints contains `knowledgeHints`, hint AI to also consider domain-knowledge extraction
```

#### 2. 实体提取流程改造

修改SKILL.md的"Step 2: Extract entities from source text"章节：

```markdown
### Step 2: Extract entities from source text

**If blueprintType = "architecture"**:
Using the user's source material AND the industry hints checklist, extract:
- capabilities, actors, flowSteps, systems
  - See `references/entities-schema.md` for definitions

**If blueprintType = "domain-knowledge"**:
Using the user's source material AND the knowledge hints checklist, extract:
- painPoints, strategies, rules, metrics, practices, pitfalls
  - See `references/knowledge-entities-schema.md` for definitions

**Entity extraction order** (for domain-knowledge):
1. Read `industryHints.knowledgeHints.checklist`（行业线索）
2. Extract painPoints first（痛点是know-how的核心锚点）
3. Derive strategies from painPoints（每个痛点对应的解决策略）
4. Extract practices from strategies（策略的具体执行实践）
5. Extract metrics to measure strategies（衡量策略效果的指标）
6. Extract rules relevant to strategies（约束策略的规则）
7. Extract pitfalls related to painPoints（导致痛点的常见误区）
8. Build relations array（solves、prevents、measures等关系）

**Minimal entity fields**:
- All knowledge entities must have: `id`, `name`, `entityType`
- Optional fields are recommended but not enforced
- User-defined fields are allowed（validator不校验）
```

---

### 五、行业Hints模板设计

#### 1. hints模板结构

修改所有`templates/{industry}/seed.json`，新增`knowledgeHints`块：

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
        "痛点：库存积压、客流下滑、会员流失、POS效率低",
        "策略：会员分层运营、智能补货、导购赋能、全渠道融合",
        "规则：食品安全合规、价格欺诈风险、数据隐私法规",
        "指标：坪效基准、客单价目标、会员复购率、员工人效",
        "最佳实践：陈列迭代周期、促销节奏、会员召回时机",
        "误区：过度依赖促销、忽视会员运营、数据孤岛"
      ]
    }
  }
}
```

#### 2. 新建跨境电商行业模板

新建`templates/cross-border-ecommerce/seed.json`：

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
        "痛点：ROI不稳、素材疲劳、平台封号、库存积压、汇率风险、合规风险",
        "策略：测款节奏策略（3天周期）、出价策略（动态调整）、受众分层策略、再营销触发时机、预算动态分配",
        "规则：Facebook政策红线（禁止误导宣传）、Google Quality Score机制、TikTok审核要点、Amazon合规要求",
        "指标：ROAS基准（>3.0）、CPA阈值、CTR基准（>1.5%）、LTV测算、转化率目标",
        "最佳实践：素材迭代周期（7天）、测款预算分配（70%测款+30%放量）、再营销触发时机（浏览>3次）、多平台分散投放",
        "误区：过度依赖单一平台、忽视合规风险、数据孤岛、盲目放量、忽视LTV、素材疲劳不更换"
      ]
    }
  }
}
```

#### 3. hints编写指南

**checklist条目格式**：
- `实体类型：具体条目1、条目2、条目3`
- AI解析规则：识别实体类型关键词（痛点/策略/规则/指标/实践/误区），提取具体条目

**行业hints编写原则**：
- 覆盖典型场景：每个实体类型至少3-5个条目
- 避免过于抽象：条目应该具体可提取（如"素材迭代周期7天"，而非"优化素材管理"）
- 提供业务上下文：条目包含数值、平台、场景等细节

---

### 六、导出视图渲染设计

#### 1. freeflow渲染策略

freeflow视图作为默认渲染器，自适应处理knowledge实体。

**实体类型识别**：
- 通过`entityType`字段识别实体类型
- 未知entityType视为用户自定义实体

**视觉样式定义**（在freeflow渲染器中）：

```javascript
const knowledgeStyles = {
  painPoint: {
    color: '#DC2626',      // 纰红色（高严重度）
    shape: 'rounded-rect',
    icon: '⚠️',
    defaultSeverity: 'high'
  },
  strategy: {
    color: '#0B6E6E',      // 深青绿（解决方案）
    shape: 'rounded-rect',
    icon: '💡',
    defaultSeverity: 'medium'
  },
  rule: {
    color: '#D97706',      // 琥珀橙（合规警告）
    shape: 'rect',
    icon: '📋',
    defaultSeverity: 'critical'
  },
  metric: {
    color: '#4F46E5',      // 靛蓝（数据指标）
    shape: 'circle',
    icon: '📊',
    defaultSeverity: 'low'
  },
  practice: {
    color: '#10B981',      // 翠绿（最佳实践）
    shape: 'rounded-rect',
    icon: '✅',
    defaultSeverity: 'low'
  },
  pitfall: {
    color: '#F59E0B',      // 黄橙（误区警告）
    shape: 'rect',
    icon: '❌',
    defaultSeverity: 'high'
  }
};
```

**severity分级渲染**：
- `critical`：粗边框（stroke-width: 4），高亮阴影
- `high`：中等边框（stroke-width: 3），中等阴影
- `medium`：标准边框（stroke-width: 2），轻微阴影
- `low`：细边框（stroke-width: 1），无阴影

**层级布局**（仅painPoints和strategies）：
- level 1实体：顶层，较大尺寸（width: 200px, height: 80px）
- level 2实体：子级，连接到父实体，较小尺寸（width: 160px, height: 60px）

#### 2. 用户自定义实体渲染

**默认样式**：
- color: '#6B7280'（灰色）
- shape: 'rounded-rect'
- icon: '📦'
- severity: 'low'

**用户自定义样式支持**：
- 允许在实体中添加`style`字段自定义视觉样式
- validator不校验style字段，直接传递给渲染器

```json
{
  "id": "custom-001",
  "name": "案例研究",
  "entityType": "caseStudy",
  "style": {
    "color": "#8B5CF6",
    "shape": "hexagon",
    "icon": "📚"
  }
}
```

#### 3. relations关系渲染

**关系类型连线样式**：

```javascript
const relationStyles = {
  solves: { color: '#10B981', dashArray: '', label: '解决' },
  prevents: { color: '#F59E0B', dashArray: '5,5', label: '规避' },
  measures: { color: '#4F46E5', dashArray: '', label: '衡量' },
  enforces: { color: '#DC2626', dashArray: '8,4', label: '约束' },
  requires: { color: '#6B7280', dashArray: '5,5', label: '依赖' },
  causes: { color: '#DC2626', dashArray: '', label: '导致' },
  impacts: { color: '#F59E0B', dashArray: '5,5', label: '影响' },
  supports: { color: '#10B981', dashArray: '', label: '支撑' }
};
```

**箭头方向**：
- 实线箭头：正向关系（solves、supports）
- 虚线箭头：约束/依赖关系（prevents、requires、enforces）
- 双向箭头：互相关联（measures）

---

### 七、Validator改造设计

#### 1. schema校验逻辑

**Python代码改造**（`scripts/business_blueprint/schema_validator.py`）：

```python
def validate_blueprint(blueprint_json):
    errors = []

    # 校验meta.blueprintType
    blueprint_type = blueprint_json.get("meta", {}).get("blueprintType", "architecture")
    if blueprint_type not in ["architecture", "domain-knowledge"]:
        errors.append(f"Invalid blueprintType: {blueprint_type}")

    # 校验knowledge块
    library = blueprint_json.get("library", {})
    knowledge = library.get("knowledge", {})

    if blueprint_type == "architecture":
        if knowledge and any(knowledge.values()):
            errors.append("architecture蓝图不应该包含knowledge实体")
    elif blueprint_type == "domain-knowledge":
        if not knowledge:
            errors.append("domain-knowledge蓝图必须包含knowledge块")
        if not any(knowledge.values()):
            errors.append("domain-knowledge蓝图的knowledge块至少包含1个实体")

    # 校验knowledge实体核心字段
    for entity_type, entities in knowledge.items():
        for entity in entities:
            if "id" not in entity:
                errors.append(f"{entity_type}实体缺少id字段")
            if "name" not in entity:
                errors.append(f"{entity_type}实体缺少name字段")
            if "entityType" not in entity:
                errors.append(f"{entity_type}实体缺少entityType字段")

    # 校验relations关系类型
    relations = blueprint_json.get("relations", [])
    valid_relation_types = [
        "supports", "depends", "realizes",  # architecture关系
        "solves", "prevents", "measures", "enforces", "requires", "causes",  # knowledge内部关系
        "impacts", "supports", "enforcedBy", "measuredBy"  # 跨类型关系
    ]
    for relation in relations:
        if relation.get("type") not in valid_relation_types:
            errors.append(f"Invalid relation type: {relation.get('type')}")

    return errors
```

**校验要点**：
- 只校验核心字段：`id`、`name`、`entityType`
- 不校验扩展字段：description、severity、level等直接放行
- 不校验用户自定义实体类型名称：允许任意entityType

#### 2. 向后兼容保证

**测试策略**：
- 所有现有architecture蓝图JSON必须通过validator校验
- blueprintType默认值为"architecture"，现有JSON无需修改
- knowledge块不存在时，validator不报错

**回归测试用例**：
```python
# 测试1：现有architecture蓝图不受影响
existing_architecture_blueprint = {
  "meta": {"title": "...", "industry": "retail"},
  "library": {
    "capabilities": [{"id": "cap-001", "name": "...", "level": 1, "description": "..."}]
  }
}
errors = validate_blueprint(existing_architecture_blueprint)
assert len(errors) == 0  # 无错误，向后兼容

# 测试2：domain-knowledge蓝图核心字段校验
domain_knowledge_blueprint = {
  "meta": {"blueprintType": "domain-knowledge"},
  "library": {
    "knowledge": {
      "painPoints": [{"id": "pain-001"}]  # 缺少name和entityType
    }
  }
}
errors = validate_blueprint(domain_knowledge_blueprint)
assert "painPoint实体缺少name字段" in errors
assert "painPoint实体缺少entityType字段" in errors

# 测试3：用户自定义字段不校验
domain_knowledge_blueprint = {
  "meta": {"blueprintType": "domain-knowledge"},
  "library": {
    "knowledge": {
      "painPoints": [
        {
          "id": "pain-001",
          "name": "ROI不稳",
          "entityType": "painPoint",
          "customField": "任意值",  # 用户自定义字段
          "anotherCustom": {"nested": "object"}  # 复杂自定义结构
        }
      ]
    }
  }
}
errors = validate_blueprint(domain_knowledge_blueprint)
assert len(errors) == 0  # 用户自定义字段不报错
```

---

### 八、实施路径与工作量估算

#### Phase 1：文档编写与schema定义（P0，立即实施）

**文件改动清单**：
| 文件 | 改动内容 | 工作量 |
|------|---------|--------|
| 新建 `references/knowledge-entities-schema.md` | 定义knowledge实体字段规范 | 1-2小时 |
| 修改 `references/entities-schema.md` | 新增knowledge块说明，更新实体概览表 | 0.5小时 |
| 新建 `scripts/business_blueprint/templates/cross-border-ecommerce/seed.json` | 跨境电商knowledgeHints模板 | 0.5小时 |
| 修改 `scripts/business_blueprint/templates/common/seed.json` | 新增meta.blueprintType字段（默认值"architecture"） | 0.5小时 |
| 修改 `scripts/business_blueprint/templates/retail/seed.json` | 新增knowledgeHints块 | 0.5小时 |
| 修改 `scripts/business_blueprint/templates/finance/seed.json` | 新增knowledgeHints块 | 0.5小时 |
| 修改 `scripts/business_blueprint/templates/manufacturing/seed.json` | 新增knowledgeHints块 | 0.5小时 |
| 修改 `SKILL.md` | 新增Blueprint Type Detection章节，修改Step 2实体提取流程 | 1-2小时 |

**Phase 1总工作量**：4-6小时

**验收标准**：
- knowledge-entities-schema.md定义清晰，AI可参照提取
- 跨境电商hints模板包含完整checklist
- SKILL.md的AI提取指南明确且可执行

---

#### Phase 2：Validator改造（P1，短期内实施）

**文件改动清单**：
| 文件 | 改动内容 | 工作量 |
|------|---------|--------|
| 修改 `scripts/business_blueprint/schema_validator.py` | 新增knowledge实体校验逻辑，校验核心字段，向后兼容保证 | 2-3小时 |
| 新建 `tests/schema_validator_test.py` | 单元测试（architecture蓝图兼容性、knowledge蓝图校验、用户自定义字段） | 1-2小时 |
| 修改 `scripts/business_blueprint/cli.py` | 在`--plan`和`--validate`命令中集成新validator | 1小时 |

**Phase 2总工作量**：4-6小时

**验收标准**：
- validator校验核心字段，不拦截扩展字段
- 所有现有architecture蓝图通过validator
- domain-knowledge蓝图缺少核心字段时validator报错

---

#### Phase 3：导出引擎改造（P2，中期迭代）

**文件改动清单**：
| 文件 | 改动内容 | 工作量 |
|------|---------|--------|
| 修改 `scripts/business_blueprint/export_routes.py` | 新增knowledge蓝图路由判断（freeflow优先） | 1-2小时 |
| 修改 `scripts/business_blueprint/renderers/freeflow_renderer.py` | 新增knowledge实体视觉样式定义，用户自定义实体渲染支持 | 3-4小时 |
| 新建 `references/knowledge-rendering-guide.md` | knowledge实体视觉设计文档（颜色、形状、图标、severity分级） | 1小时 |
| 修改 `scripts/business_blueprint/cli.py` | 在`--export`命令中集成knowledge渲染逻辑 | 1小时 |

**Phase 3总工作量**：6-8小时

**验收标准**：
- freeflow能渲染knowledge实体（痛点红、策略绿、规则橙等）
- severity分级显示（critical粗边框、low细边框）
- 用户自定义实体有默认样式，不报错

---

#### Phase 4：行业模板扩展（P3，长期迭代）

**可选行业模板**：
- 新建 `templates/ad-tech/seed.json`（广告技术行业）
- 新建 `templates/logistics/seed.json`（物流行业）
- 新建 `templates/education/seed.json`（教育行业）

**工作量**：每个行业模板0.5-1小时

---

### 九、验证测试用例

#### 测试1：向后兼容性验证

**输入**：
```
生成企业管理系统的架构蓝图
```

**预期**：
- blueprintType = "architecture"（默认）
- 只填充library核心实体（capabilities/actors/flowSteps/systems）
- knowledge块为空或不存在
- validator校验通过（无错误）
- 导出视图为现有模板（poster/swimlane/freeflow）

**验证点**：
- 现有architecture蓝图JSON无需修改即可通过validator
- 导出引擎不报错，正常渲染architecture实体

---

#### 测试2：纯knowledge蓝图验证

**输入**：
```
生成跨境电商广告投放的领域know-how大图，包含痛点、策略、平台规则、数据指标
```

**预期**：
- blueprintType = "domain-knowledge"
- 只填充library.knowledge块（painPoints/strategies/rules/metrics）
- library核心实体（capabilities等）为空或不存在
- validator校验通过（核心字段齐全）
- industry自动选择"cross-border-ecommerce"
- 导出视图为freeflow（知识图谱样式）

**验证点**：
- knowledge实体核心字段（id/name/entityType）齐全
- validator不拦截用户自定义字段
- freeflow渲染knowledge实体（痛点红、策略绿、规则橙）

---

#### 测试3：用户自定义实体验证

**输入**：
```
生成跨境电商know-how大图，除了痛点策略，我还想加一些案例研究（caseStudies）
```

**预期**：
- blueprintType = "domain-knowledge"
- knowledge块包含painPoints、strategies、caseStudies（用户自定义）
- caseStudies实体有核心字段：id、name、entityType="caseStudy"
- validator校验通过（只校验核心字段）
- freeflow渲染caseStudies（默认灰色样式）

**验证点**：
- validator允许用户自定义实体类型
- freeflow为未知entityType提供默认样式
- 用户可在caseStudies实体中添加任意扩展字段（如link、description、tags）

---

#### 测试4：混合蓝图验证（边界测试）

**输入**：
```
生成跨境电商广告投放方案，既要系统架构，又要业务策略know-how
```

**预期**：
- blueprintType = "domain-knowledge"（AI选择主需求方向）
- knowledge实体为主（痛点、策略）
- architecture实体可选关联（策略支撑能力）
- relations包含跨类型关系（strategy → capability，type="supports")

**验证点**：
- AI能判断主需求方向并选择blueprintType
- knowledge实体可单向关联architecture实体
- architecture实体不关联knowledge实体

---

### 十、风险评估与应对

#### 高风险

**无**

理由：schema扩展采用"强核心+弱扩展"设计，validator只校验核心字段，用户自定义字段直接放行，不会破坏灵活性。

#### 中风险

**风险1：validator校验核心字段可能拦截合法用户输入**
- 场景：用户忘记填写entityType字段
- 影响：validator报错，用户无法生成蓝图
- 应对：AI提取时强制填写entityType，hints模板提醒AI注意核心字段

**风险2：freeflow渲染器可能无法处理复杂用户自定义结构**
- 场景：用户在实体中添加复杂的嵌套JSON结构（如`{"nested": {"deep": "object"}}`)
- 影响：freeflow渲染器崩溃或显示异常
- 应对：freeflow渲染器增加容错逻辑，复杂结构时降级显示为文本卡片

#### 低风险

**风险3：行业hints模板可能不完整**
- 场景：跨境电商hints模板缺少某些关键痛点
- 影响：AI提取时遗漏实体
- 应对：hints模板迭代更新，用户可自定义hints补充

**风险4：用户可能不理解entityType命名规则**
- 场景：用户自定义实体时entityType命名不规范（如`"myCase"`而非`"caseStudy"`）
- 影响：不影响校验，但freeflow渲染样式可能不符合用户预期
- 应对：schema文档提供entityType命名建议（推荐使用camelCase，如`caseStudy`、`tool`）

---

### 十一、后续迭代建议

#### 1. 知识图谱交互式编辑器
让用户在HTML viewer中点击knowledge节点，展开详情卡片，添加新的know-how节点。

#### 2. 行业know-how库沉淀
收集各行业的know-how模板库，形成可复用的知识资产（例如跨境电商常见痛点清单、解决方案库）。

#### 3. know-how演化记录
支持know-how的版本管理，记录历史变更（例如Facebook政策规则的历史变更轨迹）。

#### 4. 混合蓝图视图优化
开发专门的混合视图模板，architecture实体和knowledge实体分层显示（上层架构图，下层知识图谱）。

#### 5. know-how与架构联动标注
在architecture图中标注对应的know-how（例如在某个系统节点旁显示"规避XX风险的最佳实践"卡片）。

---

## 设计审查清单

完成设计后，AI需进行自我审查：

### Placeholder扫描
- ❌ 无"TBD"、"TODO"、不完整章节、模糊需求

### 内部一致性
- ✅ 各章节描述一致（schema定义 ↔ AI提取指南 ↔ validator校验逻辑）
- ✅ 实体字段定义与relations关系类型匹配
- ✅ hints模板结构符合AI提取指南预期

### Scope检查
- ✅ 设计聚焦单一目标：扩展knowledge实体，保持向后兼容
- ✅ 无超出scope的功能（未涉及混合视图、交互式编辑等高级特性）

### Ambiguity检查
- ✅ 核心字段定义明确（id/name/entityType必填）
- ✅ 关系类型枚举清晰（solves/prevents等）
- ✅ blueprintType枚举明确（architecture/domain-knowledge，无hybrid）
- ✅ 用户自定义实体允许性明确（validator不校验entityType名称）

---

## 设计交付物

本设计文档交付后，需进入实施阶段：

1. **用户审查本设计文档**
2. **用户批准后，调用writing-plans skill**
3. **生成详细实施计划**
4. **按Phase 1 → Phase 2 → Phase 3顺序实施**
5. **每个Phase完成后回归测试**
6. **全部完成后验收**

---

**设计完成日期**: 2026-04-28
**下一步**: 用户审查本设计文档，批准后进入writing-plans skill生成实施计划