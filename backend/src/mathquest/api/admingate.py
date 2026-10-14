"""Pure ASGI gate for /api/admin: runs before routing and before any body is read.

An admin request that is not from an allowed LAN client, or that arrives while no admin password
is configured, gets the standard 404 for every method, so the routes cannot be told apart from
unknown paths.
"""

from starlette.types import ASGIApp, Receive, Scope, Send

from mathquest.api.clientip import IPNetwork, client_ip, ip_in_networks
from mathquest.api.errors import not_found_response
from mathquest.api.pathnorm import scope_is_under

_FORWARD_HEADERS = (b"x-forwarded-for", b"forwarded")


def is_admin_path(scope: Scope) -> bool:
    return scope_is_under(scope, ("api", "admin"))


def _allowed(scope: Scope) -> bool:
    app = scope["app"]
    state = app.state
    networks: tuple[IPNetwork, ...] | None = getattr(state, "admin_networks", None)
    trusted: tuple[IPNetwork, ...] | None = getattr(state, "trusted_networks", None)
    if networks is None or trusted is None or getattr(state, "admin_password_hash", None) is None:
        return False
    client = scope.get("client")
    peer = client[0] if client else None
    forwarded = [
        value.decode("latin-1") for name, value in scope["headers"] if name == b"x-forwarded-for"
    ]
    carries_forwarding = any(name in _FORWARD_HEADERS for name, _ in scope["headers"])
    if carries_forwarding and (peer is None or not ip_in_networks(peer, trusted)):
        return False
    resolved = client_ip(peer, forwarded, trusted)
    if peer is not None and ip_in_networks(peer, trusted) and ip_in_networks(resolved, trusted):
        # A proxy peer must name an untrusted client; falling back to the proxy itself is a deny.
        return False
    return ip_in_networks(resolved, networks)


class AdminGate:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and is_admin_path(scope) and not _allowed(scope):
            await not_found_response()(scope, receive, send)
            return
        await self.app(scope, receive, send)
