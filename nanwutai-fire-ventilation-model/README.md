# 南五台隧道中段火灾通风模型（第一阶段）

本目录交付研究模型规范、参数接口、FDS 输入骨架和不依赖第三方软件的校验逻辑。当前版本**故意不可生成可运行的 FDS 工况**：真实断面、纵坡、横通道、Q1/Q2/Q3、五档纵向风速、网格和人员安全阈值仍为缺失输入。

## 当前可做的检查

```powershell
python .\model\generate_cases.py --validate-only
python -m unittest discover -s .\tests -v
```

第一条命令应返回缺失参数并以非零状态退出；这是防止把占位模型误当成南五台工程模型的保护机制。第二条命令仅测试 Python 标准库实现，不安装或调用 FDS、Smokeview、PyroSim、Pathfinder。

## 获得真实资料后的顺序

1. 将图纸或参数表放入 `sources/user_materials/`，不要直接覆盖来源文件。
2. 在 `parameters.json` 中填写值、单位、来源和状态；只有可追溯的工程输入才能标为 `VERIFIED`。
3. 完成理论临界风速与粗筛，将 Q1/Q2/Q3 的转折风速写入参数文件，再由脚本生成五档共同风速。
4. 补齐 FDS 网格、几何、火源、测点等片段后运行静态校验。
5. 只有在用户明确要求安装并完成版本核对后，才能运行 FDS/Pathfinder 或声称模型通过软件验证。

研究边界和变量定义见 [MODEL_SPEC.md](MODEL_SPEC.md)。

## 结果接口

- `model/pathfinder_runs_template.csv`：30个种子的逐横通道使用与完成时间。
- `model/safety_results_template.csv`：聚合后的横通道ASET/RSET输入。
- `model/final_results_template.csv`：包含回流、温度、能见度、CO、层高、ASET、RSET和双安全判据的最终长表。

