"""Fixtures : intégration personnalisée activée et caméra simulée (protocole DVRIP) sur 127.0.0.1."""
import asyncio

import pytest

from . import fake_camera


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
async def camera(socket_enabled):
    """Caméra simulée ; renvoie son port."""
    fake_camera.reset()
    server = await asyncio.start_server(fake_camera.handle, "127.0.0.1", 0)
    yield server.sockets[0].getsockname()[1]
    server.close()
    for w in list(fake_camera.CONNECTIONS):
        w.close()
    try:
        await asyncio.wait_for(server.wait_closed(), 5)
    except TimeoutError:
        pass
