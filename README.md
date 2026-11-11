# Exemplo: SSO com Microsoft Entra ID em Python (OpenID Connect)

Aplicação mínima em **Flask** que **não tem tela de usuário e senha**: o acesso é feito pela **conta Microsoft da empresa**, validada pelo **Microsoft Entra ID** (antes Azure AD) com **OpenID Connect sobre OAuth 2.0** (Authorization Code Flow com PKCE).

É um material didático da [Gaspari Tecnologia](https://gasparitecnologia.com.br). O código é pequeno de propósito (cerca de 270 linhas de Python, incluindo configuração e comentários) para que cada etapa do login possa ser lida e entendida.

> **Escopo.** O exemplo mostra o padrão de integração (registro do app, fluxo, validação do token, sessão, logout). Ele não substitui a documentação do produto onde a sua aplicação roda. Se ela for Oracle APEX, OCI IAM ou E-Business Suite, veja [a seção Oracle](#e-se-a-aplicação-for-oracle) e use este código como referência do que acontece por baixo.

## Como o login funciona (resumo)

```
Navegador          Sua aplicação (Flask)             Microsoft Entra ID
    | GET /login ------->|                                   |
    |                    | gera state + nonce + PKCE         |
    |<-- 302 para /authorize ------------------------------->|
    |                                  usuário entra (senha, MFA, acesso condicional)
    |<-- 302 /auth/callback?code=...&state=... --------------|
    | GET /auth/callback>|                                   |
    |                    | troca code por tokens (+ PKCE) -->|
    |                    |<-- id_token --------------------- |
    |                    | valida o id_token                 |
    |<-- cookie de sessão + 302 /profile                     |
```

Diagrama detalhado e o que cada parâmetro faz: [docs/fluxo.md](docs/fluxo.md).

## Estrutura

| Arquivo | Para que serve |
|---|---|
| `app.py` | Rotas: `/login`, `/auth/callback`, `/profile`, `/logout`. Os comentários `PASSO 1..5` seguem o fluxo. |
| `auth.py` | Cliente MSAL, **validação do ID token** e decorador `login_required`. |
| `config.py` | Leitura e validação das variáveis de ambiente. |
| `templates/` | Páginas HTML mínimas. |
| `tests/` | 20 testes automatizados, sem rede. |
| `.env.example` | Modelo das variáveis (copie para `.env`). |

## Passo a passo

### 0. Pré-requisitos

- Python 3.12 (testado nesta versão).
- Acesso de administrador no Entra ID do tenant, ou alguém com o papel de *Application Developer* (ou superior) para registrar o app.

### 1. Registrar a aplicação no Entra ID

No [Microsoft Entra admin center](https://entra.microsoft.com):

1. **Entra ID > App registrations > New registration**.
2. **Name:** por exemplo `exemplo-sso-python`.
3. **Supported account types:** `Accounts in this organizational directory only` (*single tenant*). É a opção para sistema usado só por quem é do tenant da empresa.
4. **Redirect URI:** plataforma **Web**, valor `http://localhost:5000/auth/callback`.
5. **Register**.
6. Na tela **Overview**, copie o **Application (client) ID** e o **Directory (tenant) ID**.

Guia oficial: [Register an app in Microsoft Entra ID](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app).

### 2. Cadastrar o endereço de retorno do logout

Em **Authentication > Add Redirect URI** (plataforma Web), adicione também `http://localhost:5000/`.

A documentação da Microsoft informa que o `post_logout_redirect_uri` precisa coincidir com um dos Redirect URIs registrados. Sem isso, o logout mostra uma tela genérica da Microsoft em vez de voltar para a aplicação.

> Não marque *Implicit grant and hybrid flows*. Este exemplo usa o fluxo de código de autorização, que não precisa disso.

### 3. Criar o client secret

**Certificates & secrets > New client secret.** Copie o **Value** (não o *Secret ID*). Ele só aparece uma vez e tem validade, então anote a data de expiração.

> Em produção a Microsoft cita certificado como credencial de maior segurança que o secret.

### 4. Permissões

O exemplo pede apenas `openid` e `profile` (identidade). A permissão `User.Read` que vem por padrão no registro é suficiente. Não é preciso adicionar mais nada.

### 5. Controlar quem pode entrar

O registro *single tenant* já limita a usuários do seu tenant. Para limitar a pessoas ou grupos específicos:

1. **Entra ID > Enterprise apps >** selecione o app.
2. **Properties >** *Assignment required?* = **Yes**.
3. **Users and groups >** adicione quem pode acessar.

Referência: [Restrict a Microsoft Entra app to a set of users](https://learn.microsoft.com/en-us/entra/identity-platform/howto-restrict-your-app-to-a-set-of-users). Confirme nessa página que o caso de OIDC está coberto para o seu tipo de app.

### 6. Configurar o ambiente

```bash
git clone https://github.com/Gaspari-Tecnologia-Dev/exemplo-sso-microsoft-entra-python.git
cd exemplo-sso-microsoft-entra-python

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env
```

Edite o `.env`:

| Variável | De onde vem |
|---|---|
| `TENANT_ID` | Directory (tenant) ID, **em formato GUID** (a validação do emissor do token exige isso) |
| `CLIENT_ID` | Application (client) ID |
| `CLIENT_SECRET` | *Value* do secret do passo 3 |
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `REDIRECT_URI` | `http://localhost:5000/auth/callback` (idêntico ao do passo 1) |
| `POST_LOGOUT_REDIRECT_URI` | `http://localhost:5000/` (idêntico ao do passo 2) |

O arquivo `.env` está no `.gitignore`. **Nunca** suba o secret para o Git.

### 7. Rodar

```bash
python app.py
```

Abra `http://localhost:5000` (use `localhost`, como cadastrado no Entra).

### 8. Testar o login

1. Clique em **Entrar com Microsoft**.
2. Entre com uma conta do tenant. Se houver MFA ou acesso condicional, ele roda aqui, na Microsoft, sem nenhum código extra seu.
3. Na primeira vez a Microsoft pode mostrar a tela de consentimento (*Sign you in* / *View your basic profile*).
4. Você volta para `/profile`, página protegida, com nome, usuário, `oid` e `tid` vindos do ID token validado.
5. **Sair** limpa a sessão da aplicação e encerra a sessão na Microsoft.

Para ver a proteção funcionando: abra `http://localhost:5000/profile` sem estar logado. Você é mandado para `/login`.

### 9. Rodar os testes

```bash
pytest -q
```

Os testes não usam rede nem tenant real. O MSAL e o servidor de chaves da Microsoft são substituídos por dublês, mas o **ID token é assinado de verdade** (RSA + PyJWT), então a validação real é exercitada. Casos cobertos:

- login feliz abre a sessão; `/profile` sem login redireciona;
- `state` divergente (CSRF), `code` sem sessão, erro devolvido pela Microsoft;
- token com **público errado**, **emissor errado**, **tenant errado**, **expirado**, **assinatura de outra chave**, ou **sem id_token**;
- `next=//site-externo` não vira redirecionamento aberto;
- nenhum token fica no cookie de sessão;
- `TENANT_ID` diferente de GUID é recusado.

### Status de verificação

- 20 testes automatizados passando (Python 3.12, Flask 3.1, MSAL 1.39, PyJWT 2.15).
- O `/login` foi exercitado com o **MSAL real** contra o endereço de descoberta de um tenant real: gera a URL de autorização correta, com PKCE (`S256`), `state`, `nonce` e escopos `openid profile offline_access`.
- **O login ponta a ponta com um tenant seu não foi executado por quem escreveu este repositório**, porque exige um registro de app e uma conta. Os passos 1 a 8 acima são o roteiro para fazer essa verificação no seu ambiente.

## O que cada etapa faz no código

| Etapa | Onde | O que acontece |
|---|---|---|
| 1. Pedir login | `app.py: login()` | `initiate_auth_code_flow` cria `state` (anti-CSRF), `nonce` (anti-replay) e o par PKCE. Guarda na sessão e redireciona para a Microsoft. |
| 2. Usuário se autentica | Microsoft | Senha, MFA, acesso condicional. Sua aplicação nunca vê a senha. |
| 3. Trocar o código | `app.py: auth_callback()` | `acquire_token_by_auth_code_flow` confere `state`, envia o `code_verifier` e confere o `nonce`. |
| 4. Validar o ID token | `auth.py: validate_id_token()` | Assinatura RS256 (chaves públicas da Microsoft), `iss`, `aud`, `exp`, `tid`. |
| 5. Abrir sessão | `app.py: auth_callback()` | Guarda só `name`, `username`, `oid`, `tid` no cookie assinado. Nenhum token é guardado. |
| 6. Proteger rotas | `auth.py: login_required` | Sem sessão, redireciona para `/login`. |
| 7. Sair | `app.py: logout()` | Limpa a sessão local e redireciona para o `end_session_endpoint` da Microsoft. |

### Ponto importante: quem valida o ID token

O MSAL Python, a partir da versão 1.38, **não valida** mais o ID token (a própria biblioteca documenta isso). Ele cuida de `state`, PKCE e `nonce`. Assinatura, emissor, público e validade ficam por conta da aplicação, e é isso que `validate_id_token()` faz. Se você adaptar este exemplo, mantenha essa função.

## Pontos de atenção para produção

- **HTTPS obrigatório.** Troque os Redirect URIs por `https://...`. Com `REDIRECT_URI` em `https`, o cookie de sessão passa a sair com `Secure`.
- **Servidor WSGI.** `python app.py` é só para desenvolvimento. Use gunicorn ou similar atrás de HTTPS.
- **Cookie de sessão.** O cookie é assinado, mas não é criptografado, e o `SECRET_KEY` deve ser longo, aleatório e guardado em cofre de segredos. Para sessões revogáveis do lado do servidor, use sessão em Redis ou banco.
- **Client secret.** Tem validade. Planeje a rotação ou use certificado.
- **`response_mode`.** O MSAL emite um aviso recomendando `form_post`. Ele foi mantido em `query` porque, com `form_post`, o retorno vira um POST entre sites e o cookie `SameSite=Lax` não acompanha. Isso exigiria `SameSite=None; Secure` e HTTPS. É uma troca consciente deste exemplo simples.
- **Autorização.** Este exemplo cuida de **autenticação** (quem é a pessoa). Permissões dentro do sistema (papéis, grupos) são outro assunto. Veja *App roles* e a claim `groups` na documentação do Entra.
- **Mais de um tenant (SaaS).** O exemplo é single tenant de propósito. Multitenant exige tratar o `iss` por tenant e fluxo de consentimento do administrador.
- **MFA e acesso condicional** são configurados no tenant, não no código.

## E se a aplicação for Oracle

O "como" muda conforme o produto. O princípio é o mesmo (a aplicação deixa a Microsoft autenticar e confia no token ou na asserção que volta).

| Aplicação | Caminho documentado |
|---|---|
| **Oracle APEX** | Esquema de autenticação *Social Sign-In* (OIDC) apontando para `https://login.microsoftonline.com/<tenant-id>/v2.0/.well-known/openid-configuration`. Oracle: [Social Sign-In](https://docs.oracle.com/en/database/oracle/apex/26.2/htmdb/social-sign-in.html). Callback: `https://<host>/ords/apex_authentication.callback`. |
| **OCI IAM (Identity Domain)** | Federação SAML com o Entra. Oracle: [SSO entre OCI e Microsoft Entra ID](https://docs.oracle.com/en-us/iaas/Content/Identity/tutorials/azure_ad/sso_azure/azure_sso.htm). |
| **E-Business Suite, PeopleSoft, JD Edwards** | Precisam de componente intermediário. Microsoft: [Oracle IDCS para EBS](https://learn.microsoft.com/en-us/entra/identity/saas-apps/oracle-idcs-for-ebs-tutorial), [Oracle Access Manager para EBS](https://learn.microsoft.com/en-us/entra/identity/saas-apps/oracle-access-manager-for-oracle-ebs-tutorial). |
| **Aplicação própria (Java, .NET, Python...) em OCI** | O padrão deste repositório, com a biblioteca MSAL da sua linguagem. |

Mais detalhes em [docs/oracle.md](docs/oracle.md).

## Referências oficiais

- [OpenID Connect na plataforma Microsoft](https://learn.microsoft.com/en-us/entra/identity-platform/v2-protocols-oidc)
- [Fluxo de código de autorização OAuth 2.0](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow)
- [Registrar um app](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app)
- [Tipos de conta suportados (single tenant e multitenant)](https://learn.microsoft.com/en-us/security/zero-trust/develop/identity-supported-account-types)
- [SAML vs OpenID Connect](https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/saml-vs-oidc-decision-guide)
- [MSAL para Python](https://learn.microsoft.com/en-us/entra/msal/python/)

## Licença

[MIT](LICENSE).
