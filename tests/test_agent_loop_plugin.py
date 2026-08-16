# Copyright 2026 XYZ AI Lab and contributors.
# SPDX-License-Identifier: Apache-2.0

import asyncio
from typing import Any, cast

import pytest

from agentic.agent_loop import AGENT_FACTORY_SERVICE, AgentFactory, AgentLoopPlugin
from agentic.config import OrchestrationConfig
from agentic.contracts import ConversationMessage, ModelResponse
from agentic.model_clients import CallableModelClient
from agentic.orchestration import TaskOrchestrator
from agentic.plugin import PluginContext


class _TestLoop:
    def __init__(self, marker: object) -> None:
        self.marker = marker

    async def run(
        self,
        task: str | dict[str, Any],
        task_id: str | None = None,
        *,
        extra_trace_metadata: dict[str, Any] | None = None,
    ) -> tuple[object, str | dict[str, Any]]:
        del task_id, extra_trace_metadata
        return self.marker, task


def test_agent_loop_plugin_creates_isolated_agents_and_owns_their_lifetime() -> None:
    first_marker = object()
    second_marker = object()

    def build_loop(context: PluginContext) -> _TestLoop:
        return _TestLoop(context.require("marker"))

    def setup(marker: object):
        def apply(context: PluginContext) -> None:
            context.provide("marker", marker)

        return apply

    async def run() -> None:
        context = PluginContext()
        dispose_loop = await context.mount(AgentLoopPlugin(build_loop))
        factory = cast("AgentFactory", context.require(AGENT_FACTORY_SERVICE))
        first_agent = await factory.create_agent(setup=setup(first_marker))
        second_agent = await factory.create_agent(setup=setup(second_marker))

        assert await first_agent.run("first") == (first_marker, "first")
        assert await second_agent.run("second") == (second_marker, "second")
        assert context.get("marker") is None

        await dispose_loop()

        assert first_agent.closed
        assert second_agent.closed
        assert context.get(AGENT_FACTORY_SERVICE) is None
        with pytest.raises(RuntimeError, match="closed agent"):
            await first_agent.run("after close")
        with pytest.raises(RuntimeError, match="not active"):
            await factory.create_agent()

    asyncio.run(run())


def test_agent_loop_plugin_adapts_task_orchestrator() -> None:
    async def complete(
        _messages: list[ConversationMessage],
        _tools: list[dict[str, Any]] | None,
        _tool_choice: str | None,
    ) -> ModelResponse:
        return ModelResponse(message=ConversationMessage.assistant("plugin loop result"))

    def build_loop(_context: PluginContext) -> TaskOrchestrator:
        return TaskOrchestrator(
            config=OrchestrationConfig(name="plugin-test"),
            model_client=CallableModelClient(complete, context_window=4096, max_output_tokens=128),
        )

    async def run() -> None:
        context = PluginContext()
        await context.mount(AgentLoopPlugin(build_loop))
        factory = cast("AgentFactory", context.require(AGENT_FACTORY_SERVICE))
        agent = await factory.create_agent()

        result = await agent.run("test task")

        assert result.output == "plugin loop result"
        await context.close()

    asyncio.run(run())
