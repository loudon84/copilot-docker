# 财务经营分析办公室（BI 智能问数）业务使用指南

本文面向财务、经营分析、管理层等业务人员，说明「能问什么、怎么问、结果怎么读」。  
部署与运维细节见同目录 [README.md](README.md)。

---

## 1. 这是什么

`bi-strategic-office`（财务经营分析办公室）是一个 **用自然语言查询财务经营数据** 的 AI 专家助手。

你可以像对分析师说话一样提问，例如：

- 「查询 2026Q2 各产品销售利润报表」
- 「只看毛利率低于 5% 的产品」
- 「按销售区域拆分」
- 「解释销售利润的计算口径」
- 「导出为 XLSX」

系统会基于已登记的 **指标与口径** 取数，并给出表格与说明；**不会**自行编造数字，也 **不会** 执行任意 SQL 或改账。

### 与「资金/财务运营」专家的区别

| 场景 | 找谁 |
|------|------|
| 账户余额、账龄、回款、头寸、资金计划、付款运营 | `finance` 专家 |
| 经营取数、产品/客户/区域利润、同比环比、指标口径、管理分析报告 | **本专家（BI）** |

---

## 2. 问数是怎么工作的（业务视角）

业务人员不需要写 SQL。一次标准问数大致是：

```text
你的自然语言问题
    ↓
对照「语义目录」（指标、维度、时间、主体等登记口径）
    ↓
生成结构化问数请求（SemanticQuery，不是直接写 SQL）
    ↓
系统按规则编译并校验只读查询
    ↓
在只读库中取数
    ↓
返回表格 + 口径说明 + 警告（如有）
```

要点：

1. **先认口径，再取数** —— 「利润」「销售额」等必须对应已登记指标；有歧义时助手会先问你，而不是猜。
2. **数字只来自工具返回** —— 分析结论可以推断，但表格里的数不得被 AI 改写。
3. **只读** —— 不会过账、核销、付款、改库。
4. **有权限边界** —— 只能看到本实例配置允许的主体（公司）、库表与字段范围。

---

## 3. 相关目录对业务意味着什么

运行时大致有这些区域（路径供理解用途，日常在 WebUI 对话即可）：

| 区域 | 业务含义 |
|------|----------|
| `finance-bi/semantic/` | **语义目录**：登记了「有哪些报表数据集、指标叫什么、怎么算、有哪些维度」。业务口径变更时，由数据/财务 IT 维护这里的定义，而不是改聊天话术。 |
| `finance-bi/policies/` | **查询策略**：行数上限、超时、脱敏等安全与成本规则。 |
| `finance-bi/state/` | **查询状态与审计**：记住上一轮问数编号，便于「接着筛」；审计不保存完整结果明细。 |
| `plugins/hermes-finance-bi-plugin/` | **问数插件**：真正执行 ask / 下钻 / 解释 / 导出的能力。 |
| `workspace/exports/bi/` | **导出文件**：你要求导出的 CSV / Excel 落在这里，便于下载或二次加工。 |

业务人员通常 **不用直接改这些目录**；需要新增指标或改口径时，联系数据/财务 IT 更新语义目录。

### 3.1 语义目录与查询策略在哪里配置、如何安装

分两层，不要只在运行中的实例里手改（一重新注入可能被模板覆盖）：

| 层级 | 路径 | 谁维护 | 做什么 |
|------|------|--------|--------|
| **源配置（应改这里）** | `expert-templates/bi-strategic-office/semantic/` | 数据 / 财务 IT | 数据集、指标、维度、术语、示例 YAML |
| **源配置（应改这里）** | `expert-templates/bi-strategic-office/policies/` | 数据 / 财务 IT | 如 `query-policy.yaml`（行数上限、超时、脱敏等） |
| **运行时（自动安装结果）** | `instances/<实例名>/data/hermes/finance-bi/semantic/` | 一般不手改 | 插件实际读取的语义目录 |
| **运行时（自动安装结果）** | `instances/<实例名>/data/hermes/finance-bi/policies/` | 一般不手改 | 插件实际读取的策略 |

插件通过环境变量定位运行时路径（默认如下）：

```env
FINANCE_BI_CATALOG_PATH=/data/hermes/finance-bi/semantic
FINANCE_BI_POLICY_PATH=/data/hermes/finance-bi/policies
```

**安装 / 更新到实例**（IT 执行）：

```bash
# 创建实例时会自动同步；之后改了模板语义/策略，再执行：
bash scripts/sync-bi-semantic-catalog.sh financial-analysis bi-strategic-office
# 或完整重新注入（幂等）
bash scripts/inject-expert.sh financial-analysis bi-strategic-office
bash scripts/restart-instance.sh financial-analysis
```

语义目录典型文件位置示例：

