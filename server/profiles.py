from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    name: str
    force_public_egress: bool
    chain_upstreams: bool

    def validate(self) -> None:
        if self.chain_upstreams != self.force_public_egress:
            raise ValueError(
                f"profile {self.name!r} must force public egress and chain upstreams together"
            )


@dataclass(frozen=True)
class EgressConfig:
    name: str
    server: str
    port: int
    proxy_type: str = "socks5"
    username: str = ""
    password: str = ""
    udp: bool = True

    def to_proxy(self) -> dict:
        proxy = {
            "name": self.name,
            "server": self.server,
            "port": self.port,
            "type": self.proxy_type,
            "udp": self.udp,
        }
        if self.username:
            proxy["username"] = self.username
        if self.password:
            proxy["password"] = self.password
        return proxy
