import os
from dataclasses import dataclass

from profiles import EgressConfig


def _flag(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"missing required environment variable: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    subconverter_url: str
    common_config_url: str
    sources_file: str
    profiles_file: str
    service_token: str
    legacy_profile: str
    listen_host: str
    listen_port: int
    request_timeout_seconds: int
    cache_ttl_seconds: int
    company_egress: EgressConfig

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            subconverter_url=os.getenv(
                "SUBCONVERTER_URL", "http://subconverter-rules:25500/sub"
            ),
            common_config_url=_required("COMMON_CONFIG_URL"),
            sources_file=os.getenv("SOURCES_FILE", "/data/sources.yaml"),
            profiles_file=os.getenv("PROFILES_FILE", "/app/profiles.yaml"),
            service_token=_required("SERVICE_TOKEN"),
            legacy_profile=os.getenv("LEGACY_PROFILE", "company"),
            listen_host=os.getenv("LISTEN_HOST", "0.0.0.0"),
            listen_port=int(os.getenv("LISTEN_PORT", "25500")),
            request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "180")),
            cache_ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", "300")),
            company_egress=EgressConfig(
                name=os.getenv("COMPANY_SOCKS_NAME", "🏢 公司 SOCKS5"),
                server=_required("COMPANY_SOCKS_SERVER"),
                port=int(_required("COMPANY_SOCKS_PORT")),
                proxy_type=os.getenv("COMPANY_SOCKS_TYPE", "socks5"),
                username=os.getenv("COMPANY_SOCKS_USERNAME", ""),
                password=os.getenv("COMPANY_SOCKS_PASSWORD", ""),
                udp=_flag(os.getenv("COMPANY_SOCKS_UDP", "1")),
            ),
        )
