"""Shared agent protocol for Phase 4 reasoning."""

from typing import Dict, Protocol


class ReasoningAgent(Protocol):
    """Protocol implemented by all Phase 4 reasoning agents."""

    def reason(self, observations: Dict) -> Dict:
        """Return a reasoning result for the current observations."""
        ...
