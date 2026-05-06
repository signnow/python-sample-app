from abc import ABC, abstractmethod
from typing import Any

from fastapi import Response


class SampleController(ABC):
    """Contract implemented by every sample's IndexController.

    Mirrors Java's ExampleInterface (handleGet / handlePost).
    """

    @abstractmethod
    def handle_get(self, query_params: dict[str, str]) -> Response:
        """Handle GET /samples/{name}."""

    @abstractmethod
    def handle_post(self, form_data: dict[str, Any]) -> Response:
        """Handle POST /api/samples/{name}."""
