import ipaddress
from typing import Dict, Iterable, List, Optional, Set

from profiles import EgressConfig, Profile


PUBLIC_GROUP = "🎯 常规公网"
SKIP_PROXY_TYPES = {"direct", "reject", "reject-drop", "pass", "compatible"}
BUILTIN_TARGETS = {"DIRECT", "REJECT", "REJECT-DROP", "PASS", "COMPATIBLE"}
COMPANY_FORBIDDEN_TERMINALS = {"DIRECT", "PASS", "COMPATIBLE"}

LOCAL_EXACT_DOMAINS = {
    "localhost",
    "router.asus.com",
    "www.asusrouter.com",
    "routerlogin.com",
    "www.routerlogin.com",
    "tplogin.cn",
    "miwifi.com",
    "www.miwifi.com",
}
LOCAL_DOMAIN_SUFFIXES = {"lan", "local", "localdomain", "home.arpa"}
LOCAL_NETWORKS = tuple(
    ipaddress.ip_network(network)
    for network in (
        "10.0.0.0/8",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "224.0.0.0/4",
        "255.255.255.255/32",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
        "ff00::/8",
    )
)


class ValidationError(ValueError):
    pass


def _names(items: Iterable[dict], kind: str) -> List[str]:
    names = []
    for item in items:
        if not isinstance(item, dict):
            raise ValidationError(f"{kind} entry must be a mapping")
        name = item.get("name")
        if not isinstance(name, str) or not name:
            raise ValidationError(f"{kind} entry is missing a name")
        names.append(name)
    if len(names) != len(set(names)):
        raise ValidationError(f"duplicate {kind} names are not allowed")
    return names


def _rule_target(rule: str) -> Optional[str]:
    parts = rule.split(",")
    if len(parts) < 2:
        return None
    if parts[0] in {"MATCH", "FINAL"}:
        return parts[1]
    if len(parts) < 3:
        return None
    return parts[2]


def _domain_is_local(value: str) -> bool:
    value = value.lower().rstrip(".")
    if value in LOCAL_EXACT_DOMAINS:
        return True
    return any(value == suffix or value.endswith(f".{suffix}") for suffix in LOCAL_DOMAIN_SUFFIXES)


def _network_is_local(value: str) -> bool:
    try:
        candidate = ipaddress.ip_network(value, strict=False)
    except ValueError:
        return False
    return any(
        candidate.version == allowed.version and candidate.subnet_of(allowed)
        for allowed in LOCAL_NETWORKS
    )


def is_local_direct_rule(rule: str) -> bool:
    parts = rule.split(",")
    if len(parts) < 3 or _rule_target(rule) != "DIRECT":
        return False
    rule_type, value = parts[0], parts[1]
    if rule_type in {"DOMAIN", "DOMAIN-SUFFIX"}:
        return _domain_is_local(value)
    if rule_type in {"IP-CIDR", "IP-CIDR6"}:
        return _network_is_local(value)
    return rule_type == "GEOIP" and value.upper() == "LAN"


