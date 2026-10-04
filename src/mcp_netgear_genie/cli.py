"""Command-Line Interface for Netgear Genie MCP Server & Diagnostic Tool."""

import argparse
import asyncio
import json
import sys
from rich.console import Console
from rich.table import Table

from .client import NetgearGenieClient
from .config import NetgearConfig
from .diagnostics import evaluate_signal_health
from .server import mcp

console = Console()


async def cmd_info(args):
    """Retrieve and display general modem information."""
    config = NetgearConfig(host=args.host, username=args.user, password=args.password)
    client = NetgearGenieClient(config)
    try:
        info = await client.get_modem_info()
        if args.json:
            print(info.model_dump_json(indent=2))
        else:
            table = Table(title=f"Netgear Modem Information ({info.model})")
            table.add_column("Property", style="cyan", no_wrap=True)
            table.add_column("Value", style="green")
            table.add_row("Model", info.model)
            table.add_row("Hardware Version", info.hardware_version)
            table.add_row("Firmware Version", info.firmware_version)
            table.add_row("Serial Number", info.serial_number)
            table.add_row("CM MAC", info.mac_address)
            table.add_row("Certificate", info.certificate_status)
            table.add_row("System Uptime", info.system_uptime)
            table.add_row("Status", info.connection_status)
            console.print(table)
    finally:
        await client.close()


async def cmd_status(args):
    """Retrieve and display DOCSIS channel status."""
    config = NetgearConfig(host=args.host, username=args.user, password=args.password)
    client = NetgearGenieClient(config)
    try:
        status = await client.get_cable_status()
        if args.json:
            print(status.model_dump_json(indent=2))
        else:
            console.print(f"[bold cyan]Netgear DOCSIS Status[/bold cyan] (Uptime: {status.system_uptime})")

            # Downstream table
            ds_table = Table(title="Downstream Bonded Channels")
            ds_table.add_column("Ch", style="cyan", justify="right")
            ds_table.add_column("Lock", style="green")
            ds_table.add_column("Modulation")
            ds_table.add_column("ID", justify="right")
            ds_table.add_column("Freq (MHz)", justify="right")
            ds_table.add_column("Power (dBmV)", justify="right")
            ds_table.add_column("SNR (dB)", justify="right")
            ds_table.add_column("Correctables", justify="right")
            ds_table.add_column("Uncorrectables", justify="right", style="red")

            for ch in status.downstream_channels:
                ds_table.add_row(
                    str(ch.channel),
                    ch.lock_status,
                    ch.modulation,
                    str(ch.channel_id),
                    f"{ch.frequency_mhz:.1f}",
                    f"{ch.power_dbmv:+.1f}",
                    f"{ch.snr_mer_db:.1f}",
                    f"{ch.correctable_codewords:,}",
                    f"{ch.uncorrectable_codewords:,}"
                )
            console.print(ds_table)

            # Upstream table
            us_table = Table(title="Upstream Bonded Channels")
            us_table.add_column("Ch", style="cyan", justify="right")
            us_table.add_column("Lock", style="green")
            us_table.add_column("Modulation")
            us_table.add_column("ID", justify="right")
            us_table.add_column("Freq (MHz)", justify="right")
            us_table.add_column("Power (dBmV)", justify="right")

            for ch in status.upstream_channels:
                us_table.add_row(
                    str(ch.channel),
                    ch.lock_status,
                    ch.modulation,
                    str(ch.channel_id),
                    f"{ch.frequency_mhz:.1f}",
                    f"{ch.power_dbmv:.1f}"
                )
            console.print(us_table)

            # OFDM table if present
            if status.ofdm_channels:
                ofdm_table = Table(title="Downstream OFDM Channels (DOCSIS 3.1)")
                ofdm_table.add_column("Ch", style="cyan", justify="right")
                ofdm_table.add_column("Lock", style="green")
                ofdm_table.add_column("Profile")
                ofdm_table.add_column("Freq (MHz)", justify="right")
                ofdm_table.add_column("Power (dBmV)", justify="right")
                ofdm_table.add_column("SNR (dB)", justify="right")
                ofdm_table.add_column("Uncorrectables", justify="right", style="red")
                for ch in status.ofdm_channels:
                    ofdm_table.add_row(
                        str(ch.channel),
                        ch.lock_status,
                        ch.modulation_profile,
                        f"{ch.frequency_mhz:.1f}",
                        f"{ch.power_dbmv:+.1f}",
                        f"{ch.snr_mer_db:.1f}",
                        f"{ch.uncorrectable_codewords:,}"
                    )
                console.print(ofdm_table)
    finally:
        await client.close()


