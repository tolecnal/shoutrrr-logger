from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/shoutrrr_logger"

    # OpenID Connect
    oidc_discovery_url: str = "http://localhost:8080/realms/master/.well-known/openid-configuration"
    oidc_client_id: str = "shoutrrr-logger"
    oidc_client_secret: str = ""

    # Application
    secret_key: str = "change-me-in-production"
    app_base_url: str = "http://localhost:4000"
    workers: int = 4

    # Space-separated scopes to request at login. "roles" is required for
    # Keycloak to include role claims in the UserInfo response.
    oidc_scopes: str = "openid email profile roles"

    # Role mapping from OIDC claims.
    #
    # OIDC_ROLES_CLAIM is a dot-separated path into the userinfo / ID token JSON
    # that resolves to a list of role strings.  The application looks for the
    # values of OIDC_ROLE_VIEWER and OIDC_ROLE_ADMIN inside that list.
    #
    # Keycloak default:  realm_access.roles
    # Auth0 / custom:    set to whatever claim your provider populates
    oidc_roles_claim: str = "realm_access.roles"
    oidc_role_viewer: str = "viewer"
    oidc_role_admin: str = "admin"


settings = Settings()