def _validate_group_graph(groups: List[dict], proxy_names: Set[str]) -> Dict[str, dict]:
    group_names = _names(groups, "proxy group")
    group_map = {group["name"]: group for group in groups}
    known_targets = proxy_names | set(group_names) | BUILTIN_TARGETS

    for group in groups:
        members = group.get("proxies")
        if not isinstance(members, list) or not members:
            raise ValidationError(f"proxy group {group['name']!r} has no members")
        unknown = [member for member in members if member not in known_targets]
        if unknown:
            raise ValidationError(
                f"proxy group {group['name']!r} references unknown members: {unknown}"
            )

    visiting: Set[str] = set()
    visited: Set[str] = set()

    def visit(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            raise ValidationError(f"proxy group cycle detected at {name!r}")
        visiting.add(name)
        for member in group_map[name]["proxies"]:
            if member in group_map:
                visit(member)
        visiting.remove(name)
        visited.add(name)

    for name in group_names:
        visit(name)
    return group_map


def _validate_rules(rules: List[str], known_targets: Set[str]) -> None:
    for rule in rules:
        if not isinstance(rule, str):
            raise ValidationError("rule entries must be strings")
        target = _rule_target(rule)
        if target is None:
            raise ValidationError(f"cannot determine rule target: {rule!r}")
        if target not in known_targets:
            raise ValidationError(f"rule references unknown target {target!r}: {rule!r}")


def _validate_company(
    proxies: List[dict],
    groups: List[dict],
    rules: List[str],
    group_map: Dict[str, dict],
    egress: EgressConfig,
) -> None:
    proxy_map = {proxy["name"]: proxy for proxy in proxies}
    egress_proxy = proxy_map.get(egress.name)
    if egress_proxy is None:
        raise ValidationError("company profile is missing its SOCKS5 egress")
    if egress_proxy.get("dialer-proxy"):
        raise ValidationError("company SOCKS5 egress must not have a dialer-proxy")
    if str(egress_proxy.get("type", "")).lower() != "socks5":
        raise ValidationError("company egress must use the socks5 proxy type")
    if not isinstance(egress_proxy.get("port"), int) or not 1 <= egress_proxy["port"] <= 65535:
        raise ValidationError("company SOCKS5 port is invalid")

    try:
        egress_address = ipaddress.ip_address(egress.server)
    except ValueError as error:
        raise ValidationError("company SOCKS5 server must be a literal LAN IP") from error
    if not (egress_address.is_private or egress_address.is_loopback or egress_address.is_link_local):
        raise ValidationError("company SOCKS5 server must be inside a local network")

    for proxy in proxies:
        if proxy["name"] == egress.name:
            continue
        if str(proxy.get("type", "")).lower() in SKIP_PROXY_TYPES:
            continue
        if proxy.get("dialer-proxy") != egress.name:
            raise ValidationError(
                f"company upstream {proxy['name']!r} does not use the SOCKS5 egress"
            )

    for group in groups:
        forbidden = COMPANY_FORBIDDEN_TERMINALS.intersection(group["proxies"])
        if forbidden:
            raise ValidationError(
                f"company group {group['name']!r} can bypass SOCKS5 via {sorted(forbidden)}"
            )

    public_group = group_map.get(PUBLIC_GROUP)
    if public_group is None or public_group.get("proxies") != [egress.name]:
        raise ValidationError("company public group must contain only the SOCKS5 egress")

    for rule in rules:
        target = _rule_target(rule)
        if target in COMPANY_FORBIDDEN_TERMINALS - {"DIRECT"}:
            raise ValidationError(
                f"company profile contains a bypass rule targeting {target}: {rule!r}"
            )
        if target == "DIRECT" and not is_local_direct_rule(rule):
            raise ValidationError(f"company profile contains a public DIRECT rule: {rule!r}")


def _validate_home(
    proxies: List[dict], group_map: Dict[str, dict], egress: EgressConfig
) -> None:
    if any(proxy["name"] == egress.name for proxy in proxies):
        raise ValidationError("home profile must not contain the company SOCKS5 egress")
    chained = [proxy["name"] for proxy in proxies if proxy.get("dialer-proxy")]
    if chained:
        raise ValidationError(f"home profile contains chained upstreams: {chained}")
    public_group = group_map.get(PUBLIC_GROUP)
    if public_group is None or public_group.get("proxies") != ["DIRECT"]:
        raise ValidationError("home public group must contain only DIRECT")


def validate_profile(config: dict, profile: Profile, egress: EgressConfig) -> None:
    proxies = config.get("proxies")
    groups = config.get("proxy-groups")
    rules = config.get("rules")
    if not isinstance(proxies, list):
        raise ValidationError("profile is missing the proxies list")
    if not isinstance(groups, list):
        raise ValidationError("profile is missing the proxy-groups list")
    if not isinstance(rules, list):
        raise ValidationError("profile is missing the rules list")

    proxy_names = set(_names(proxies, "proxy"))
    group_map = _validate_group_graph(groups, proxy_names)
    _validate_rules(rules, proxy_names | set(group_map) | BUILTIN_TARGETS)

    if profile.force_public_egress:
        _validate_company(proxies, groups, rules, group_map, egress)
    else:
        _validate_home(proxies, group_map, egress)
