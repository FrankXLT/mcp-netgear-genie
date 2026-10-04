"""Unit tests for Netgear Genie MCP Client and Diagnostic Engine using unittest."""

import unittest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from mcp_netgear_genie.client import NetgearGenieClient
from mcp_netgear_genie.config import NetgearConfig
from mcp_netgear_genie.diagnostics import evaluate_signal_health
from mcp_netgear_genie.models import (
    CableStatusResponse,
    DownstreamChannel,
    UpstreamChannel,
    OFDMChannel,
)

SAMPLE_DOCSIS_HTML = """
<html>
<body>
<table>
    <tr><th>Startup Procedure</th><th>Status</th><th>Comment</th></tr>
    <tr><td>Acquire Downstream Channel</td><td>Locked</td><td>621000000 Hz</td></tr>
    <tr><td>Connectivity State</td><td>OK</td><td>Operational</td></tr>
    <tr><td>Boot State</td><td>OK</td><td>Operational</td></tr>
    <tr><td>Security</td><td>Enabled</td><td>BPI+</td></tr>
    <tr><td>IP Provisioning Mode</td><td>Honor MDD</td><td>IPv4 only</td></tr>
</table>

<table>
    <tr>
        <th>Channel</th><th>Lock Status</th><th>Modulation</th><th>Channel ID</th>
        <th>Frequency</th><th>Power</th><th>SNR / MER</th><th>Unerrored Codewords</th>
        <th>Correctable Codewords</th><th>Uncorrectable Codewords</th>
    </tr>
    <tr>
        <td>1</td><td>Locked</td><td>QAM256</td><td>1</td><td>621000000 Hz</td>
        <td>-1.2 dBmV</td><td>38.2 dB</td><td>12345678</td><td>100</td><td>0</td>
    </tr>
    <tr>
        <td>2</td><td>Locked</td><td>QAM256</td><td>2</td><td>627000000 Hz</td>
        <td>-1.5 dBmV</td><td>37.9 dB</td><td>12345600</td><td>150</td><td>5</td>
    </tr>
</table>

<table>
    <tr>
        <th>Channel</th><th>Lock Status</th><th>Modulation</th><th>Channel ID</th>
        <th>Frequency</th><th>Power</th>
    </tr>
    <tr>
        <td>1</td><td>Locked</td><td>ATDMA</td><td>1</td><td>17400000 Hz</td><td>42.5 dBmV</td>
    </tr>
    <tr>
        <td>2</td><td>Locked</td><td>ATDMA</td><td>2</td><td>23800000 Hz</td><td>43.0 dBmV</td>
    </tr>
</table>

<table>
    <tr>
        <th>Channel</th><th>Lock Status</th><th>Modulation / Profile ID</th><th>Channel ID</th>
        <th>Frequency</th><th>Power</th><th>SNR / MER</th><th>Active Subcarrier Number Range</th>
        <th>Unerrored Codewords</th><th>Correctable Codewords</th><th>Uncorrectable Codewords</th>
    </tr>
    <tr>
        <td>1</td><td>Locked</td><td>0, 1, 2, 3</td><td>193</td><td>850000000 Hz</td>
        <td>0.5 dBmV</td><td>40.2 dB</td><td>296 ~ 7615</td><td>999999</td><td>50</td><td>0</td>
    </tr>
</table>
</body>
</html>
"""


SAMPLE_EVENT_LOG_XML = """
<docsDevEventTable>
    <tr>
        <docsDevEvIndex>1</docsDevEvIndex>
        <docsDevEvFirstTime>2026-09-28, 12:43:09</docsDevEvFirstTime>
        <docsDevEvLastTime>2026-09-28, 12:43:09</docsDevEvLastTime>
        <docsDevEvCounts>1</docsDevEvCounts>
        <docsDevEvLevel>3</docsDevEvLevel>
        <docsDevEvId>82000200</docsDevEvId>
        <docsDevEvText>No Ranging Response received - T3 time-out;CM-MAC=20:76:8f:11:22:33;CMTS-MAC=00:01:5c:66:77:88;CM-QOS=1.1;CM-VER=3.1;</docsDevEvText>
    </tr>
    <tr>
        <docsDevEvIndex>2</docsDevEvIndex>
        <docsDevEvFirstTime>2026-09-28, 15:00:00</docsDevEvFirstTime>
        <docsDevEvLastTime>2026-09-28, 15:00:00</docsDevEvLastTime>
        <docsDevEvCounts>5</docsDevEvCounts>
        <docsDevEvLevel>5</docsDevEvLevel>
        <docsDevEvId>84000100</docsDevEvId>
        <docsDevEvText>DHCP WARNING - Non-critical field invalid in response;</docsDevEvText>
    </tr>
</docsDevEventTable>
"""

