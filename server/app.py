import hmac
from typing import Optional

import requests
import yaml
from flask import Flask, Response, abort

from cache import TtlCache
from fetcher import SubconverterClient
from repository import Source, load_profiles, load_sources
from settings import Settings
from transformer import transform_profile
from validator import ValidationError


def create_app(
    settings: Settings, client: Optional[SubconverterClient] = None
) -> Flask:
    app = Flask(__name__)
    sources = load_sources(settings.sources_file)
    profiles = load_profiles(settings.profiles_file)
    if settings.legacy_profile not in profiles:
        raise ValueError(f"unknown legacy profile: {settings.legacy_profile}")

    client = client or SubconverterClient(
        endpoint=settings.subconverter_url,
        common_config_url=settings.common_config_url,
        timeout_seconds=settings.request_timeout_seconds,
    )
    cache = TtlCache(settings.cache_ttl_seconds)

    def resolve_source(source_name: str, source_token: str) -> Source:
        source = sources.get(source_name)
        if source is None or not hmac.compare_digest(source.token, source_token):
            abort(404)
        return source

    def render(source_name: str, source_token: str, profile_name: str) -> Response:
        source = resolve_source(source_name, source_token)
        profile = profiles.get(profile_name)
        if profile is None:
            abort(404)

        cache_key = (source_name, profile_name)
        body = cache.get(cache_key)
        if body is None:
            try:
                template = client.generate(source.url)
                result = transform_profile(
                    template=template,
                    profile=profile,
                    egress=settings.company_egress,
                )
                body = yaml.safe_dump(result, allow_unicode=True, sort_keys=False)
            except (requests.RequestException, ValueError, ValidationError):
                app.logger.exception(
                    "profile generation failed for source=%s profile=%s",
                    source_name,
                    profile_name,
                )
                abort(502)
            cache.put(cache_key, body)

        response = Response(body, mimetype="text/yaml; charset=utf-8")
        response.headers["Cache-Control"] = (
            f"private, max-age={settings.cache_ttl_seconds}, must-revalidate"
        )
        return response

    @app.get("/<service_token>/sub/<source>/<source_token>/clash/<profile>")
    def profile_subscription(
        service_token: str, source: str, source_token: str, profile: str
    ) -> Response:
        if not hmac.compare_digest(settings.service_token, service_token):
            abort(404)
        return render(source, source_token, profile)

    @app.get("/<service_token>/sub/<source>/<source_token>/clash")
    def legacy_subscription(
        service_token: str, source: str, source_token: str
    ) -> Response:
        if not hmac.compare_digest(settings.service_token, service_token):
            abort(404)
        return render(source, source_token, settings.legacy_profile)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True, "profiles": sorted(profiles)}

    return app
