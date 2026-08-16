# Copyright 2026 XYZ AI Lab and contributors.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from agentic.contracts import ConversationMessage
    from agentic.plugin import PluginContext

COMPACTION_SERVICE = "compaction"


class Compactor(Protocol):
    @property
    def latest_summary(self) -> str:
        """Return the latest compacted state, or an empty sentinel before compaction."""
        ...

    def should_trigger(self, turn_count: int) -> bool:
        """Return whether this turn should be compacted."""
        ...

    async def maybe_compress(
        self,
        turn_count: int,
        visible_conversation: list[ConversationMessage],
        task_text: str,
    ) -> tuple[ConversationMessage | None, str | None]:
        """Return an append-only compaction marker and its summary when triggered."""
        ...


class CompactionPlugin:
    def __init__(self, compactor: Compactor) -> None:
        self._compactor = compactor

    def apply(self, context: PluginContext) -> None:
        context.provide(COMPACTION_SERVICE, self._compactor)
