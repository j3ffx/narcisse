"""uvicorn, made to close the live streams first when it stops."""

import socket

import uvicorn


class Server(uvicorn.Server):
    """Without this, stopping would wait for every open browser tab to drop its event stream."""

    async def shutdown(self, sockets: list[socket.socket] | None = None) -> None:
        services = getattr(getattr(self.config.app, "state", None), "services", None)
        if services is not None:
            services.bus.close()
        await super().shutdown(sockets)
