"""Configuracao lida de variaveis de ambiente (ou do arquivo .env)."""
import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from dotenv import load_dotenv

_GUID = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_REQUIRED = ("TENANT_ID", "CLIENT_ID", "CLIENT_SECRET", "SECRET_KEY")


@dataclass(frozen=True)
class Settings:
    tenant_id: str
    client_id: str
    client_secret: str
    secret_key: str
    redirect_uri: str = "http://localhost:5000/auth/callback"
    post_logout_redirect_uri: str = "http://localhost:5000/"

    def __post_init__(self):
        # O issuer do ID token e https://login.microsoftonline.com/<GUID>/v2.0.
        # Por isso exigimos o GUID do tenant (e nao o dominio, nem "common").
        if not _GUID.match(self.tenant_id):
            raise RuntimeError(
                "TENANT_ID deve ser o Directory (tenant) ID no formato GUID. "
                "Nao use dominio, 'common' nem 'organizations'."
            )

    @property
    def authority(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}"

    @property
    def issuer(self) -> str:
        return f"{self.authority}/v2.0"

    @property
    def jwks_uri(self) -> str:
        return f"{self.authority}/discovery/v2.0/keys"

    @property
    def logout_url(self) -> str:
        from urllib.parse import quote

        return (
            f"{self.authority}/oauth2/v2.0/logout"
            f"?post_logout_redirect_uri={quote(self.post_logout_redirect_uri, safe='')}"
        )

    @property
    def callback_path(self) -> str:
        return urlparse(self.redirect_uri).path

    @property
    def cookie_secure(self) -> bool:
        # Em producao o cookie so deve trafegar por HTTPS.
        return urlparse(self.redirect_uri).scheme == "https"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        missing = [name for name in _REQUIRED if not os.getenv(name)]
        if missing:
            raise RuntimeError(
                "Variaveis de ambiente faltando: " + ", ".join(missing)
                + ". Copie .env.example para .env e preencha."
            )
        kwargs = {
            "tenant_id": os.environ["TENANT_ID"],
            "client_id": os.environ["CLIENT_ID"],
            "client_secret": os.environ["CLIENT_SECRET"],
            "secret_key": os.environ["SECRET_KEY"],
        }
        if os.getenv("REDIRECT_URI"):
            kwargs["redirect_uri"] = os.environ["REDIRECT_URI"]
        if os.getenv("POST_LOGOUT_REDIRECT_URI"):
            kwargs["post_logout_redirect_uri"] = os.environ["POST_LOGOUT_REDIRECT_URI"]
        return cls(**kwargs)
