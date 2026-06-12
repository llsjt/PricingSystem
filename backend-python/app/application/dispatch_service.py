"""Application-layer dispatch entrypoint.

The implementation remains in ``app.services.dispatch_service`` while the
architecture-facing import path is kept stable for plan conformance.
"""

from app.services.dispatch_service import DispatchService

__all__ = ["DispatchService"]
