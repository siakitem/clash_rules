import copy
from typing import Iterable, List

from profiles import EgressConfig, Profile
from validator import PUBLIC_GROUP, SKIP_PROXY_TYPES, ValidationError, validate_profile


def _unique(items: Iterable[str]) -> List[str]:
    result = []
    seen = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _base_sections(template: dict) -> tuple:
    proxies = template.get("proxies")
    groups = template.get("proxy-groups")
    rules = template.get("rules")
    if not isinstance(proxies, list):
        raise ValidationError("subconverter template is missing proxies")
    if not isinstance(groups, list):
        raise ValidationError("subconverter template is missing proxy-groups")
    if not isinstance(rules, list):
        raise ValidationError("subconverter template is missing rules")
    return copy.deepcopy(proxies), copy.deepcopy(groups), copy.deepcopy(rules)


def _set_public_group(groups: List[dict], target: str) -> None:
    for group in groups:
        if group.get("name") == PUBLIC_GROUP:
            group["proxies"] = [target]
            return
    raise ValidationError(f"common template is missing {PUBLIC_GROUP!r}")


def _compile_company(
    proxies: List[dict], groups: List[dict], egress: EgressConfig
) -> List[dict]:
    if any(proxy.get("name") == egress.name for proxy in proxies):
        raise ValidationError(f"upstream source already contains {egress.name!r}")

    for proxy in proxies:
        if str(proxy.get("type", "")).lower() in SKIP_PROXY_TYPES:
            continue
        proxy["dialer-proxy"] = egress.name

    for group in groups:
        members = group.get("proxies")
        if not isinstance(members, list):
            raise ValidationError(f"proxy group {group.get('name')!r} has no members")
        group["proxies"] = _unique(
            egress.name if member == "DIRECT" else member for member in members
        )

    _set_public_group(groups, egress.name)
    return [egress.to_proxy()] + proxies


def _compile_home(proxies: List[dict], groups: List[dict]) -> List[dict]:
    _set_public_group(groups, "DIRECT")
    return proxies


def transform_profile(
    template: dict, profile: Profile, egress: EgressConfig
) -> dict:
    profile.validate()
    proxies, groups, rules = _base_sections(template)

    if profile.chain_upstreams:
        proxies = _compile_company(proxies, groups, egress)
    else:
        proxies = _compile_home(proxies, groups)

    result = {
        "proxies": proxies,
        "proxy-groups": groups,
        "rules": rules,
    }
    validate_profile(result, profile, egress)
    return result
