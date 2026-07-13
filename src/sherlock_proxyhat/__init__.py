"""sherlock-proxyhat — run the Sherlock OSINT tool through ProxyHat residential proxies."""

from sherlock_proxyhat._resolve import ProxyHatConfigError, resolve_credentials
from sherlock_proxyhat.cli import build_command, main, proxyhat_proxy_url

__all__ = [
    "ProxyHatConfigError",
    "build_command",
    "main",
    "proxyhat_proxy_url",
    "resolve_credentials",
]
__version__ = "0.1.0"
