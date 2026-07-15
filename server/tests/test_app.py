import sys
import tempfile
import unittest
from pathlib import Path

import yaml


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from profiles import EgressConfig  # noqa: E402
from settings import Settings  # noqa: E402
from test_transformer import base_template  # noqa: E402


class FakeSubconverterClient:
    def __init__(self):
        self.calls = []

    def generate(self, nodes_url: str) -> dict:
        self.calls.append(nodes_url)
        return base_template()


class AppTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.sources_file = root / "sources.yaml"
        self.profiles_file = root / "profiles.yaml"
        self.sources_file.write_text(
            yaml.safe_dump(
                {
                    "sources": {
                        "yll": {
                            "token": "source-token",
                            "url": "https://nodes.example.invalid/profile.yaml",
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        self.profiles_file.write_text(
            yaml.safe_dump(
                {
                    "profiles": {
                        "company": {
                            "force_public_egress": True,
                            "chain_upstreams": True,
                        },
                        "home": {
                            "force_public_egress": False,
                            "chain_upstreams": False,
                        },
                    }
                }
            ),
            encoding="utf-8",
        )
        self.settings = Settings(
            subconverter_url="http://subconverter.invalid/sub",
            common_config_url="https://config.example.invalid/common.ini",
            sources_file=str(self.sources_file),
            profiles_file=str(self.profiles_file),
            service_token="service-token",
            legacy_profile="company",
            listen_host="127.0.0.1",
            listen_port=25500,
            request_timeout_seconds=10,
            cache_ttl_seconds=300,
            company_egress=EgressConfig(
                name="🏢 公司 SOCKS5",
                server="192.168.1.10",
                port=1080,
            ),
        )
        self.subconverter = FakeSubconverterClient()
        self.app = create_app(self.settings, client=self.subconverter)
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _get_profile(self, profile: str):
        return self.client.get(
            f"/service-token/sub/yll/source-token/clash/{profile}"
        )

    def test_company_and_home_endpoints_generate_distinct_profiles(self) -> None:
        company = self._get_profile("company")
        home = self._get_profile("home")

        self.assertEqual(200, company.status_code)
        self.assertEqual(200, home.status_code)
        company_yaml = yaml.safe_load(company.text)
        home_yaml = yaml.safe_load(home.text)
        self.assertEqual("🏢 公司 SOCKS5", company_yaml["proxies"][0]["name"])
        self.assertEqual(2, len(home_yaml["proxies"]))
        self.assertEqual(2, len(self.subconverter.calls))

    def test_legacy_endpoint_keeps_company_behavior(self) -> None:
        response = self.client.get(
            "/service-token/sub/yll/source-token/clash"
        )

        self.assertEqual(200, response.status_code)
        profile = yaml.safe_load(response.text)
        self.assertEqual("🏢 公司 SOCKS5", profile["proxies"][0]["name"])

    def test_profile_response_is_cached(self) -> None:
        self._get_profile("home")
        self._get_profile("home")

        self.assertEqual(1, len(self.subconverter.calls))

    def test_unknown_credentials_and_profile_return_not_found(self) -> None:
        self.assertEqual(
            404,
            self.client.get(
                "/wrong/sub/yll/source-token/clash/company"
            ).status_code,
        )
        self.assertEqual(
            404,
            self.client.get(
                "/service-token/sub/yll/wrong/clash/company"
            ).status_code,
        )
        self.assertEqual(404, self._get_profile("unknown").status_code)

    def test_healthz_lists_profiles(self) -> None:
        response = self.client.get("/healthz")

        self.assertEqual(200, response.status_code)
        self.assertEqual(["company", "home"], response.json["profiles"])


if __name__ == "__main__":
    unittest.main()
