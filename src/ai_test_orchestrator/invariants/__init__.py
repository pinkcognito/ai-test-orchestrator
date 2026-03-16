"""
Invariant check plugin registry.

Invariants are auto-discovered from modules in this package. Each module
should define one or more classes implementing the InvariantCheck protocol.
Register them by adding to the REGISTRY list.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import InvariantCheck

# Global registry — populated by register() calls or auto-discovery
REGISTRY: list[InvariantCheck] = []


def register(check: InvariantCheck) -> InvariantCheck:
    """Register an invariant check instance. Returns the check for decorator use."""
    REGISTRY.append(check)
    return check


def get_all_checks() -> list[InvariantCheck]:
    """Return all registered invariant checks."""
    return list(REGISTRY)


def clear_registry() -> None:
    """Clear all registered checks. Useful for testing."""
    REGISTRY.clear()
