"""Gateway credential resolution for sherlock-proxyhat.

Mirrors the other ProxyHat integrations: explicit ``username``/``password``
(or ``PROXYHAT_USERNAME``/``PROXYHAT_PASSWORD``) win; otherwise an API key
(``PROXYHAT_API_KEY``) looks up your sub-users via the official ``proxyhat`` SDK
and picks an active one with remaining traffic — or the one named by ``sub_user``.
Everything here except the sub-user lookup is offline.
"""

from __future__ import annotations

import os

from proxyhat import ProxyHat


class ProxyHatConfigError(RuntimeError):
    """Raised when ProxyHat credentials cannot be resolved."""


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    return value.strip() if value and value.strip() else None


def resolve_credentials(
    *,
    api_key: str | None = None,
    username: str | None = None,
    password: str | None = None,
    sub_user: str | None = None,
) -> tuple[str, str]:
    """Resolve a sub-user's ``(proxy_username, proxy_password)``.

    Options win over environment variables. Precedence:

    1. explicit ``username`` + ``password`` (``PROXYHAT_USERNAME`` / ``PROXYHAT_PASSWORD``)
    2. ``api_key`` (``PROXYHAT_API_KEY``) → auto-pick an active sub-user, or the
       one named by ``sub_user`` (``PROXYHAT_SUBUSER``).
    """
    username = username or _env("PROXYHAT_USERNAME")
    password = password or _env("PROXYHAT_PASSWORD")
    if username and password:
        return username, password

    api_key = api_key or _env("PROXYHAT_API_KEY")
    if not api_key:
        raise ProxyHatConfigError(
            "sherlock-proxyhat: no credentials. Pass --proxyhat-api-key (or PROXYHAT_API_KEY), "
            "or --proxyhat-username + --proxyhat-password (PROXYHAT_USERNAME / PROXYHAT_PASSWORD)."
        )

    return _resolve_sub_user(api_key, sub_user or _env("PROXYHAT_SUBUSER"))


def _resolve_sub_user(api_key: str, want: str | None) -> tuple[str, str]:
    users = ProxyHat(api_key=api_key).sub_users.list()
    usable = [u for u in users if not u.suspended_at and (u.traffic_limit == 0 or u.used_traffic < u.traffic_limit)]
    if want:
        chosen = next((u for u in users if u.uuid == want or u.name == want), None)
    else:
        chosen = usable[0] if usable else None

    if chosen is None or not chosen.proxy_username or not chosen.proxy_password:
        raise ProxyHatConfigError(
            f'sherlock-proxyhat: no sub-user matched "{want}" (or it has no proxy credentials).'
            if want
            else "sherlock-proxyhat: no usable sub-user found (all suspended or out of traffic). "
            "Create one, top up, or pass --proxyhat-sub-user."
        )
    return chosen.proxy_username, chosen.proxy_password
