# Research canon

## Literature facts

1. 公开实车试验论文将南五台隧道描述为全长约2516 m、双洞分离、单洞双车道并设照明。该信息仅是公开资料，不替代竣工图或运营单位数据。[长安大学学报公开PDF](https://zzszrb.chd.edu.cn/Upload/PaperUpLoad/0796c4c3-f4f3-4f61-a19c-c9cc52f82485.pdf)
2. 《公路隧道设计规范 第一册 土建工程》JTG 3370.1—2018 自2019年5月1日起施行；具体项目仍需核对适用标准和竣工年代。[交通运输部公告](https://xxgk.mot.gov.cn/jigou/glj/202006/t20200623_3313116.html)
3. NIST 将 FDS 定义为面向低速流动、着重火灾烟气与热输运的大涡模拟程序；当前官方手册页列示 FDS 6.11.1，但本项目尚未安装或核对本机版本。[NIST FDS 手册](https://pages.nist.gov/fds/manuals.html)
4. Pathfinder 2026.1 文档说明，启用 FDS 输出集成并提供烟尘能见度数据时，可用能见度限制人员最大速度；本项目将其定义为顺序耦合。[Pathfinder 文档](https://www.thunderheadeng.com/docs/2026-1/pathfinder/profiles/advanced/)

## Experimental facts

- 当前未提供南五台隧道竣工图、纵断面、横通道设施表、风机参数或实测风速。
- 当前未提供南五台运营车型构成、排队长度、载客率、探测报警时序或疏散试验数据。
- 当前没有 FDS 或 Pathfinder 仿真结果。

## Thermodynamic / model facts

- 火源纵向位置固定为研究洞长度的二分之一；最终坐标必须由复核后的研究洞长度计算。
- 核心自变量为三档完整车型设计火灾情景与五档共同纵向风速，共15组FDS工况。
- Q1/Q2/Q3不仅包含峰值HRR，还成套包含增长曲线、火源面积、阻塞尺寸、烟产率、CO产率和燃烧热。
- ASET由横通道入口处多个可生存性指标的最早持续越限时刻决定；阈值未核实时不得计算ASET。
- 模拟输出属于模型结果，不得表述为实测事实或真实火灾验证。

## Supervisor / user constraints

- 不能直接套用1.2或1.8 m/s，必须建立南五台参数化研究模型。
- 当前不假设真实断面和横通道布局。
- Q1/Q2/Q3暂不赋具体功率。
- 暂不执行网格划分、计算资源配置或仿真运行。
- 未经用户明确指令，不得安装FDS、Smokeview、PyroSim、Pathfinder或其他依赖。

## Terminology definitions

- `ASET`: Available Safe Egress Time，可用安全疏散时间。
- `RSET`: Required Safe Egress Time，所需安全疏散时间。
- `M(q,v,k)`: 工况 `(q,v)` 下横通道 `k` 的时间安全裕度，即 `ASET-RSET`。
- `有效横通道`: 在对应Pathfinder工况中至少有人员实际通过的横通道。
- `最低稳健合格风速`: 对全部三档火灾及全部有效横通道同时满足双安全判据的最低共同风速。
- `顺序耦合`: 先运行FDS，再用其输出修改Pathfinder中的速度、出口可用性或改道；不含Pathfinder向FDS反馈。

## Forbidden claims

- 不得称公开长度、示意断面或占位参数为竣工实参。
- 不得在未运行软件时声称模型可运行、收敛、通过验证或得到推荐风速。
- 不得把完整车型情景差异仅归因于HRR。
- 不得把未越限指标写成“无限安全”；必须按右删失报告。
- 不得将最低安全风速等同于临界风速。

## Unresolved claims

- 两条行车洞中哪一条在火灾通风上更不利，需由真实纵坡、洞口条件与自然风压确定。
- Q1/Q2/Q3的具体设计功率及燃烧参数尚待车型构成和适用设计依据。
- 温度、能见度、CO和烟气层高度的项目适用阈值尚待中国现行规范与项目文件核定。
- 横通道数量、位置、尺寸、防火门及安全洞压力边界未知。