async def cmd_health(args):
    """Evaluate and display RF signal health."""
    config = NetgearConfig(host=args.host, username=args.user, password=args.password)
    client = NetgearGenieClient(config)
    try:
        status = await client.get_cable_status()
        summary = evaluate_signal_health(status)
        if args.json:
            print(summary.model_dump_json(indent=2))
        else:
            status_color = "green" if summary.overall_status == "HEALTHY" else "yellow" if summary.overall_status == "ATTENTION_NEEDED" else "red"
            console.print(f"Overall RF Health: [{status_color} bold]{summary.overall_status}[/{status_color} bold]")
            console.print(f"Downstream Channels: {summary.healthy_downstream}/{summary.total_downstream} healthy")
            console.print(f"Upstream Channels:   {summary.healthy_upstream}/{summary.total_upstream} healthy")
            console.print(f"Uncorrectable Codewords: {summary.total_uncorrectable_errors:,}")
            if summary.recommendations:
                console.print("\n[bold]Recommendations:[/bold]")
                for r in summary.recommendations:
                    console.print(f" - {r}")
    finally:
        await client.close()


async def cmd_logs(args):
    """Retrieve and display event logs."""
    config = NetgearConfig(host=args.host, username=args.user, password=args.password)
    client = NetgearGenieClient(config)
    try:
        logs = await client.get_event_logs(
            min_priority=args.priority,
            limit=args.limit,
            keyword=args.keyword
        )
        if args.json:
            print(logs.model_dump_json(indent=2))
        else:
            table = Table(title=f"Netgear Event Logs ({logs.returned_entries}/{logs.total_entries})")
            table.add_column("Time", style="cyan", no_wrap=True)
            table.add_column("Priority", style="bold")
            table.add_column("Description")

            for entry in logs.logs:
                color = "red" if entry.priority_level <= 3 else "yellow" if entry.priority_level <= 5 else "white"
                table.add_row(
                    entry.timestamp,
                    f"[{color}]{entry.priority}[/{color}]",
                    entry.description
                )
            console.print(table)
    finally:
        await client.close()


def main():
    """Main CLI parser."""
    parser = argparse.ArgumentParser(description="Netgear Genie MCP Server & Diagnostic CLI")
    parser.add_argument("--host", default=NetgearConfig.host, help="Modem URL (default: http://192.168.100.1)")
    parser.add_argument("--user", default=NetgearConfig.username, help="Modem username (default: admin)")
    parser.add_argument("--password", default=NetgearConfig.password, help="Modem password (default from env)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")

    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # info
    subparsers.add_parser("info", help="Display modem metadata")

    # status
    subparsers.add_parser("status", help="Display DOCSIS channel stats")

    # health
    subparsers.add_parser("health", help="Evaluate DOCSIS RF signal health")

    # logs
    log_parser = subparsers.add_parser("logs", help="Display DOCSIS event logs")
    log_parser.add_argument("--priority", help="Filter by minimum priority ('Critical', 'Warning', etc.)")
    log_parser.add_argument("--limit", type=int, default=50, help="Max entries to return (default: 50)")
    log_parser.add_argument("--keyword", help="Search string in description")

    # server
    subparsers.add_parser("server", help="Start the FastMCP stdio server")

    args = parser.parse_args()

    if not args.subcommand or args.subcommand == "server":
        mcp.run()
    elif args.subcommand == "info":
        asyncio.run(cmd_info(args))
    elif args.subcommand == "status":
        asyncio.run(cmd_status(args))
    elif args.subcommand == "health":
        asyncio.run(cmd_health(args))
    elif args.subcommand == "logs":
        asyncio.run(cmd_logs(args))


if __name__ == "__main__":
    main()
