"""Aplicacao Flask de exemplo: login com conta Microsoft (Entra ID) via OpenID Connect."""
from datetime import timedelta

import jwt
from flask import Flask, abort, redirect, render_template, request, session, url_for

from auth import (
    build_jwks_client,
    build_msal_app,
    is_safe_next,
    login_required,
    validate_id_token,
)
from config import Settings


def create_app(settings: Settings | None = None, msal_app=None, jwks_client=None) -> Flask:
    """Fabrica da app. Os parametros opcionais existem para os testes injetarem dubles."""
    settings = settings or Settings.from_env()
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=settings.secret_key,
        SESSION_COOKIE_HTTPONLY=True,      # JavaScript nao le o cookie
        SESSION_COOKIE_SAMESITE="Lax",     # Lax permite a volta do login (GET de topo)
        SESSION_COOKIE_SECURE=settings.cookie_secure,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    )

    # Criados sob demanda: o MSAL faz uma chamada de rede ao ser instanciado.
    state = {"msal": msal_app, "jwks": jwks_client}

    def get_msal():
        if state["msal"] is None:
            state["msal"] = build_msal_app(settings)
        return state["msal"]

    def get_jwks():
        if state["jwks"] is None:
            state["jwks"] = build_jwks_client(settings)
        return state["jwks"]

    @app.get("/")
    def index():
        return render_template("index.html", user=session.get("user"))

    # PASSO 1: o usuario clica em "Entrar". Montamos o pedido de login e
    # mandamos o navegador para a Microsoft.
    @app.get("/login")
    def login():
        flow = get_msal().initiate_auth_code_flow(
            scopes=[],  # so identidade (openid, profile). Sem acesso a APIs.
            redirect_uri=settings.redirect_uri,
        )
        # O "flow" guarda state, nonce e o code_verifier (PKCE). Fica na sessao
        # ate a Microsoft devolver o usuario.
        session["flow"] = flow
        next_url = request.args.get("next")
        session["next"] = next_url if is_safe_next(next_url) else None
        return redirect(flow["auth_uri"])

    # PASSO 2: a Microsoft autentica o usuario (senha, MFA, acesso condicional)
    # e o devolve aqui com ?code=...&state=...
    @app.get(settings.callback_path, endpoint="auth_callback")
    def auth_callback():
        flow = session.pop("flow", None)
        if not flow:
            abort(400, "Sessao de login nao encontrada. Comece de novo em /login.")

        # PASSO 3: troca o code por tokens. O MSAL confere state (anti-CSRF),
        # envia o code_verifier (PKCE) e confere o nonce.
        try:
            result = get_msal().acquire_token_by_auth_code_flow(flow, request.args.to_dict())
        except ValueError:
            abort(400, "Resposta de login invalida (state nao confere).")

        if "error" in result:
            return render_template(
                "error.html",
                title="Login recusado",
                message=f"{result.get('error')}: {result.get('error_description', '')}",
            ), 401

        # PASSO 4: validar o ID token (assinatura, emissor, publico, validade, tenant).
        try:
            claims = validate_id_token(settings, get_jwks(), result["id_token"])
        except (jwt.PyJWTError, KeyError):
            return render_template(
                "error.html", title="Token invalido", message="Nao foi possivel validar o ID token."
            ), 401

        # PASSO 5: abrir a sessao da nossa aplicacao. Guardamos so o necessario
        # (nenhum token fica no cookie).
        next_url = session.pop("next", None)
        session.clear()  # evita fixacao de sessao
        session["user"] = {
            "name": claims.get("name"),
            "username": claims.get("preferred_username"),
            "oid": claims.get("oid"),
            "tid": claims.get("tid"),
        }
        session.permanent = True
        return redirect(next_url or url_for("profile"))

    @app.get("/profile")
    @login_required
    def profile():
        return render_template("profile.html", user=session["user"])

    # Logout: limpa a sessao local E encerra a sessao na Microsoft.
    @app.get("/logout")
    def logout():
        session.clear()
        return redirect(settings.logout_url)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.errorhandler(400)
    def bad_request(err):
        return render_template("error.html", title="Pedido invalido", message=err.description), 400

    return app


if __name__ == "__main__":
    # Servidor de desenvolvimento. Em producao use um servidor WSGI (ex.: gunicorn) atras de HTTPS.
    create_app().run(host="127.0.0.1", port=5000, debug=False)
