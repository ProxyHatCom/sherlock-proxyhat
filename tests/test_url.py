from types import SimpleNamespace

import pytest

from sherlock_proxyhat import ProxyHatConfigError, proxyhat_proxy_url, resolve_credentials


def sub_user(**kw):
    base = dict(
        uuid="u",
        name=None,
        proxy_username="ph-1",
        proxy_password="pw",
        traffic_limit=0,
        used_traffic=0,
        suspended_at=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


class TestProxyUrl:
    def test_url_shape_and_geo(self):
        url = proxyhat_proxy_url(username="ph-1", password="pw", country="us")
        assert url.startswith("http://ph-1-country-us:pw@gate.proxyhat.com:8080")

    def test_rotating_by_default(self):
        # Sherlock reuses one proxy for the whole run, so the default rotates:
        # no session id / ttl means the gateway hands out a fresh IP per connection.
        url = proxyhat_proxy_url(username="ph-1", password="pw")
        assert "-sid-" not in url
        assert "-ttl-" not in url
        assert url.startswith("http://ph-1-country-any:pw@")

    def test_sticky_opt_in_pins_ip(self):
        url = proxyhat_proxy_url(username="ph-1", password="pw", sticky=True)
        assert "-sid-" in url
        assert "-ttl-30m" in url

    def test_custom_sticky_ttl(self):
        url = proxyhat_proxy_url(username="ph-1", password="pw", sticky="2h")
        assert "-ttl-2h" in url

    def test_full_geo_targeting(self):
        url = proxyhat_proxy_url(
            username="ph-1",
            password="pw",
            country="de",
            region="berlin",
            city="berlin",
            filter="high",
        )
        assert "ph-1-country-de" in url
        assert "-region-berlin" in url
        assert "-city-berlin" in url
        assert "-filter-high" in url

    def test_socks5_protocol(self):
        url = proxyhat_proxy_url(username="ph-1", password="pw", protocol="socks5")
        assert url.startswith("socks5://ph-1-country-any:pw@gate.proxyhat.com:1080")


class TestCredentialResolution:
    def test_explicit_username_password(self):
        assert resolve_credentials(username="ph-1", password="pw") == ("ph-1", "pw")

    def test_raises_without_credentials(self, monkeypatch):
        for var in ("PROXYHAT_API_KEY", "PROXYHAT_USERNAME", "PROXYHAT_PASSWORD", "PROXYHAT_SUBUSER"):
            monkeypatch.delenv(var, raising=False)
        with pytest.raises(ProxyHatConfigError):
            resolve_credentials()

    def test_api_key_picks_active_sub_user(self, monkeypatch):
        users = [
            sub_user(uuid="s", proxy_username="susp", suspended_at="2026-01-01"),
            sub_user(uuid="g", proxy_username="good", traffic_limit=100, used_traffic=100),
            sub_user(uuid="ok", proxy_username="ok", traffic_limit=100, used_traffic=1),
        ]
        fake_client = SimpleNamespace(sub_users=SimpleNamespace(list=lambda: users))
        monkeypatch.setattr("sherlock_proxyhat._resolve.ProxyHat", lambda **kw: fake_client)
        assert resolve_credentials(api_key="ph_key") == ("ok", "pw")

    def test_api_key_named_sub_user(self, monkeypatch):
        users = [sub_user(uuid="a", proxy_username="a"), sub_user(uuid="b", name="prod", proxy_username="b")]
        fake_client = SimpleNamespace(sub_users=SimpleNamespace(list=lambda: users))
        monkeypatch.setattr("sherlock_proxyhat._resolve.ProxyHat", lambda **kw: fake_client)
        assert resolve_credentials(api_key="ph_key", sub_user="prod") == ("b", "pw")

    def test_api_key_no_usable_sub_user(self, monkeypatch):
        users = [sub_user(traffic_limit=100, used_traffic=100)]
        fake_client = SimpleNamespace(sub_users=SimpleNamespace(list=lambda: users))
        monkeypatch.setattr("sherlock_proxyhat._resolve.ProxyHat", lambda **kw: fake_client)
        with pytest.raises(ProxyHatConfigError):
            resolve_credentials(api_key="ph_key")

    def test_url_resolves_via_api_key(self, monkeypatch):
        users = [sub_user(proxy_username="good", proxy_password="secret")]
        fake_client = SimpleNamespace(sub_users=SimpleNamespace(list=lambda: users))
        monkeypatch.setattr("sherlock_proxyhat._resolve.ProxyHat", lambda **kw: fake_client)
        url = proxyhat_proxy_url(api_key="ph_key", country="us")
        assert url.startswith("http://good-country-us:secret@gate.proxyhat.com:8080")
