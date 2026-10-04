"""Markdown presentation formatters mirroring Netgear Genie Web UI."""

from typing import Dict, Any, List
from .models import (
    ModemInfoResponse,
    CableStatusResponse,
    SignalHealthSummary,
    EventLogResponse,
    DashboardSummaryResponse,
)


def format_uptime(raw_uptime: str) -> str:
    """Format raw uptime (e.g. '484:35:10' or '21 days 02:40:02') into human readable string."""
    if not raw_uptime or raw_uptime == "Unknown":
        return "Unknown"
    
    # Format: HH:MM:SS
    if ":" in raw_uptime and "day" not in raw_uptime.lower():
        parts = raw_uptime.split(":")
        if len(parts) == 3:
            try:
                hours = int(parts[0])
                mins = int(parts[1])
                secs = int(parts[2])
                days = hours // 24
                rem_hours = hours % 24
                
                parts_str = []
                if days > 0:
                    parts_str.append(f"{days} day{'s' if days != 1 else ''}")
                if rem_hours > 0 or days > 0:
                    parts_str.append(f"{rem_hours} hr{'s' if rem_hours != 1 else ''}")
                parts_str.append(f"{mins} min{'s' if mins != 1 else ''}")
                return ", ".join(parts_str)
            except ValueError:
                pass
    return raw_uptime


def format_modem_info_markdown(info: ModemInfoResponse) -> str:
    """Format modem hardware/firmware metadata as a clean card."""
    lines = [
        f"## 📟 Netgear Genie Modem Information ({info.model})",
        "",
        f"**Connection Status**: `🟢 {info.connection_status}` | **Network Access**: `{info.network_access}`",
        "",
        "| Attribute | Value |",
        "| :--- | :--- |",
        f"| **Model** | `{info.model}` |",
        f"| **Hardware Version** | `{info.hardware_version}` |",
        f"| **Firmware Version** | `{info.firmware_version}` |",
        f"| **Serial Number** | `{info.serial_number}` |",
        f"| **Cable MAC Address** | `{info.mac_address}` |",
        f"| **CM Certificate** | `{info.certificate_status}` |",
        f"| **System Uptime** | {info.system_uptime_display} (`{info.system_uptime}`) |",
        ""
    ]
    return "\n".join(lines)


def format_cable_status_markdown(status: CableStatusResponse) -> str:
    """Format complete DOCSIS channel diagnostic state into tables matching Genie Web UI."""
    lines = [
        "## 📡 DOCSIS Cable Connection Diagnostics",
        "",
        f"**System Up Time**: {status.system_uptime_display} (`{status.system_uptime}`)  ",
        f"**Starting Frequency**: `{status.starting_frequency_mhz:.1f} MHz` ({status.starting_frequency_hz} Hz)  ",
        f"**Bonded Channels**: ⬇️ **{status.total_locked_downstream}** Downstream | ⬆️ **{status.total_locked_upstream}** Upstream | 📶 **{status.total_locked_ofdm}** OFDM",
        "",
        "### ⚙️ Startup Procedure",
        "| Procedure | Status | Comment |",
        "| :--- | :--- | :--- |"
    ]

    for item in status.startup_procedure:
        icon = "🔒" if "locked" in item.comment.lower() or "locked" in item.status.lower() else "✅"
        lines.append(f"| **{item.procedure}** | {icon} {item.status} | {item.comment} |")

    lines.extend([
        "",
        f"### ⬇️ Downstream Bonded Channels ({len(status.downstream_channels)} Channels)",
        "| Ch | Lock | Modulation | ID | Frequency | Power | SNR / MER | Unerrored | Uncorrectable |",
        "|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|"
    ])

    for ch in status.downstream_channels:
        lock_icon = "🔒" if ch.lock_status.lower() == "locked" else "❌"
        # Power highlight
        power_str = f"+{ch.power_dbmv:.1f} dBmV" if ch.power_dbmv > 0 else f"{ch.power_dbmv:.1f} dBmV"
        snr_str = f"{ch.snr_mer_db:.1f} dB"
        err_str = f"⚠️ **{ch.uncorrectable_codewords:,}**" if ch.uncorrectable_codewords > 0 else "0"
        lines.append(
            f"| {ch.channel} | {lock_icon} {ch.lock_status} | {ch.modulation} | {ch.channel_id} | "
            f"{ch.frequency_mhz:.1f} MHz | {power_str} | {snr_str} | {ch.unerrored_codewords:,} | {err_str} |"
        )

    lines.extend([
        "",
        f"### ⬆️ Upstream Bonded Channels ({len(status.upstream_channels)} Channels)",
        "| Ch | Lock | Modulation | ID | Frequency | Power |",
        "|:---:|:---:|:---:|:---:|:---:|:---:|"
    ])

    for ch in status.upstream_channels:
        lock_icon = "🔒" if ch.lock_status.lower() == "locked" else "❌"
        power_str = f"{ch.power_dbmv:.1f} dBmV"
        lines.append(
            f"| {ch.channel} | {lock_icon} {ch.lock_status} | {ch.modulation} | {ch.channel_id} | "
            f"{ch.frequency_mhz:.1f} MHz | {power_str} |"
        )

    if status.ofdm_channels:
        lines.extend([
            "",
            f"### 📶 Downstream OFDM Channels (DOCSIS 3.1, {len(status.ofdm_channels)} Channels)",
            "| Ch | Lock | Profile ID | ID | Frequency | Power | SNR / MER | Active Subcarrier Range | Uncorrectable |",
            "|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|"
        ])
        for ch in status.ofdm_channels:
            lock_icon = "🔒" if ch.lock_status.lower() == "locked" else "❌"
            power_str = f"+{ch.power_dbmv:.1f} dBmV" if ch.power_dbmv > 0 else f"{ch.power_dbmv:.1f} dBmV"
            snr_str = f"{ch.snr_mer_db:.1f} dB"
            subcarrier = ch.active_subcarrier_range or "--"
            err_str = f"⚠️ **{ch.uncorrectable_codewords:,}**" if ch.uncorrectable_codewords > 0 else "0"
            lines.append(
                f"| {ch.channel} | {lock_icon} {ch.lock_status} | `{ch.modulation_profile}` | {ch.channel_id} | "
                f"{ch.frequency_mhz:.1f} MHz | {power_str} | {snr_str} | `{subcarrier}` | {err_str} |"
            )

    return "\n".join(lines)