```text
expert-templates/bi-strategic-office/semantic/
├── datasources/     # 数据源说明
├── datasets/        # 数据集（对应哪张表、可用指标/维度）
├── metrics/         # 指标定义与计算公式
├── dimensions/      # 维度
├── glossary/        # 业务别名与歧义说明
└── examples/        # 示例问法

expert-templates/bi-strategic-office/policies/
└── query-policy.yaml
```

### 3.2 当前生产库接入信息（DW_TEMP）

| 项 | 值 |
|----|-----|
| 引擎 | SQL Server 2012 |
| 地址 | `192.168.99.37:1433`（若连不上再核对是否实际为自定义端口） |
| 库名 | `DW_TEMP` |
| 只读账号 | `AIUser`（密码勿写入仓库，写在实例 `.env`） |
| 事实表 | `dbo.ebs1_cux_ar_gp_details`（授权分销销售毛利报表） |
| 字段字典 | `dbo.DW_AI_Table_Column_List`（表名 / 字段名 / 解释） |

实例 `.env` 示例：

```env
FINANCE_BI_DSN=mssql+pymssql://AIUser:PASSWORD@192.168.99.37:1433/DW_TEMP
FINANCE_BI_DIALECT=mssql
FINANCE_BI_TDS_VERSION=7.0
FINANCE_BI_ALLOWED_SCHEMAS=dbo
FINANCE_BI_ALLOWED_ENTITIES=   # 按实际主体字段值填写，如有
FINANCE_BI_CATALOG_PATH=/data/hermes/finance-bi/semantic
FINANCE_BI_POLICY_PATH=/data/hermes/finance-bi/policies
```

**pymssql 报 `20002 Adaptive Server connection failed`**：多为 TDS 协议版本与 SQL Server 2012 不匹配，先设 `FINANCE_BI_TDS_VERSION=7.0` 再连；脚本 `--probe-columns` 会自动依次尝试 7.0–7.4。

**用字典表生成语义字段（IT）**：

```bash
# 1) 先看字典表真实列名（若默认 table_name/column_name/column_comment 对不上）
export FINANCE_BI_DSN='mssql+pymssql://AIUser:PASSWORD@192.168.99.37:1433/DW_TEMP'
export FINANCE_BI_TDS_VERSION=7.0
python scripts/lib/sync_bi_semantic_from_dw_dict.py --probe-columns

# 2) 按探测结果设置列名环境变量后生成 dataset YAML
export DW_DICT_TABLE_COL=表名列
export DW_DICT_COLUMN_COL=字段名列
export DW_DICT_DESC_COL=解释列
python scripts/lib/sync_bi_semantic_from_dw_dict.py \
  --table ebs1_cux_ar_gp_details \
  --out expert-templates/bi-strategic-office/semantic/datasets/ebs1_cux_ar_gp_details.yaml

# 3) 人工补全 metrics/*.yaml 中的 SUM 表达式后同步到实例
bash scripts/sync-bi-semantic-catalog.sh financial-analysis bi-strategic-office
bash scripts/restart-instance.sh financial-analysis
```

---

## 4. 对话里会用到的六种能力（通俗说明）

助手在后台通过固定工具完成工作，你只需正常说话：

| 能力 | 你怎么说（示例） | 作用 |
|------|------------------|------|
| 查数据集/日期字段 | 「销售利润报表有哪些数据集？列出日期字段」 | 返回语义目录元数据（不查业务库） |
| 发起问数 | 「查 2026Q2 各品牌销售毛利」 | 按语义目录取数，返回表格与口径 |
| 继续筛选/下钻 | 「只看毛利率低于 5%」「按客户拆」 | 基于上一轮结果改条件，不重新乱猜 |
| 解释口径 | 「销售利润怎么算的？」 | 说明指标定义、时间字段、币种、过滤条件 |
| 查有哪些指标 | 「有哪些利润相关指标？」 | 检索可用数据集/指标/维度/别名 |
| 出报告前校验 | 「正式出报告前帮我检查一下」 | 检查主体、时间、币种、粒度与质量警告 |
| 导出 | 「导出为 Excel」 | 生成 CSV 或 XLSX 到导出目录 |

生产主数据集：`ebs1_cux_ar_gp_details`；主时间字段：`ar_fin_due_date`。

---

## 5. 怎么提问效果最好

### 5.1 建议说清楚的要素

尽量包含下面几项（缺了助手可能会追问）：

1. **时间**：如 2026Q2、2026 年 4–6 月、本季度  
2. **看什么**：产品利润、客户贡献、区域毛利等  
3. **怎么切**：按产品、按区域、按客户、Top10 等  
4. **主体/公司**（若有多主体）：如香港主体、HK01  
5. **币种**（若有多币种）：如报告币种 HKD  

### 5.2 推荐问法示例

```text
查询 2026Q2 各产品销售利润报表
```

