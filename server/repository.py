from dataclasses import dataclass
from typing import Dict

import yaml

from profiles import Profile


@dataclass(frozen=True)
class Source:
    token: str
    url: str


def _load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ValueError(f"invalid YAML mapping: {path}")
    return data


def load_sources(path: str) -> Dict[str, Source]:
    raw_sources = _load_yaml(path).get("sources")
    if not isinstance(raw_sources, dict):
        raise ValueError("sources file is missing the sources mapping")

    sources = {}
    for name, raw in raw_sources.items():
        if not isinstance(raw, dict):
            raise ValueError(f"invalid source definition: {name}")
        token = raw.get("token")
        url = raw.get("url")
        if not isinstance(token, str) or not token:
            raise ValueError(f"source {name!r} is missing a token")
        if not isinstance(url, str) or not url:
            raise ValueError(f"source {name!r} is missing a URL")
        sources[name] = Source(token=token, url=url)
    return sources


def load_profiles(path: str) -> Dict[str, Profile]:
    raw_profiles = _load_yaml(path).get("profiles")
    if not isinstance(raw_profiles, dict):
        raise ValueError("profiles file is missing the profiles mapping")

    profiles = {}
    for name, raw in raw_profiles.items():
        if not isinstance(raw, dict):
            raise ValueError(f"invalid profile definition: {name}")
        force_public_egress = raw.get("force_public_egress")
        chain_upstreams = raw.get("chain_upstreams")
        if not isinstance(force_public_egress, bool):
            raise ValueError(
                f"profile {name!r} must define force_public_egress as a boolean"
            )
        if not isinstance(chain_upstreams, bool):
            raise ValueError(
                f"profile {name!r} must define chain_upstreams as a boolean"
            )
        profile = Profile(
            name=name,
            force_public_egress=force_public_egress,
            chain_upstreams=chain_upstreams,
        )
        profile.validate()
        profiles[name] = profile
    return profiles
