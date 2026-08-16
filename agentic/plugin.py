# Copyright 2026 XYZ AI Lab and contributors.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Protocol, Self

type Disposable = Callable[[], Awaitable[None] | None]
type PluginDisposer = Callable[[], Awaitable[None]]


class Plugin(Protocol):
    def apply(self, context: PluginContext) -> Disposable | Awaitable[Disposable | None] | None:
        """Install the plugin and optionally return one cleanup callback."""
        ...


class PluginContext:
    def __init__(self, *, _services: dict[str, object] | None = None) -> None:
        self._disposers: list[PluginDisposer] = []
        self._services = _services if _services is not None else {}
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def effect(self, dispose: Disposable) -> PluginDisposer:
        if self._closed:
            raise RuntimeError("Cannot register an effect on a closed plugin context.")
        disposed = False

        async def owned_dispose() -> None:
            nonlocal disposed
            if disposed:
                return
            disposed = True
            result = dispose()
            if inspect.isawaitable(result):
                await result

        self._disposers.append(owned_dispose)
        return owned_dispose

    def provide(self, name: str, service: object) -> PluginDisposer:
        if self._closed:
            raise RuntimeError("Cannot provide a service on a closed plugin context.")
        if name in self._services:
            raise ValueError(f"Service '{name}' is already provided.")
        self._services[name] = service

        def dispose() -> None:
            if self._services.get(name) is service:
                self._services.pop(name, None)

        return self.effect(dispose)

    def get(self, name: str) -> object | None:
        return self._services.get(name)

    def require(self, name: str) -> object:
        service = self.get(name)
        if service is None:
            raise LookupError(f"Service '{name}' is not available.")
        return service

    async def mount(self, plugin: Plugin) -> PluginDisposer:
        if self._closed:
            raise RuntimeError("Cannot mount a plugin on a closed plugin context.")
        plugin_context = PluginContext(_services=self._services)
        dispose_plugin = self.effect(plugin_context.close)
        try:
            result = plugin.apply(plugin_context)
            if inspect.isawaitable(result):
                result = await result
            if result is not None:
                plugin_context.effect(result)
        except Exception:
            await dispose_plugin()
            raise
        return dispose_plugin

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        errors: list[Exception] = []
        for dispose in reversed(self._disposers):
            try:
                await dispose()
            except Exception as error:
                errors.append(error)
        self._disposers.clear()
        if errors:
            raise ExceptionGroup("Plugin cleanup failed.", errors)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        await self.close()
