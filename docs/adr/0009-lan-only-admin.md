# 0009. Admin area reachable from the LAN only

- Status: accepted
- Date: 2026-10-14

## Context
The admin area can hide, rename, reset and delete players and change the signup word.
The app itself is public, behind a reverse proxy, so the admin routes share a host
with the game. A password alone would leave them open to guessing from anywhere, and
would let outsiders probe which admin routes exist.

## Decision
- An ASGI middleware runs before routing and before any request body is read. A
  request under `/api/admin` that does not come from an allowed client gets the same
  404 as any unknown path, for every method, so the routes cannot be told apart from
  paths that do not exist. The password is never checked for those clients.
- Allowed clients are set by `ADMIN_ALLOWED_CIDRS`. The default is
  `192.168.0.0/16,127.0.0.1/32,::1/128`. It is deliberately narrow and does not
  include container or overlay ranges, which would admit the proxy itself.
- The gate and the static file handler normalise paths with the same code (case
  folding, repeated decoding, `.` and `..` segments), so an encoded or oddly cased
  path cannot slip past one while the other treats it as admin.
- Proxy handling fails closed. A request carrying forwarding headers from a peer that
  is not a trusted proxy is denied. A trusted proxy that names no untrusted client is
  denied. Admin is also disabled, with every route a 404, when no admin password is
  configured.
- The password is read from a file, hashed once at boot with argon2id, and compared
  by hash. Logins are capped at 10 per client address per 10 minutes.
- A successful login creates a random session token. Only its SHA-256 is stored, with
  an expiry of 8 hours. The cookie is `HttpOnly`, `SameSite=Strict` and scoped to
  `/api/admin`, and state-changing requests need a custom header.
- Logins (successful and failed), logouts and every admin action write a row to an
  audit table. A failed login records no password and no session.

## Alternatives rejected
- **Password-only admin on the internet.** One weak or leaked password would expose
  every player record, and the routes would be visible to scanners.
- **A VPN or a separate admin service.** Strong isolation, but a second deployment, a
  second image and a VPN to maintain for a handful of actions.
- **An authentication layer in the reverse proxy.** It would keep the app unaware of
  the rule, and a proxy misconfiguration or a direct path to the app would silently
  remove the protection. Keeping the check in the app keeps it with the code it
  protects.

## Consequences
Admin works only from the home network. If the proxy does not see real client
addresses, or its trusted range is too wide, admin stops working (404) rather than
opening up. The deployment guide has a spoof check to run after every proxy change.
The allowed networks are configuration, so a household on a different address range
sets `ADMIN_ALLOWED_CIDRS`.
