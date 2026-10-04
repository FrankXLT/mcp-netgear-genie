"""FastMCP Server implementation for Netgear Genie Cable Modems."""

import logging
from typing import Optional, Any, Union
from mcp.server.fastmcp import FastMCP

from .client import NetgearGenieClient
from .config import NetgearConfig
from .diagnostics import evaluate_signal_health
from .formatters import (
    format_modem_info_markdown,
    format_cable_status_markdown,
    format_signal_health_markdown,
    format_event_logs_markdown,
    format_dashboard_markdown,
)
from .models import (
    ModemInfoResponse,
    CableStatusResponse,
    SignalHealthSummary,
    EventLogResponse,
    DashboardSummaryResponse,
    ActionResponse,
)

logger = logging.getLogger(__name__)

# Initialize FastMCP Server
mcp = FastMCP("netgear-genie")
client = NetgearGenieClient()


@mcp.tool()
async def get_dashboard_summary(format: str = "table") -> Any:
    """
    Consolidated executive health check and gateway dashboard (mirroring Netgear Genie Basic tab).
    Combines modem hardware info, RF signal vitals, and recent DOCSIS event logs in a single call.

    Args:
        format: Output presentation format. Options:
                - 'table': Rendered visual Markdown dashboard (Default, recommended for AI chat).
                - 'json': Structured JSON dictionary for programmatic processing.
                - 'both': Returns dictionary containing both markdown and structured data.
    """
    dashboard = await client.get_dashboard_summary()
    if format.lower() == "json":
        return dashboard.model_dump()
    elif format.lower() == "both":
        return {
            "markdown": format_dashboard_markdown(dashboard),
            "data": dashboard.model_dump()
        }
    return format_dashboard_markdown(dashboard)


@mcp.tool()
async def get_modem_info(format: str = "table") -> Any:
    """
    Retrieve hardware revision, firmware version, serial number, MAC address,
    and system uptime for the Netgear Genie cable modem (CM1000).

    Args:
        format: 'table' for formatted Markdown card, 'json' for raw structured dictionary, or 'both'.
    """
    info = await client.get_modem_info()
    if format.lower() == "json":
        return info.model_dump()
    elif format.lower() == "both":
        return {
            "markdown": format_modem_info_markdown(info),
            "data": info.model_dump()
        }
    return format_modem_info_markdown(info)


@mcp.tool()
async def get_cable_status(active_only: bool = True, format: str = "table") -> Any:
    """
    Scrape DOCSIS 3.1 channel diagnostics:
    - Startup Procedure status
    - Downstream bonded channels (Frequency, Power dBmV, SNR dB, Unerrored & Uncorrectable codewords)
    - Upstream bonded channels (Frequency, Transmit Power dBmV, Modulation)
    - Downstream OFDM & Upstream OFDMA channels with Active Subcarrier Ranges
    - Frequency Start Value & System uptime

    Args:
        active_only: If True (default), filters out inactive/unlocked channel slots (e.g. channels 25-32).
                     If False, returns all 32 downstream and 8 upstream slots allocated by firmware.
        format: 'table' for rich Markdown tables matching Netgear Genie UI, 'json' for raw dictionary, or 'both'.
    """
    status = await client.get_cable_status(active_only=active_only)
    if format.lower() == "json":
        return status.model_dump()
    elif format.lower() == "both":
        return {
            "markdown": format_cable_status_markdown(status),
            "data": status.model_dump()
        }
    return format_cable_status_markdown(status)


@mcp.tool()
async def get_signal_health(format: str = "table") -> Any:
    """
    Evaluate DOCSIS RF signal health across all downstream and upstream channels.
    Flags power level anomalies, low SNR, and uncorrectable packet errors with
    actionable cabling/splitter recommendations.

    Args:
        format: 'table' for formatted diagnostic report, 'json' for raw dictionary, or 'both'.
    """
    status = await client.get_cable_status(active_only=True)
    health = evaluate_signal_health(status)
    if format.lower() == "json":
        return health.model_dump()
    elif format.lower() == "both":
        return {
            "markdown": format_signal_health_markdown(health),
            "data": health.model_dump()
        }
    return format_signal_health_markdown(health)


@mcp.tool()
async def get_event_logs(
    min_priority: Optional[str] = None,
    limit: int = 50,
    keyword: Optional[str] = None,
    format: str = "table"
) -> Any:
    """
    Retrieve and parse DOCSIS event logs from the modem.
    Decomposes CM-MAC, CMTS-MAC, DOCSIS version, and QoS profile parameters.

    Args:
        min_priority: Minimum severity to return ('Critical', 'Error', 'Warning', 'Notice').
        limit: Maximum number of entries to return (default: 50).
        keyword: Optional search string in log description (e.g. 'T3', 'SYNC', 'DHCP').
        format: 'table' for formatted Markdown table with priority summary, 'json' for raw dictionary, or 'both'.
    """
    logs = await client.get_event_logs(
        min_priority=min_priority,
        limit=limit,
        keyword=keyword
    )
    if format.lower() == "json":
        return logs.model_dump()
    elif format.lower() == "both":
        return {
            "markdown": format_event_logs_markdown(logs),
            "data": logs.model_dump()
        }
    return format_event_logs_markdown(logs)


@mcp.tool()
async def clear_event_logs(confirm: bool = False) -> ActionResponse:
    """
    Clear the modem's internal DOCSIS event log table.

    Args:
        confirm: Must be explicitly set to True to prevent accidental log loss.
    """
    if not confirm:
        return ActionResponse(
            success=False,
            action="clear_event_logs",
            message="Confirmation required. Pass confirm=True to clear logs."
        )
    return await client.clear_event_logs()


@mcp.tool()
async def reboot_modem(confirm: bool = False) -> ActionResponse:
    """
    Trigger a graceful software reboot of the Netgear cable modem.

    Args:
        confirm: Must be explicitly set to True to execute reboot.
    """
    if not confirm:
        return ActionResponse(
            success=False,
            action="reboot_modem",
            message="Confirmation required. Pass confirm=True to trigger modem reboot."
        )
    return await client.reboot_modem()


@mcp.resource("netgear://modem/info")
async def resource_modem_info() -> str:
    """Provides modem metadata as JSON."""
    info = await client.get_modem_info()
    return info.model_dump_json(indent=2)


@mcp.resource("netgear://modem/cable-status")
async def resource_cable_status() -> str:
    """Provides full DOCSIS connection diagnostics as JSON."""
    status = await client.get_cable_status()
    return status.model_dump_json(indent=2)


@mcp.resource("netgear://modem/event-logs")
async def resource_event_logs() -> str:
    """Provides recent DOCSIS event logs as JSON."""
    logs = await client.get_event_logs(limit=50)
    return logs.model_dump_json(indent=2)


def main():
    """Server entrypoint."""
    mcp.run()


if __name__ == "__main__":
    main()

