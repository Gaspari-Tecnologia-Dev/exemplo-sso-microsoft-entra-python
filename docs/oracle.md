# Oracle: o que muda em relação ao exemplo em Python

O exemplo deste repositório mostra o padrão. Em produtos Oracle, o "cliente OIDC" ou "provedor de serviço SAML" já vem pronto no produto, e o trabalho passa a ser **configurar** em vez de **programar**.

As informações abaixo vêm da documentação oficial indicada em cada item. Menus e nomes de tela mudam entre versões, então confira na documentação da sua versão.

## Oracle APEX (OIDC)

- O APEX tem o esquema de autenticação **Social Sign-In**, que aceita provedor OpenID Connect por **Discovery URL**.
- Discovery URL do Entra: `https://login.microsoftonline.com/<tenant-id>/v2.0/.well-known/openid-configuration`.
- Redirect URI a cadastrar no Entra: `https://<host>/ords/apex_authentication.callback` (ou `.callback2`, conforme a documentação da Oracle).
- Client ID e Client Secret entram numa **Web Credential** do APEX.
- Mapeamento deste exemplo para o APEX:

| Neste exemplo | No APEX |
|---|---|
| `CLIENT_ID`, `CLIENT_SECRET` | Web Credential (Credential Store) |
| `TENANT_ID` | Dentro da Discovery URL |
| `scope=openid profile` | Campo *Scope* (o APEX adiciona `openid` sozinho) |
| `preferred_username` | Campo *Username* do esquema (por exemplo `#preferred_username#`) |
| `validate_id_token()` | Feito pelo APEX |

Fonte: [Oracle APEX, Social Sign-In](https://docs.oracle.com/en/database/oracle/apex/26.2/htmdb/social-sign-in.html).

## OCI IAM Identity Domain (SAML)

- Federação em que o **Entra é o IdP** e o **OCI IAM é o SP**.
- O usuário precisa existir nos dois lados, ou usar provisionamento JIT.
- Fontes: [SSO entre OCI e Microsoft Entra ID](https://docs.oracle.com/en-us/iaas/Content/Identity/tutorials/azure_ad/sso_azure/azure_sso.htm) e [Provisionamento JIT](https://docs.oracle.com/en-us/iaas/Content/Identity/tutorials/azure_ad/jit_azure/azure_jit.htm).

## E-Business Suite, PeopleSoft, JD Edwards

- Não falam OIDC nativamente. Usa-se componente intermediário (Oracle IDCS, Oracle Access Manager, gateway de terceiros).
- Fontes (Microsoft Learn): [Oracle IDCS para EBS](https://learn.microsoft.com/en-us/entra/identity/saas-apps/oracle-idcs-for-ebs-tutorial), [Oracle Access Manager para EBS](https://learn.microsoft.com/en-us/entra/identity/saas-apps/oracle-access-manager-for-oracle-ebs-tutorial), [Datawiza](https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/datawiza-sso-mfa-oracle-ebs), [F5 BIG-IP](https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/f5-big-ip-oracle-enterprise-business-suite-easy-button).

## Como escolher entre OIDC e SAML

Guia da Microsoft: [SAML vs OpenID Connect](https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/saml-vs-oidc-decision-guide). Em geral, a escolha é ditada pelo que o produto Oracle suporta.
