# Scope

- Project: 南五台隧道中段火灾通风参数化模型
- Mode: compose
- Text type: 第一阶段研究模型与仿真输入骨架
- Target reader: 研究者、导师及后续模型实施人员
- Language: zh
- Deliverable scope: 研究基础文件、参数接口、FDS 模板、15 工况生成器、ASET/RSET 与选速逻辑、标准库单元测试
- Desired version: 可审查的第一阶段技术底稿
- Current stage boundary: 只建立模型规范与骨架；不补造真实断面、纵坡、横通道、火源功率或人员安全阈值
- Deferred work: 网格划分、FDS/Pathfinder 安装与运行、PyroSim 工程、真实疏散人群标定、结果分析
- Constraints: 未经用户明确指令不得安装软件或依赖；不得把假设值写成南五台实参；不得将顺序耦合表述为实时双向联算
- Vault access allowed: no
- Archive after confirmation: no

## 第一阶段验收标准

1. 所有参数均带值、单位、来源、状态和是否阻塞生成的信息。
2. 缺少真实工程输入时，生成器必须失败且不产生 `.fds` 文件。
3. 输入完整后，工况编号稳定为 `F1_V1` 至 `F3_V5`，共15组。
4. ASET、RSET、最小安全裕度与最低稳健合格风速均有可测试的确定性算法。
5. 所有自动测试只使用 Python 标准库。
