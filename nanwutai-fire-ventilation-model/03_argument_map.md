# Argument map

## Scientific tension

- What is known: 南五台为双洞分离公路隧道，火灾纵向风会同时影响上游回流抑制和下游烟气传播。
- What is unknown: 在真实几何、三档车型设计火灾和可信不利排队条件下，哪一个共同风速能使所有有效横通道保持足够疏散裕度。
- Why the gap matters: 仅套用通用风速或只控制烟气回流，可能忽略下游ASET缩短、横通道失效和RSET变化。

## Central research question

在南五台隧道中段起火且采用不利方向单洞模型时，哪一档共同纵向风速能够以最低通风强度，使三档车型设计火灾下所有有效横通道同时满足 `ASET-RSET≥60 s` 与 `ASET/RSET≥1.5`？

## Central thesis

合理风速应由真实隧道参数、烟气场和逐工况疏散共同决定，并以全局最低安全裕度筛选，而不是预设为某个通用临界风速。

## Supporting arguments

### Argument 1
- Claim: 风速选点必须覆盖三档火灾各自的烟气回流转折区。
- Evidence: 已锁定的理论计算加0.25 m/s粗筛方法。
- Limitation: 当前缺少Q值、断面与纵坡，不能产生数值风速。

### Argument 2
- Claim: 单独控制回流不足以证明人员安全。
- Evidence: 研究同时输出横通道温度、能见度、CO、烟气层高度以及ASET/RSET。
- Limitation: 各阈值和人员参数仍需项目证据。

### Argument 3
- Claim: 推荐值应是满足全工况双安全判据的最低共同风速。
- Evidence: 用户锁定的稳健合格与最低风速目标。
- Limitation: 若五档均不合格，只能扩大范围，不能强行给出推荐值。

## Counterarguments / alternative explanations

- 较高风速可能消除上游回流，但也可能缩短下游横通道ASET，因此不预设“风速越高越安全”。
- 若车型情景同时改变燃烧与阻塞参数，组间差异不能解释为单一HRR效应。
- 若最不利方向判断错误，单洞15工况不能代表另一方向；真实纵断面到位后必须先完成方向筛选。

## Final move

先以参数门禁保证南五台输入真实可追溯，再生成15个核心FDS工况和对应Pathfinder顺序耦合工况，最后按全局双判据给出最低稳健合格风速或明确报告无可行风速。