def format_signal_health_markdown(health: SignalHealthSummary) -> str:
    """Format RF signal health analysis with recommendations and channel warnings."""
    status_icon = "🟢" if health.overall_status == "GOOD" else ("🟡" if health.overall_status == "WARNING" else "🔴")
    
    lines = [
        f"## 🩺 DOCSIS RF Signal Health: {status_icon} **{health.overall_status}**",
        "",
        f"- **Downstream Status**: {health.healthy_downstream}/{health.total_downstream} channels in spec "
        f"(Power: `{health.downstream_power_min:+.1f}` to `{health.downstream_power_max:+.1f}` dBmV, Avg SNR: `{health.downstream_snr_avg:.1f}` dB)",
        f"- **Upstream Status**: {health.healthy_upstream}/{health.total_upstream} channels in spec "
        f"(Power: `{health.upstream_power_min:.1f}` to `{health.upstream_power_max:.1f}` dBmV)",
        f"- **Total Uncorrectable Codewords**: `{health.total_uncorrectable_errors:,}`",
        ""
    ]

    if health.recommendations:
        lines.append("### 💡 Recommendations")
        for rec in health.recommendations:
            lines.append(f"- {rec}")
        lines.append("")

    # Filter out only anomalous channels for compact viewing
    anomalies = [c for c in health.channel_evaluations if c.status != "GOOD"]
    if anomalies:
        lines.extend([
            f"### ⚠️ Flagged Channels ({len(anomalies)} Channels Outside Ideal Spec)",
            "| Type | ID | Power | SNR | Uncorrectable | Status | Findings |",
            "|:---:|:---:|:---:|:---:|:---:|:---:|:---|"
        ])
        for ch in anomalies:
            badge = "🔴 CRITICAL" if ch.status == "CRITICAL" else "🟡 WARNING"
            snr_str = f"{ch.snr_db:.1f} dB" if ch.snr_db is not None else "--"
            issues_str = "; ".join(ch.issues)
            lines.append(f"| {ch.channel_type} | {ch.channel_id} | {ch.power_dbmv:+.1f} dBmV | {snr_str} | {ch.uncorrectables} | {badge} | {issues_str} |")
    else:
        lines.append("✅ **All channels are operating within optimal DOCSIS RF parameters.**")

    return "\n".join(lines)


