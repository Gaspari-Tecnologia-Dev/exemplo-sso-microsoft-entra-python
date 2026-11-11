# Fluxo detalhado: Authorization Code com PKCE e OpenID Connect

```mermaid
sequenceDiagram
    autonumber
    participant B as Navegador
    participant A as Aplicação (Flask)
    participant E as Microsoft Entra ID

    B->>A: GET /login
    A->>A: initiate_auth_code_flow (state, nonce, code_verifier)
    A-->>B: 302 para /oauth2/v2.0/authorize
    B->>E: pedido de autorização (client_id, redirect_uri, scope, state, nonce, code_challenge)
    E->>B: tela de login (senha, MFA, acesso condicional, consentimento)
    B->>E: credenciais
    E-->>B: 302 para /auth/callback?code=...&state=...
    B->>A: GET /auth/callback?code=...&state=...
    A->>A: confere state (anti-CSRF)
    A->>E: POST /oauth2/v2.0/token (code, code_verifier, client_secret)
    E-->>A: id_token (+ access_token, refresh_token)
    A->>A: valida id_token (assinatura, iss, aud, exp, tid)
    A-->>B: cookie de sessão + 302 /profile
```

## Parâmetros do pedido de autorização

| Parâmetro | Função |
|---|---|
| `client_id` | Identifica o app registrado no Entra. |
| `redirect_uri` | Para onde a Microsoft devolve o usuário. Precisa ser idêntico ao cadastrado. |
| `scope` | `openid profile offline_access`. `openid` pede o login (ID token). |
| `state` | Valor aleatório devolvido junto do código. Se não conferir, é tentativa de CSRF. |
| `nonce` | Vai dentro do ID token. Impede reaproveitar um token antigo (replay). |
| `code_challenge` | Hash (S256) do `code_verifier`. É o PKCE: quem roubar o `code` não consegue trocá-lo sem o verifier. |

## O que o ID token prova

Um JWT assinado pela Microsoft com, entre outras, estas claims:

| Claim | Significado | Como é verificada aqui |
|---|---|---|
| `iss` | Quem emitiu | Igual a `https://login.microsoftonline.com/<TENANT_ID>/v2.0` |
| `aud` | Para quem foi emitido | Igual ao `CLIENT_ID` |
| `exp`, `iat` | Validade | Obrigatórias, com tolerância de 120 s de relógio |
| `tid` | Tenant do usuário | Igual ao `TENANT_ID` |
| `nonce` | Anti-replay | Conferido pelo MSAL contra o valor guardado no `flow` |
| `oid` | ID do usuário no tenant (estável) | Guardado na sessão |
| `preferred_username` | Normalmente o UPN (e-mail corporativo) | Guardado na sessão, para exibição |

> Use `oid` (junto de `tid`) como identificador do usuário em sistemas que precisam de chave estável. O `preferred_username` pode mudar.

## O que o MSAL faz e o que não faz (versão 1.39)

| Faz | Não faz |
|---|---|
| Gera `state`, `nonce` e PKCE | Validar assinatura, `iss`, `aud` e `exp` do ID token |
| Confere `state` na volta | Decidir quem pode entrar |
| Troca o `code` por tokens | Guardar sessão da sua aplicação |
| Confere o hash do `nonce` | |

Por isso existe `validate_id_token()` em `auth.py`.
