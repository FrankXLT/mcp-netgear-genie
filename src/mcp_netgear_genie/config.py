"""Configuration settings for Netgear Genie MCP Server."""

import os
from dataclasses import dataclass


@dataclass
class NetgearConfig:
    """Modem connection and credentials configuration."""
    host: str = os.getenv("NETGEAR_HOST", "http://192.168.100.1").rstrip("/")
    username: str = os.getenv("NETGEAR_USERNAME", "admin")
    password: str = os.getenv("NETGEAR_PASSWORD", "password")
    timeout: float = float(os.getenv("NETGEAR_TIMEOUT", "10.0"))
    verify_ssl: bool = os.getenv("NETGEAR_VERIFY_SSL", "false").lower() in ("true", "1", "yes")
    port: int = int(os.getenv("NETGEAR_PORT", "8000"))

    def get_url(self, endpoint: str) -> str:
        """Construct full URL for a given modem endpoint."""
        clean_endpoint = endpoint.lstrip("/")
        return f"{self.host}/{clean_endpoint}"
