<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/axisagentic-logo-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/assets/axisagentic-logo-light.svg">
    <img alt="AxisAgentic - 运行时与轨迹采集框架" src="docs/assets/axisagentic-logo-light.svg" width="680">
  </picture>

  <p>
    <a href="README.md">English</a> ·
    <strong>简体中文</strong>
  </p>

  <p>
    <a href="https://github.com/yshenaw/DeepSeek-Harness-AxisAgentic/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/yshenaw/DeepSeek-Harness-AxisAgentic/actions/workflows/ci.yml/badge.svg"></a>
    <img alt="Python 3.12+" src="https://img.shields.io/badge/Python-3.12%2B-blue.svg">
    <a href="https://github.com/astral-sh/ruff"><img alt="Ruff" src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json"></a>
    <a href="LICENSE"><img alt="License: Apache-2.0" src="https://img.shields.io/badge/License-Apache_2.0-blue.svg"></a>
    <a href="CONTRIBUTING.md"><img alt="PRs Welcome" src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg"></a>
  </p>

  <p>
    <a href="https://xyz-lab.ai">XYZ AI Lab</a> ·
    <a href="https://xyz-lab.ai/blogs/ai4ai-at-scale/">技术报告</a>
  </p>
</div>

AxisAgentic 是面向长时程 AI 智能体的可扩展运行时，也负责采集执行过程中产生的轨迹。它支持兼容 OpenAI 的端点和可插拔本地模型客户端，并提供多轮执行、工具编排、上下文管理、恢复和基准评估等能力。每条轨迹都保留模型实际可见的状态，因此同一份记录既可用于恢复、回放和基准评估，也可以经筛选后导出为 SFT 数据。

仓库目前提供 Web Search 和 WideSearch 两个参考 recipe。相同的扩展接口也能用于领域 Agent、通用 Agent 和编程 Agent。本仓库不包含模型权重。