```text
对比 2026Q2 与 2025Q2 各产品利润变化
```

```text
查询香港主体前十大客户的销售额和毛利
```

```text
毛利率低于 5% 的产品有哪些？按销售区域拆分
```

```text
销售利润使用什么口径？数据更新到什么时候？
```

### 5.3 多轮追问

先问出一张表，再追加条件：

```text
你：查询 2026Q2 各产品销售利润报表
助手：…（给出表格与 query 编号）
你：只看毛利率低于 5% 的产品
你：按销售区域拆分
你：导出为 XLSX
```

这样比每次整句重说更稳定，也符合「基于上一轮结果下钻」的设计。

### 5.4 容易引起歧义、需要先澄清的说法

遇到下列情况，助手应先确认，业务人员也建议主动说清：

| 说法 | 为什么歧义 | 建议改成 |
|------|------------|----------|
| 「利润」 | 可能是销售毛利、经营利润、净利润等 | 「销售毛利」或明确指标名 |
| 未说主体 | 多公司时范围不清 | 「香港主体 / HK01」 |
| 未说币种 | 原币与报告币可能不同 | 「报告币种 HKD」 |
| 「最近」 | 时间窗口不清 | 「2026Q2」或具体起止日 |

---

## 6. 如何阅读助手的回答

正式答复应能看到（或缺省时说明「未指定 / 使用默认」）：

```text
时间口径
主体范围
报告币种
指标口径
数据更新时间
查询警告
```

并区分四类内容：

| 类型 | 含义 | 能否当「账上事实」 |
|------|------|-------------------|
| 数据事实 | 工具返回的表格数字 | 可以，作为本次取数结果 |
| 计算结果 | 由返回数再汇总/比率（如合计毛利率） | 可以，但需核对口径 |
| 业务推断 | 「可能因为促销导致…」 | 仅供参考，需业务确认 |
| 待确认事项 | 缺口径、缺主体、数据质量警告 | 未确认前勿用于对外结论 |

**禁止**把助手「猜」的数写进对外报告；有警告时先处理警告。

---

## 7. 使用规范（必读）

### 7.1 可以做

- 经营分析取数、下钻、同比环比对比（在已支持指标范围内）
- 询问指标定义与查询依据
- 导出 CSV / Excel 做二次分析
- 出管理层分析草稿（须标注事实与推断）

### 7.2 不可以做

- 要求执行任意 SQL、改库、过账、付款、核销
- 要求绕过主体权限看未授权公司数据
- 把完整客户明细、敏感金额、连接串写入长期记忆或对外知识库
- 在口径未确认时，把推断当成已审计结论对外发布

### 7.3 权限与安全（业务须知）

- 当前为 **实例级权限**：同一实例内用户共享同一主体白名单（如仅 HK01）。
- 数据库账号为 **只读**；即使误操作也无法通过本助手改账。
- 查询有行数与超时限制，过大请求会被拒绝或截断并提示。
- 审计会记录「问了什么、用了什么口径」，但 **不保存完整结果集**。

---

## 8. 常见问题（业务）

**Q：为什么助手不直接给答案，却反问我？**  
A：指标或主体存在多种合法口径时，必须先澄清，避免错数。

**Q：数字和我在 ERP/BI 看板不一致？**  
A：先让助手「解释口径」，核对时间字段、主体、币种、指标版本与数据更新时间；仍不一致时联系数据/财务 IT 核对语义目录与源表。

**Q：导出的文件在哪里？**  
A：在实例的 `workspace/exports/bi/`（由运维/IT 协助下载）；对话中也会给出路径提示。

**Q：能不能一次查很多年、全公司所有明细？**  
A：受行数上限、超时与权限策略限制；请缩小时间或维度，或让 IT 调整策略与语义定义。

**Q：我想新增一个指标（比如「经营利润」）？**  
A：由数据/财务 IT 在语义目录登记指标与数据集后即可使用；业务侧用自然语言提问即可，无需改代码。

---

## 9. 建议的业务协作流程

```text
业务提出问题（WebUI）
    → 助手澄清口径（如需）
    → 取数并展示表格
    → 业务确认口径与范围
    → 需要时：下钻 / 校验 / 导出
    → 形成分析结论（区分事实与推断）
    → 口径或指标不足：提需求给数据/财务 IT 更新语义目录
```

---

## 10. 相关文档

| 文档 | 读者 |
|------|------|
| 本文件 `GUIDE.md` | 业务使用人员 |
| [README.md](README.md) | 部署与运维 |
| [SOUL.md](SOUL.md) | 助手身份与输出契约（IT/提示词维护） |
| `prd/v1.9_strategic-office-finance-bi.md` | 产品需求与安全边界 |

如有指标定义争议或权限开通需求，请联系数据/财务 IT，并注明：实例名称、主体、希望使用的指标与时间范围。
