"""Core composition orchestrator."""

from __future__ import annotations

from vera.engine.anti_repetition import AntiRepetitionGuard
from vera.engine.composer import Composer, compose
from vera.engine.conversation_manager import ConversationManager
from vera.engine.suppression import SuppressionGuard

__all__ = ["AntiRepetitionGuard", "Composer", "ConversationManager", "SuppressionGuard", "compose"]
