from typing import Optional

import requests
import yaml


class SubconverterClient:
    def __init__(
        self,
        endpoint: str,
        common_config_url: str,
        timeout_seconds: int,
        session: Optional[requests.Session] = None,
    ):
        self._endpoint = endpoint
        self._common_config_url = common_config_url
        self._timeout_seconds = timeout_seconds
        self._session = session or requests.Session()

    def generate(self, nodes_url: str) -> dict:
        response = self._session.get(
            self._endpoint,
            params={
                "target": "clash",
                "url": nodes_url,
                "config": self._common_config_url,
            },
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        data = yaml.safe_load(response.text)
        if not isinstance(data, dict):
            raise ValueError("subconverter returned a non-mapping YAML document")
        return data
