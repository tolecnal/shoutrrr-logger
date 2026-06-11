from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/shoutrrr_logger"

    # SQLAlchemy async engine connection pool, *per worker process*. With
    # gunicorn's `-w WORKERS`, each worker gets its own pool, so the total
    # connections this app can open is roughly:
    #   WORKERS * (db_pool_size + db_max_overflow)
    # Keep that comfortably under PostgreSQL's `max_connections` (default 100).
    db_pool_size: int = 5
    db_max_overflow: int = 5

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

    environment: str = "production"

    # Disables outbound SSRF validation (utils.ssrf.validate_url_for_ssrf).
    # Must NEVER be set in production - intended only for test suites that
    # exercise plugin dispatch against local/loopback addresses. Distinct
    # from `environment` so that leaving ENVIRONMENT=test set in a real
    # deployment does not also disable SSRF protection.
    ssrf_validation_disabled: bool = False

    @model_validator(mode="after")
    def validate_secrets(self) -> "Settings":
        if self.environment.lower() == "production":
            if self.secret_key == "change-me-in-production":
                raise ValueError("SECRET_KEY must be changed from the default in production")
            if not self.oidc_client_secret:
                raise ValueError("OIDC_CLIENT_SECRET must be set in production")
        return self


settings = Settings()