> [!IMPORTANT]
> **Fork 与实验。** 本仓库派生自 [XYZ-AI-Lab/AxisAgentic](https://github.com/XYZ-AI-Lab/AxisAgentic)。上游项目仍是当前保留运行时、recipe、文档、归属说明和引用信息的来源。本 Fork 通过小型且保持兼容的改动，探索一种受 DeepSeek Harness 启发的 **“everything is plugin”** 组合模型；这并不表示本仓库与 DeepSeek Harness 兼容，也不表示完整的 AxisAgentic 运行时已经全部 plugin 化。

## 🧩 实验性 Plugin 组合

这个 Fork 的目标是在不重写现有运行时的前提下，让后续修改 Harness、Agent Loop、Skill 和上下文管理更加容易。目前实验层包括：

- **明确的生命周期归属：** `PluginContext` 管理作用域服务和清理 effect。初始化失败时自动回滚，显式卸载是幂等的，context 关闭时按注册的反向顺序清理。
- **可撤销注册：** Tool 和参数修复 Hook 的注册都会返回 disposer，因此 plugin 拥有的能力可以被安全移除。
- **可插拔 Agent Loop：** `AgentLoopPlugin` 提供 `AgentFactory`；每个新 Agent 都有独立的 `PluginContext`，用于组合自己的模型、工具、策略和辅助服务。
- **可插拔 Compaction：** `CompactionPlugin` 在 Agent 本地 context 中提供 `Compactor`；`WebSearchTaskOrchestrator` 依赖接口，而不是具体的压缩管理器。

```mermaid
flowchart LR
  R[Root PluginContext] --> L[AgentLoopPlugin]
  L --> F[AgentFactory]
  F --> A[Agent A Context]
  F --> B[Agent B Context]
  A --> CA[CompactionPlugin / Skills / Policy]
  B --> CB[独立的 plugins 和 services]
  A --> OA[Agent Loop 实现]
  B --> OB[Agent Loop 实现]
```

这条边界目前刻意保持精简。`ConversationRuntime`、`TaskOrchestrator`、模型客户端、轨迹格式、配置，以及现有 Web Search/WideSearch runner 的装配方式仍兼容上游设计。依赖就绪后自动激活、Provider 热替换、通用事件总线、长期 Memory 和完整的 recipe plugin 化尚未实现。

### AI4AI：由外部开发 Agent 驱动的 Harness 演化

本项目中的 **AI4AI**，是指使用 Claude Code、Codex 或 Copilot 等外部开发 Agent 演化 AxisAgentic Harness。外部 Agent 可以检查源码、重放轨迹、分析 Benchmark 结果、实现候选改动，并运行回归测试或成本对比；AxisAgentic 则提供具有独立作用域、可撤销、可测试的边界，使这个过程保持受控。

```text
观察代码、轨迹和指标
-> 提出 Harness 改动
-> 实现候选 Plugin/Profile
-> 运行测试与 Benchmark
-> 与 Baseline 对比
-> 人工审查
-> 晋升或回滚
```

Plugin 组合之所以更适合这套流程，是因为它把 Harness 改动变成了更小的演化单元：

- **更小的改动面：** 外部 Agent 可以替换一个 Loop、Skill、Policy 或 Compactor，而不必重写中心编排器。
- **候选方案隔离：** Baseline 和 Candidate Agent 可以在同一评测进程中使用不同的 Plugin Context，而不会共享可变服务。
- **可复现的比较：** 候选方案可以被描述为明确的 Plugin/Profile 组合，并在相同数据集、轨迹和指标上与 Baseline 比较。
- **低成本回滚：** 可撤销注册和明确的清理归属，使失败候选可以被移除，而不会残留 Tool、Hook 或外部资源。
- **更安全的晋升：** 开发 Agent 只负责产生候选改动；是否进入稳定 Harness，仍由测试、Benchmark、代码审查和显式晋升决定。

这属于**由 AI 辅助、受控的 Harness 演化**，而不是不受限制的运行时自修改。外部 Agent 不会自动获得生产环境权限，运行时实验也不会在缺少源码变更、验证和审查时自动晋升。因此 Plugin 不是最终目的，而是需要隔离、度量和回滚的 Harness 改动所使用的最小实用单元。

<details>
<summary>最小可运行组合示例</summary>

```python
import asyncio
from typing import Any, cast

from agentic import AGENT_FACTORY_SERVICE, AgentFactory, AgentLoopPlugin, PluginContext


class LabelPlugin:
  def __init__(self, label: str) -> None:
    self._label = label

  def apply(self, context: PluginContext) -> None:
    context.provide("label", self._label)


class EchoLoop:
  def __init__(self, context: PluginContext) -> None:
    self._label = cast("str", context.require("label"))

  async def run(
    self,
    task: str | dict[str, Any],
    task_id: str | None = None,
    *,
    extra_trace_metadata: dict[str, Any] | None = None,
  ) -> str:
    del task_id, extra_trace_metadata
    return f"{self._label}: {task}"


async def main() -> None:
  async with PluginContext() as root:
    await root.mount(AgentLoopPlugin(EchoLoop))
    factory = cast("AgentFactory", root.require(AGENT_FACTORY_SERVICE))

    async def setup(context: PluginContext) -> None:
      await context.mount(LabelPlugin("agent-1"))

    agent = await factory.create_agent(setup=setup)
    print(await agent.run("hello"))  # agent-1: hello


asyncio.run(main())
```

如需切换压缩策略，只需实现 `Compactor` 协议，并在 Agent setup 中挂载 `CompactionPlugin(your_compactor)`。Agent Loop 随后可以通过 `COMPACTION_SERVICE` 获取它，而不依赖具体实现。

</details>

## ✨ 核心能力

- 只追加轨迹保留运行时事件，并能重建模型在任意阶段实际可见的上下文。
- 模型客户端、工具、编排器、数据集、评估器、奖励函数和 recipe 策略均可替换。
- 上下文预算、压缩、回滚、重试与恢复、自我验证和工具限制用于支撑长时程运行。
- 每个任务都会记录轨迹、token 与耗时指标、评估产物，以及轨迹筛选所需的来源信息。
- SFT exporter 按运行时可见性规则重放轨迹，rollout 接口则负责连接外部训练系统。
- 严格的 YAML schema 和可移植路径方案让运行记录可以跨环境复现。

## 🔁 从执行到学习

每个任务都会写入一条只追加轨迹。这份记录是回放、评估和轨迹采集的共同输入。筛选后的轨迹可以继续导出给外部训练流程。

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/axisagentic-execution-learning-loop-zh-CN-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="docs/assets/axisagentic-execution-learning-loop-zh-CN-light.svg">
  <img alt="AxisAgentic 从执行到学习的数据闭环：运行轨迹支持回放、评估、轨迹采集、状态忠实的 SFT 导出和外部训练" src="docs/assets/axisagentic-execution-learning-loop-zh-CN-light.svg">
</picture>

运行时通过 marker 记录 rollback、context compaction 和 discard-all。重放这些 marker 可以还原模型在具体阶段看到的上下文。轨迹检查和 SFT 导出遵循同一套规则，因此不会把不可见历史或已回滚的动作写入监督样本。

内置 exporter 可以生成 Swift Agent 等训练格式，并保留 source trace、任务状态和可选元数据。外部训练流程负责最终的正确性筛选、loss mask 和优化。AxisAgentic 提供回放与导出边界，让推理和训练使用同一份交互历史。

## 🦅 旗舰参考系统：XYZ-Aquila

XYZ-Aquila 是基于 AxisAgentic 构建的搜索系统。它的 recipe 将搜索和抓取与上下文管理、恢复、评估、状态忠实的 SFT 导出组合在一起。底层接口也适用于其他模型客户端、工具和任务领域。

### 📊 评测结果

[Aquila 技术报告](https://xyz-lab.ai/blogs/ai4ai-at-scale/)给出了 XYZ-Aquila-mini 和 XYZ-Aquila-pro 在七项智能体基准上的评测结果。下图复现了其中六项基准的对比。

![XYZ-Aquila 在六项智能体搜索基准上的评测结果](docs/assets/aquila-benchmark-results.svg)

*图中指标：BrowseComp、BrowseComp-ZH、LiveBrowseComp 和 Humanity's Last Exam 使用 LLM-judge accuracy；DeepSearchQA 使用 macro F1；WideSearch 使用 item-level F1 Max@4。详情请参阅[评估与可复现性](docs/evaluation.zh-CN.md)。*

部分基线数值来自公开报告，所用评测框架、工具、裁判模型和日期并不相同。这张图适合做基准层面的对照，不能视为同一受控实验下的通用排名。

## 🚀 快速开始

AxisAgentic 需要 Python 3.12 或更高版本，以及一个 OpenAI 兼容模型端点。[快速开始](docs/getting-started.zh-CN.md)介绍安装、服务变量、recipe 配置、dry run、回放和 SFT 导出；完整配置项见[配置](docs/configuration.zh-CN.md)。

```bash
git clone https://github.com/yshenaw/DeepSeek-Harness-AxisAgentic.git
cd DeepSeek-Harness-AxisAgentic
python3.12 -m venv .venv
source .venv/bin/activate
./setup_env.sh
source .envs/axis_agentic_env.sh
cp .env.example .envs/.env
```

配置好模型服务和数据集后，可以在不启动任务的情况下校验 Web Search recipe：

```bash
cp recipe/web_search/configs/default.yaml my-search-run.yaml
python -m recipe.web_search.runners.run_eval_config \
  --config my-search-run.yaml \
  --dry-run
```

## 📚 文档

- [文档索引](docs/README.zh-CN.md)
- [快速开始](docs/getting-started.zh-CN.md)
- [配置](docs/configuration.zh-CN.md)
- [架构](docs/architecture.zh-CN.md)
- [项目结构](docs/project-structure.zh-CN.md)
- [评估与可复现性](docs/evaluation.zh-CN.md)
- [Recipes](recipe/README.md)

## 🤝 参与贡献

[贡献指南](CONTRIBUTING.md)介绍开发环境和提交前检查。参与者需要遵守[行为准则](CODE_OF_CONDUCT.md)。安全漏洞请按[安全策略](SECURITY.md)上报。

## 📜 许可证

除非另有说明，AxisAgentic 采用 [Apache License 2.0](LICENSE) 许可。第三方归属和许可说明请参阅 [NOTICE](NOTICE)。

## 📝 上游引用

对于本仓库保留的 AxisAgentic 实现，请按以下条目引用上游软件：

```bibtex
@software{wang2026axisagentic,
  author       = {Wang, Jinyu and Zhang, Yifei and {{XYZ Agentic Team}}},
  title        = {AxisAgentic: An Extensible Runtime and Trajectory-Collection Framework for Long-Horizon Agents},
  organization = {XYZ AI Lab},
  year         = {2026},
  url          = {https://github.com/XYZ-AI-Lab/AxisAgentic}
}
```
