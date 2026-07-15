import copy
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from profiles import EgressConfig, Profile  # noqa: E402
from transformer import transform_profile  # noqa: E402
from validator import PUBLIC_GROUP, ValidationError  # noqa: E402


COMPANY = Profile(
    name="company", force_public_egress=True, chain_upstreams=True
)
HOME = Profile(name="home", force_public_egress=False, chain_upstreams=False)
EGRESS = EgressConfig(
    name="🏢 公司 SOCKS5",
    server="192.168.1.10",
    port=1080,
    proxy_type="socks5",
)


def base_template() -> dict:
    return {
        "proxies": [
            {"name": "🇭🇰 node-1", "type": "vless", "server": "one.example"},
            {"name": "🇺🇸 node-2", "type": "vless", "server": "two.example"},
        ],
        "proxy-groups": [
            {"name": PUBLIC_GROUP, "type": "select", "proxies": ["DIRECT"]},
            {
                "name": "🚀 节点选择",
                "type": "select",
                "proxies": ["🇭🇰 node-1", "🇺🇸 node-2", "DIRECT"],
            },
            {
                "name": "🛑 广告拦截",
                "type": "select",
                "proxies": ["REJECT", "DIRECT"],
            },
            {
                "name": "🐟 Final兜底",
                "type": "select",
                "proxies": ["🚀 节点选择", "DIRECT"],
            },
        ],
        "rules": [
            "DOMAIN-SUFFIX,lan,DIRECT",
            "IP-CIDR,192.168.0.0/16,DIRECT,no-resolve",
            f"DOMAIN-SUFFIX,example.cn,{PUBLIC_GROUP}",
            "DOMAIN-SUFFIX,google.com,🚀 节点选择",
            "MATCH,🐟 Final兜底",
        ],
    }


class TransformerTest(unittest.TestCase):
    def test_company_forces_every_public_path_through_socks5(self) -> None:
        result = transform_profile(base_template(), COMPANY, EGRESS)

        self.assertEqual(EGRESS.name, result["proxies"][0]["name"])
        self.assertNotIn("dialer-proxy", result["proxies"][0])
        for proxy in result["proxies"][1:]:
            self.assertEqual(EGRESS.name, proxy["dialer-proxy"])

        groups = {group["name"]: group for group in result["proxy-groups"]}
        self.assertEqual([EGRESS.name], groups[PUBLIC_GROUP]["proxies"])
        for group in groups.values():
            self.assertNotIn("DIRECT", group["proxies"])

        self.assertEqual("DOMAIN-SUFFIX,lan,DIRECT", result["rules"][0])
        self.assertEqual(
            "IP-CIDR,192.168.0.0/16,DIRECT,no-resolve", result["rules"][1]
        )

    def test_home_omits_company_egress_and_dialer_proxy(self) -> None:
        result = transform_profile(base_template(), HOME, EGRESS)

        self.assertEqual(2, len(result["proxies"]))
        self.assertTrue(all("dialer-proxy" not in proxy for proxy in result["proxies"]))
        groups = {group["name"]: group for group in result["proxy-groups"]}
        self.assertEqual(["DIRECT"], groups[PUBLIC_GROUP]["proxies"])
        self.assertIn("DIRECT", groups["🚀 节点选择"]["proxies"])

    def test_company_rejects_public_direct_rule(self) -> None:
        template = base_template()
        template["rules"].insert(0, "DOMAIN-SUFFIX,example.com,DIRECT")

        with self.assertRaisesRegex(ValidationError, "public DIRECT"):
            transform_profile(template, COMPANY, EGRESS)

    def test_company_rejects_public_socks_server(self) -> None:
        public_egress = EgressConfig(
            name=EGRESS.name,
            server="8.8.8.8",
            port=1080,
        )

        with self.assertRaisesRegex(ValidationError, "local network"):
            transform_profile(base_template(), COMPANY, public_egress)

    def test_company_rejects_pass_rule(self) -> None:
        template = base_template()
        template["rules"].insert(0, "DOMAIN-SUFFIX,example.com,PASS")

        with self.assertRaisesRegex(ValidationError, "bypass rule"):
            transform_profile(template, COMPANY, EGRESS)

    def test_home_rejects_upstream_dialer_proxy(self) -> None:
        template = base_template()
        template["proxies"][0]["dialer-proxy"] = "unexpected-chain"

        with self.assertRaisesRegex(ValidationError, "chained upstreams"):
            transform_profile(template, HOME, EGRESS)

    def test_group_cycle_is_rejected(self) -> None:
        template = base_template()
        template["proxy-groups"].extend(
            [
                {"name": "cycle-a", "type": "select", "proxies": ["cycle-b"]},
                {"name": "cycle-b", "type": "select", "proxies": ["cycle-a"]},
            ]
        )

        with self.assertRaisesRegex(ValidationError, "cycle detected"):
            transform_profile(template, HOME, EGRESS)

    def test_input_template_is_not_mutated(self) -> None:
        template = base_template()
        original = copy.deepcopy(template)

        transform_profile(template, COMPANY, EGRESS)

        self.assertEqual(original, template)


if __name__ == "__main__":
    unittest.main()
