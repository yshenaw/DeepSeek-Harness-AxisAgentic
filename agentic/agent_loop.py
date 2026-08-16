# Copyright 2026 XYZ AI Lab and contributors.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from agentic.plugin import PluginContext

AGENT_FACTORY_SERVICE = "agent_factory"


class AgentLoop(Protocol):
    async def run(
        self,
        task: str | dict[str, Any],
        task_id: str | None = None,
        *,
        extra_trace_metadata: dict[str, Any] | None = None,
    ) -> Any:
        """Run one task."""
        ...


type AgentSetup = Callable[[PluginContext], Awaitable[None] | None]
type AgentLoopBuilder = Callable[[PluginContext], AgentLoop | Awaitable[AgentLoop]]


class Agent:
    def __init__(self, *, context: PluginContext, loop: AgentLoop) -> None:
        self.context = context
        self.loop = loop
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    async def run(
        self,
        task: str | dict[str, Any],
        task_id: str | None = None,
        *,
        extra_trace_metadata: dict[str, Any] | None = None,
    ) -> Any:
        if self._closed:
            raise RuntimeError("Cannot run a closed agent.")
        return await self.loop.run(task, task_id=task_id, extra_trace_metadata=extra_trace_metadata)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self.context.close()


class AgentFactory:
    def __init__(self, *, owner: PluginContext, builder: AgentLoopBuilder) -> None:
        self._owner = owner
        self._builder = builder

    async def create_agent(self, *, setup: AgentSetup | None = None) -> Agent:
        if self._owner.closed:
            raise RuntimeError("Agent factory is not active.")
        context = PluginContext()
        try:
            if setup is not None:
                setup_result = setup(context)
                if inspect.isawaitable(setup_result):
                    await setup_result
            loop = self._builder(context)
            if inspect.isawaitable(loop):
                loop = await loop
            agent = Agent(context=context, loop=loop)
            self._owner.effect(agent.close)
        except Exception:
            await context.close()
            raise
        return agent


class AgentLoopPlugin:
    def __init__(self, builder: AgentLoopBuilder) -> None:
        self._builder = builder

    def apply(self, context: PluginContext) -> None:
        context.provide(AGENT_FACTORY_SERVICE, AgentFactory(owner=context, builder=self._builder))
