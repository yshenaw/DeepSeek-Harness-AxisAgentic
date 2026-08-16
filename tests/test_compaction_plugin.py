# Copyright 2026 XYZ AI Lab and contributors.
# SPDX-License-Identifier: Apache-2.0

import asyncio
from typing import Any, cast

from agentic.agent_loop import AGENT_FACTORY_SERVICE, AgentFactory, AgentLoopPlugin
from agentic.compaction import COMPACTION_SERVICE, CompactionPlugin, Compactor
from agentic.config import OrchestrationConfig
from agentic.contracts import ConversationMessage
from agentic.model_clients import CallableModelClient
from agentic.plugin import PluginContext
from recipe.web_search.agent.orchestrator import WebSearchTaskOrchestrator


class _StubCompactor:
    @property
    def latest_summary(self) -> str:
        return "summary"

    def should_trigger(self, turn_count: int) -> bool:
        return turn_count > 0

    async def maybe_compress(
        self,
        turn_count: int,
        visible_conversation: list[ConversationMessage],
        task_text: str,
    ) -> tuple[ConversationMessage | None, str | None]:
        del turn_count, visible_conversation, task_text
        return None, self.latest_summary


class _LoopWithCompactor:
    def __init__(self, compactor: Compactor) -> None:
        self.compactor = compactor

    async def run(
        self,
        task: str | dict[str, Any],
        task_id: str | None = None,
        *,
        extra_trace_metadata: dict[str, Any] | None = None,
    ) -> str:
        del task, task_id, extra_trace_metadata
        return self.compactor.latest_summary


def test_compaction_plugin_is_agent_scoped_and_disposed_with_agent() -> None:
    compactor = _StubCompactor()

    async def setup(context: PluginContext) -> None:
        await context.mount(CompactionPlugin(compactor))

    def build_loop(context: PluginContext) -> _LoopWithCompactor:
        return _LoopWithCompactor(cast("Compactor", context.require(COMPACTION_SERVICE)))

    async def run() -> None:
        root = PluginContext()
        await root.mount(AgentLoopPlugin(build_loop))
        factory = cast("AgentFactory", root.require(AGENT_FACTORY_SERVICE))
        agent = await factory.create_agent(setup=setup)

        assert root.get(COMPACTION_SERVICE) is None
        assert agent.context.require(COMPACTION_SERVICE) is compactor
        assert await agent.run("task") == "summary"

        await agent.close()

        assert agent.context.get(COMPACTION_SERVICE) is None
        await root.close()

    asyncio.run(run())


def test_compaction_plugin_supplies_web_search_orchestrator() -> None:
    compactor = _StubCompactor()

    async def setup(context: PluginContext) -> None:
        await context.mount(CompactionPlugin(compactor))

    def build_loop(context: PluginContext) -> WebSearchTaskOrchestrator:
        async def unused_complete(*_args: Any, **_kwargs: Any) -> None:
            return None

        return WebSearchTaskOrchestrator(
            config=OrchestrationConfig(name="compaction-plugin-test"),
            model_client=CallableModelClient(unused_complete, context_window=4096, max_output_tokens=128),
            context_compression_manager=cast("Compactor", context.require(COMPACTION_SERVICE)),
        )

    async def run() -> None:
        root = PluginContext()
        await root.mount(AgentLoopPlugin(build_loop))
        factory = cast("AgentFactory", root.require(AGENT_FACTORY_SERVICE))
        agent = await factory.create_agent(setup=setup)

        loop = cast("WebSearchTaskOrchestrator", agent.loop)
        assert loop._context_compression_manager is compactor

        await root.close()

    asyncio.run(run())
