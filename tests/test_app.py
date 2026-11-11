"""Testes sem rede: o MSAL e o servidor de chaves da Microsoft sao substituidos por dubles.

O ID token e assinado de verdade (RSA + PyJWT), entao a validacao real roda.
"""
import time
import types

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app import create_app
from config import Settings

TENANT = "11111111-2222-3333-4444-555555555555"
CLIENT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
ISSUER = f"https://login.microsoftonline.com/{TENANT}/v2.0"

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def make_token(key=KEY, **overrides):
    now = int(time.time())
    claims = {
        "iss": ISSUER, "aud": CLIENT, "sub": "sub-123", "oid": "oid-123", "tid": TENANT,
        "name": "Maria Teste", "preferred_username": "maria@empresa.com.br",
        "iat": now, "nbf": now, "exp": now + 3600,
    }
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "k1"})


class FakeJwks:
    """Faz o papel do PyJWKClient, devolvendo a chave publica de teste."""
    def get_signing_key_from_jwt(self, _token):
        return types.SimpleNamespace(key=KEY.public_key())


class FakeMsal:
    def __init__(self, result=None, error=None):
        self.result, self.error = result, error

    def initiate_auth_code_flow(self, scopes, redirect_uri):
        assert scopes == []
        return {"state": "st", "nonce": "n", "code_verifier": "v", "redirect_uri": redirect_uri,
                "auth_uri": "https://login.microsoftonline.com/fake/authorize?state=st"}

    def acquire_token_by_auth_code_flow(self, flow, args):
        if self.error:
            raise self.error
        return self.result


@pytest.fixture
def settings():
    return Settings(tenant_id=TENANT, client_id=CLIENT, client_secret="x", secret_key="k")


def client_for(settings, **msal_kwargs):
    app = create_app(settings, msal_app=FakeMsal(**msal_kwargs), jwks_client=FakeJwks())
    c = app.test_client()
    c.get("/login")  # prepara o "flow" na sessao, como o navegador faria
    return c


def callback(c):
    return c.get("/auth/callback?code=abc&state=st")


def test_profile_without_login_redirects_to_login(settings):
    c = create_app(settings, msal_app=FakeMsal(), jwks_client=FakeJwks()).test_client()
    r = c.get("/profile")
    assert r.status_code == 302 and r.headers["Location"].startswith("/login")


def test_login_redirects_to_microsoft(settings):
    c = create_app(settings, msal_app=FakeMsal(), jwks_client=FakeJwks()).test_client()
    r = c.get("/login")
    assert r.status_code == 302
    assert r.headers["Location"].startswith("https://login.microsoftonline.com/")


def test_successful_login_opens_session(settings):
    c = client_for(settings, result={"id_token": make_token()})
    r = callback(c)
    assert r.status_code == 302 and r.headers["Location"] == "/profile"
    page = c.get("/profile")
    assert page.status_code == 200 and b"Maria Teste" in page.data


def test_next_param_is_used_after_login(settings):
    app = create_app(settings, msal_app=FakeMsal(result={"id_token": make_token()}), jwks_client=FakeJwks())
    c = app.test_client()
    c.get("/login?next=/profile")
    assert callback(c).headers["Location"] == "/profile"


def test_open_redirect_is_blocked(settings):
    app = create_app(settings, msal_app=FakeMsal(result={"id_token": make_token()}), jwks_client=FakeJwks())
    c = app.test_client()
    c.get("/login?next=//evil.example.com")
    assert callback(c).headers["Location"] == "/profile"


def test_state_mismatch_is_rejected(settings):
    c = client_for(settings, error=ValueError("state mismatch"))
    assert callback(c).status_code == 400
    assert c.get("/profile").status_code == 302  # continua sem sessao


def test_callback_without_flow_is_rejected(settings):
    c = create_app(settings, msal_app=FakeMsal(), jwks_client=FakeJwks()).test_client()
    assert c.get("/auth/callback?code=abc&state=st").status_code == 400


def test_identity_provider_error_is_rejected(settings):
    c = client_for(settings, result={"error": "access_denied", "error_description": "negado"})
    assert callback(c).status_code == 401
    assert c.get("/profile").status_code == 302


@pytest.mark.parametrize("token_kwargs", [
    {"aud": "outro-app"},                                   # emitido para outro app
    {"iss": "https://login.microsoftonline.com/x/v2.0"},    # emissor errado
    {"tid": "99999999-9999-9999-9999-999999999999"},        # tenant errado
    {"exp": int(time.time()) - 3600},                       # expirado
])
def test_invalid_claims_are_rejected(settings, token_kwargs):
    c = client_for(settings, result={"id_token": make_token(**token_kwargs)})
    assert callback(c).status_code == 401
    assert c.get("/profile").status_code == 302


def test_bad_signature_is_rejected(settings):
    c = client_for(settings, result={"id_token": make_token(key=OTHER_KEY)})
    assert callback(c).status_code == 401


def test_missing_id_token_is_rejected(settings):
    c = client_for(settings, result={"access_token": "so-access-token"})
    assert callback(c).status_code == 401


def test_logout_clears_session_and_goes_to_microsoft(settings):
    c = client_for(settings, result={"id_token": make_token()})
    callback(c)
    r = c.get("/logout")
    assert r.status_code == 302
    assert r.headers["Location"].startswith(f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/logout")
    assert c.get("/profile").status_code == 302


def test_no_token_is_stored_in_cookie(settings):
    c = client_for(settings, result={"id_token": make_token()})
    callback(c)
    with c.session_transaction() as s:
        assert set(s["user"]) == {"name", "username", "oid", "tid"}
        assert "id_token" not in s and "access_token" not in s


@pytest.mark.parametrize("bad", ["common", "organizations", "empresa.onmicrosoft.com"])
def test_tenant_must_be_guid(bad):
    with pytest.raises(RuntimeError):
        Settings(tenant_id=bad, client_id=CLIENT, client_secret="x", secret_key="k")


def test_missing_env_vars(monkeypatch):
    for n in ("TENANT_ID", "CLIENT_ID", "CLIENT_SECRET", "SECRET_KEY"):
        monkeypatch.delenv(n, raising=False)
    monkeypatch.setattr("config.load_dotenv", lambda: None)
    with pytest.raises(RuntimeError, match="faltando"):
        Settings.from_env()