class TestNetgearGenie(unittest.TestCase):
    def test_parse_docsis_html_tables(self):
        client = NetgearGenieClient(NetgearConfig())
        response = CableStatusResponse()
        client._parse_docsis_html_tables(SAMPLE_DOCSIS_HTML, response)

        # Verify Startup Procedure
        self.assertEqual(len(response.startup_procedure), 5)
        self.assertEqual(response.startup_procedure[0].procedure, "Acquire Downstream Channel")
        self.assertEqual(response.startup_procedure[0].status, "Locked")

        # Verify Downstream Channels
        self.assertEqual(len(response.downstream_channels), 2)
        ch1 = response.downstream_channels[0]
        self.assertEqual(ch1.channel, 1)
        self.assertEqual(ch1.lock_status, "Locked")
        self.assertEqual(ch1.modulation, "QAM256")
        self.assertEqual(ch1.frequency_mhz, 621.0)
        self.assertEqual(ch1.power_dbmv, -1.2)
        self.assertEqual(ch1.snr_mer_db, 38.2)
        self.assertEqual(ch1.uncorrectable_codewords, 0)

        # Verify Upstream Channels
        self.assertEqual(len(response.upstream_channels), 2)
        us1 = response.upstream_channels[0]
        self.assertEqual(us1.channel, 1)
        self.assertEqual(us1.modulation, "ATDMA")
        self.assertEqual(us1.power_dbmv, 42.5)

        # Verify OFDM Channels
        self.assertEqual(len(response.ofdm_channels), 1)
        ofdm = response.ofdm_channels[0]
        self.assertEqual(ofdm.channel_id, 193)
        self.assertEqual(ofdm.power_dbmv, 0.5)
        self.assertEqual(ofdm.snr_mer_db, 40.2)

    def test_signal_health_diagnostics_healthy(self):
        status = CableStatusResponse(
            downstream_channels=[
                DownstreamChannel(
                    channel=1, lock_status="Locked", modulation="QAM256", channel_id=1,
                    frequency_hz=621000000, frequency_mhz=621.0, power_dbmv=0.0, snr_mer_db=38.0,
                    unerrored_codewords=1000, correctable_codewords=0, uncorrectable_codewords=0
                )
            ],
            upstream_channels=[
                UpstreamChannel(
                    channel=1, lock_status="Locked", modulation="ATDMA", channel_id=1,
                    frequency_hz=24000000, frequency_mhz=24.0, power_dbmv=42.0
                )
            ]
        )

        health = evaluate_signal_health(status)
        self.assertEqual(health.overall_status, "HEALTHY")
        self.assertEqual(health.healthy_downstream, 1)
        self.assertEqual(health.healthy_upstream, 1)
        self.assertEqual(health.total_uncorrectable_errors, 0)

    def test_signal_health_diagnostics_critical_power(self):
        status = CableStatusResponse(
            downstream_channels=[
                DownstreamChannel(
                    channel=1, lock_status="Locked", modulation="QAM256", channel_id=1,
                    frequency_hz=621000000, frequency_mhz=621.0, power_dbmv=-12.5, snr_mer_db=28.0,
                    unerrored_codewords=1000, correctable_codewords=50, uncorrectable_codewords=500
                )
            ],
            upstream_channels=[
                UpstreamChannel(
                    channel=1, lock_status="Locked", modulation="ATDMA", channel_id=1,
                    frequency_hz=24000000, frequency_mhz=24.0, power_dbmv=53.0
                )
            ]
        )

        health = evaluate_signal_health(status)
        self.assertEqual(health.overall_status, "CRITICAL")
        self.assertEqual(health.healthy_downstream, 0)
        self.assertEqual(health.healthy_upstream, 0)
        self.assertEqual(health.total_uncorrectable_errors, 500)
        self.assertGreater(len(health.recommendations), 0)



    def test_parse_event_log_xml(self):
        import xml.etree.ElementTree as ET
        from mcp_netgear_genie.models import EventLogEntry
        from mcp_netgear_genie.client import PRIORITY_MAP

        root = ET.fromstring(SAMPLE_EVENT_LOG_XML.strip())
        entries = []
        for tr in root.findall(".//tr"):
            data = {child.tag: (child.text or "").strip() for child in tr}
            idx = int(data.get("docsDevEvIndex", "0"))
            level_val = int(data.get("docsDevEvLevel", "6"))
            entries.append(EventLogEntry(
                index=idx,
                timestamp=data.get("docsDevEvLastTime", ""),
                priority=PRIORITY_MAP.get(level_val, f"Level {level_val}"),
                priority_level=level_val,
                event_id=data.get("docsDevEvId", ""),
                counts=int(data.get("docsDevEvCounts", "1")),
                description=data.get("docsDevEvText", "")
            ))

        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].index, 1)
        self.assertEqual(entries[0].priority, "Critical (3)")
        self.assertEqual(entries[0].priority_level, 3)
        self.assertIn("T3 time-out", entries[0].description)

        self.assertEqual(entries[1].index, 2)
        self.assertEqual(entries[1].priority, "Warning (5)")
        self.assertEqual(entries[1].counts, 5)

    def test_parse_uptime(self):
        from mcp_netgear_genie.client import parse_uptime

        secs, display = parse_uptime("484:35:10")
        self.assertEqual(secs, 484 * 3600 + 35 * 60 + 10)
        self.assertIn("20 days", display)
        self.assertIn("4 hrs", display)
        self.assertIn("35 mins", display)

        secs2, display2 = parse_uptime("21 days 02:40:02")
        self.assertEqual(secs2, 21 * 86400 + 2 * 3600 + 40 * 60 + 2)
        self.assertEqual(display2, "21 days, 2 hrs, 40 mins")

    def test_formatters_markdown(self):
        from mcp_netgear_genie.models import ModemInfoResponse, EventLogResponse, EventLogEntry
        from mcp_netgear_genie.formatters import (
            format_modem_info_markdown,
            format_cable_status_markdown,
            format_signal_health_markdown,
            format_event_logs_markdown,
        )

        # Test modem info formatting
        info = ModemInfoResponse(
            model="CM1000",
            hardware_version="2.02",
            firmware_version="V7.01.01",
            serial_number="1234567890ABC",
            mac_address="AA:BB:CC:DD:EE:FF",
            system_uptime="484:35:10",
            system_uptime_display="20 days, 4 hrs, 35 mins"
        )
        md_info = format_modem_info_markdown(info)
        self.assertIn("Netgear Genie Modem Information (CM1000)", md_info)
        self.assertIn("1234567890ABC", md_info)
        self.assertIn("20 days, 4 hrs, 35 mins", md_info)

        # Test cable status formatting
        status = CableStatusResponse(
            starting_frequency_hz=519000000,
            starting_frequency_mhz=519.0,
            total_locked_downstream=1,
            downstream_channels=[
                DownstreamChannel(
                    channel=1, lock_status="Locked", modulation="QAM256", channel_id=17,
                    frequency_hz=525000000, frequency_mhz=525.0, power_dbmv=15.6, snr_mer_db=37.9,
                    unerrored_codewords=1000, correctable_codewords=0, uncorrectable_codewords=0
                )
            ],
            ofdm_channels=[
                OFDMChannel(
                    channel=1, lock_status="Locked", modulation_profile="0, 1, 2, 3", channel_id=159,
                    frequency_hz=862000000, frequency_mhz=862.0, power_dbmv=17.0, snr_mer_db=36.8,
                    active_subcarrier_range="290 ~ 3809"
                )
            ]
        )
        md_cable = format_cable_status_markdown(status)
        self.assertIn("519.0 MHz", md_cable)
        self.assertIn("290 ~ 3809", md_cable)
        self.assertIn("+15.6 dBmV", md_cable)

        # Test event log formatting
        logs = EventLogResponse(
            total_entries=1,
            returned_entries=1,
            priority_breakdown={"Critical (3)": 1},
            logs=[
                EventLogEntry(
                    index=1,
                    timestamp="2026-10-04, 00:50:06",
                    priority="Critical (3)",
                    priority_level=3,
                    event_id="82000200",
                    description="No Ranging Response received - T3 time-out;CM-MAC=AA:BB:CC:DD:EE:FF;",
                    clean_message="No Ranging Response received - T3 time-out",
                    cm_mac="AA:BB:CC:DD:EE:FF"
                )
            ]
        )
        md_logs = format_event_logs_markdown(logs)
        self.assertIn("No Ranging Response received - T3 time-out", md_logs)
        self.assertIn("Critical (3)", md_logs)


if __name__ == "__main__":
    unittest.main()
