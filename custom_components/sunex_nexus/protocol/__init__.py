"""Shared, read-only SUNEX transport; no model register meanings are assumed."""
from .transport import NexusTransport, ProtocolError, RegisterSnapshot

__all__ = ["NexusTransport", "ProtocolError", "RegisterSnapshot"]
