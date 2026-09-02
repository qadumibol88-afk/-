# Model contracts

## Section: 工程事实与参数台账

- Purpose: 区分公开事实、工程实参、研究假设和缺失输入。
- Inputs: 图纸、设施表、运营数据、规范与用户约束。
- Allowed claims: 带来源和状态的参数陈述。
- Forbidden claims: 将公开近似值或占位值表述为竣工实参。
- Required evidence: 每项参数的值、单位、来源、状态。
- Validation checklist: 状态枚举合法；阻塞项完整；来源非空；数值单位明确。

## Section: FDS参数与工况生成

- Purpose: 在输入完整后稳定生成F1_V1至F3_V5。
- Inputs: 参数文件、FDS模板、三档火源和五档风速。
- Allowed claims: 静态生成成功、组合数量与替换内容正确。
- Forbidden claims: 未调用FDS时声称语法或物理模型已通过运行验证。
- Required evidence: 生成清单、参数快照和测试结果。
- Validation checklist: 15组且无重复；火源位于L/2；缺失输入时不写文件；非核心参数不随工况漂移。

## Section: ASET处理

- Purpose: 以四指标最早持续越限确定各横通道ASET。
- Inputs: FDS测点时间序列、阈值、持续时间和点位映射。
- Allowed claims: 越限时刻、控制指标和右删失状态。
- Forbidden claims: 将瞬时尖峰作为ASET；将未越限写成无限安全。
- Required evidence: 原始时间序列、阈值来源和处理日志。
- Validation checklist: 连续10 s规则正确；最早指标正确；单位一致；右删失明确。

## Section: RSET与顺序耦合

- Purpose: 用烟气能见度和出口失效信息修正逐工况疏散。
- Inputs: FDS输出、人员参数、30个随机种子、出口使用记录。
- Allowed claims: 有效横通道的RSET 95百分位和无人使用状态。
- Forbidden claims: 称为实时双向联算；为空横通道虚构RSET。
- Required evidence: 种子清单、人员守恒、出口记录和Pathfinder版本。
- Validation checklist: 每工况30次；人员数守恒；关闭与改道有效；RSET算法一致。

## Section: 推荐风速

- Purpose: 按全局双安全判据选择最低共同风速。
- Inputs: 各工况各有效横通道ASET与RSET。
- Allowed claims: 最低合格风速、次优档和无可行解。
- Forbidden claims: 五档均失败时强行推荐最高档；把临界风速等同于推荐风速。
- Required evidence: 完整15工况安全表。
- Validation checklist: 裕度≥60 s；比值≥1.5；三档火灾全覆盖；按风速升序取首个合格值。
