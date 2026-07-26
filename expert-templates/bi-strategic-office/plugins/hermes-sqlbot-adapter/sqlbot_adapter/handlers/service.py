"""Compatibility shim — prefer sqlbot_adapter.service."""

from sqlbot_adapter.service import SQLBotService, get_service, reset_service_for_tests

__all__ = ["SQLBotService", "get_service", "reset_service_for_tests"]
