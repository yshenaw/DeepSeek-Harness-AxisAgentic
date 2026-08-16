# Copyright 2026 XYZ AI Lab and contributors.
# SPDX-License-Identifier: Apache-2.0

import asyncio

import pytest

from agentic.plugin import PluginContext


def test_plugin_context_disposes_effects_in_reverse_order() -> None:
    events: list[str] = []

    class TestPlugin:
        def apply(self, context: PluginContext) -> None:
            context.effect(lambda: events.append("first"))

            async def dispose_second() -> None:
                events.append("second")

            context.effect(dispose_second)

    async def run() -> None:
        context = PluginContext()
        await context.mount(TestPlugin())
        await context.close()
        await context.close()

    asyncio.run(run())

    assert events == ["second", "first"]


def test_unmount_disposes_only_the_owned_plugin() -> None:
    events: list[str] = []

    class TestPlugin:
        def __init__(self, name: str) -> None:
            self.name = name

        def apply(self, context: PluginContext) -> None:
            context.effect(lambda: events.append(self.name))

    async def run() -> None:
        context = PluginContext()
        dispose_first = await context.mount(TestPlugin("first"))
        await context.mount(TestPlugin("second"))
        await dispose_first()
        assert events == ["first"]
        await context.close()

    asyncio.run(run())

    assert events == ["first", "second"]


def test_plugin_context_rolls_back_failed_plugin_setup() -> None:
    events: list[str] = []

    class FailingPlugin:
        def apply(self, context: PluginContext) -> None:
            context.effect(lambda: events.append("disposed"))
            raise ValueError("setup failed")

    async def run() -> None:
        context = PluginContext()
        with pytest.raises(ValueError, match="setup failed"):
            await context.mount(FailingPlugin())
        assert events == ["disposed"]
        await context.close()

    asyncio.run(run())

    assert events == ["disposed"]


def test_plugin_service_is_visible_until_its_plugin_unmounts() -> None:
    service = object()

    class ProviderPlugin:
        def apply(self, context: PluginContext) -> None:
            context.provide("test_service", service)

    async def run() -> None:
        context = PluginContext()
        dispose = await context.mount(ProviderPlugin())
        assert context.require("test_service") is service
        await dispose()
        assert context.get("test_service") is None
        with pytest.raises(LookupError, match="test_service"):
            context.require("test_service")

    asyncio.run(run())
