"""Pecas de autenticacao: cliente MSAL, validacao do ID token e protecao de rotas."""
import functools

import jwt
import msal
from flask import redirect, request, session, url_for

from config import Settings


def build_msal_app(settings: Settings) -> msal.ConfidentialClientApplication:
    """Cliente confidencial (backend guarda o client secret).

    A criacao consulta o endereco de descoberta do tenant na internet.
    """
    return msal.ConfidentialClientApplication(
        settings.client_id,
        authority=settings.authority,
        client_credential=settings.client_secret,
    )


def build_jwks_client(settings: Settings) -> jwt.PyJWKClient:
    """Baixa (e guarda em cache) as chaves publicas com que a Microsoft assina os tokens."""
    return jwt.PyJWKClient(settings.jwks_uri, cache_keys=True)


def validate_id_token(settings: Settings, jwks_client, id_token: str) -> dict:
    """Valida o ID token e devolve suas claims.

    O MSAL Python (a partir da 1.38) NAO valida o ID token. Ele so confere
    state, PKCE e nonce. Quem valida assinatura, emissor, publico e validade
    e a aplicacao, e e isso que esta funcao faz.

    Levanta jwt.PyJWTError se qualquer verificacao falhar.
    """
    signing_key = jwks_client.get_signing_key_from_jwt(id_token)
    claims = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256"],                 # nunca aceite "none" nem HS256 aqui
        audience=settings.client_id,          # o token foi emitido para ESTE app?
        issuer=settings.issuer,               # foi emitido pelo SEU tenant?
        options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        leeway=120,                           # tolerancia de relogio (segundos)
    )
    # Defesa extra: o tenant de origem precisa ser o esperado.
    if claims.get("tid") != settings.tenant_id:
        raise jwt.InvalidIssuerError("tid do token diferente do tenant configurado")
    return claims


def is_safe_next(target: str | None) -> bool:
    """So aceita caminhos locais (evita open redirect)."""
    return bool(target) and target.startswith("/") and not target.startswith("//")


def login_required(view):
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)

    return wrapper
