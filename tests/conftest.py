"""Native HA integration fixtures. Tests never use a physical gateway."""
import pytest


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations, request):
    if request.node.path.name == "test_transport.py":
        # The protocol suite intentionally uses a loopback-only synthetic server.
        request.getfixturevalue("socket_enabled")
    yield