def format_event_logs_markdown(logs: EventLogResponse) -> str:
    """Format decomposed event logs with priority badges and clean messages."""
    breakdown_parts = []
    for prio, count in logs.priority_breakdown.items():
        if "critical" in prio.lower():
            icon = "🔴"
        elif "error" in prio.lower():
            icon = "🟠"
        elif "warning" in prio.lower():
            icon = "🟡"
        else:
            icon = "ℹ️"
        breakdown_parts.append(f"{icon} **{prio}**: {count}")

    breakdown_str = " | ".join(breakdown_parts) if breakdown_parts else "No logs recorded"

    lines = [
        "## 📜 Cable Modem DOCSIS Event Logs",
        "",
        f"**Showing**: {logs.returned_entries} of {logs.total_entries} logs  ",
        f"**Summary**: {breakdown_str}",
        "",
        "| Time | Priority | Message | CMTS MAC |",
        "| :--- | :--- | :--- | :--- |"
    ]

    for log in logs.logs:
        if "critical" in log.priority.lower():
            prio_badge = f"🔴 `{log.priority}`"
        elif "error" in log.priority.lower():
            prio_badge = f"🟠 `{log.priority}`"
        elif "warning" in log.priority.lower():
            prio_badge = f"🟡 `{log.priority}`"
        else:
            prio_badge = f"ℹ️ `{log.priority}`"

        cmts = f"`{log.cmts_mac}`" if log.cmts_mac else "--"
        msg = log.clean_message or log.description
        lines.append(f"| `{log.timestamp}` | {prio_badge} | {msg} | {cmts} |")

    return "\n".join(lines)


def format_dashboard_markdown(d: DashboardSummaryResponse) -> str:
    """Consolidated executive dashboard mirroring Netgear Genie UI."""
    rf_icon = "🟢" if d.overall_rf_health == "GOOD" else ("🟡" if d.overall_rf_health == "WARNING" else "🔴")

    lines = [
        f"# 🌐 Netgear Genie Gateway Dashboard ({d.model})",
        "",
        f"**Connection Status**: `🟢 {d.connection_status}` | **RF Health**: {rf_icon} ` {d.overall_rf_health}` | **System Uptime**: {d.system_uptime_display}",
        "",
        "### 📟 Hardware & Firmware",
        f"- **Model**: `{d.model}` (HW: `{d.hardware_version}`, FW: `{d.firmware_version}`)",
        f"- **Serial Number**: `{d.serial_number}`",
        f"- **Cable MAC Address**: `{d.mac_address}` (Certificate: `{d.certificate_status}`)",
        "",
        "### 📶 DOCSIS RF Signal Summary",
        f"- **Downstream**: {d.downstream_summary.get('count', 0)} bonded channels (Power: `{d.downstream_summary.get('power_min', 0):+.1f}` to `{d.downstream_summary.get('power_max', 0):+.1f}` dBmV, Avg SNR: `{d.downstream_summary.get('snr_avg', 0):.1f}` dB, Uncorrectables: `{d.downstream_summary.get('uncorrectables', 0):,}`)",
        f"- **Upstream**: {d.upstream_summary.get('count', 0)} bonded channels (Power: `{d.upstream_summary.get('power_min', 0):.1f}` to `{d.upstream_summary.get('power_max', 0):.1f}` dBmV, Avg: `{d.upstream_summary.get('power_avg', 0):.1f}` dBmV)",
        f"- **OFDM (DOCSIS 3.1)**: {d.ofdm_summary.get('count', 0)} channels active (Power: `{d.ofdm_summary.get('power_avg', 0):+.1f}` dBmV, Subcarriers: {d.ofdm_summary.get('subcarrier_ranges', [])})",
        ""
    ]

    if d.health_recommendations:
        lines.append("### 💡 RF Recommendations")
        for rec in d.health_recommendations:
            lines.append(f"- {rec}")
        lines.append("")

    lines.extend([
        "### 📜 DOCSIS Event Log Summary",
        f"- **Total Events**: {d.event_log_summary.get('total', 0)}",
        f"- **Breakdown**: Critical: `{d.event_log_summary.get('critical', 0)}`, Error: `{d.event_log_summary.get('error', 0)}`, Warning: `{d.event_log_summary.get('warning', 0)}`, Notice: `{d.event_log_summary.get('notice', 0)}`",
        ""
    ])

    return "\n".join(lines)
