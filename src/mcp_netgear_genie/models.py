"""Data models for Netgear Genie MCP Server responses.

Uses dataclasses for zero-dependency execution and full FastMCP compatibility.
"""

import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any


class BaseModelCompat:
    """Base compatibility class providing JSON serialization methods."""
    def model_dump_json(self, indent: Optional[int] = None) -> str:
        return json.dumps(asdict(self), indent=indent)

    def model_dump(self) -> dict:
        return asdict(self)


@dataclass
class ModemInfoResponse(BaseModelCompat):
    """General metadata and status of the Netgear cable modem."""
    model: str = "CM1000"
    hardware_version: str = "Unknown"
    firmware_version: str = "Unknown"
    serial_number: str = "Unknown"
    mac_address: str = "Unknown"
    certificate_status: str = "Installed"
    system_uptime: str = "Unknown"
    system_uptime_seconds: int = 0
    system_uptime_display: str = "Unknown"
    network_access: str = "Allowed"
    connection_status: str = "GOOD"


@dataclass
class StartupProcedureItem(BaseModelCompat):
    """Individual item in the DOCSIS startup procedure."""
    procedure: str
    status: str
    comment: str = ""


@dataclass
class DownstreamChannel(BaseModelCompat):
    """DOCSIS SC-QAM downstream bonded channel statistics."""
    channel: int
    lock_status: str
    modulation: str
    channel_id: int
    frequency_hz: int
    frequency_mhz: float
    power_dbmv: float
    snr_mer_db: float
    unerrored_codewords: int = 0
    correctable_codewords: int = 0
    uncorrectable_codewords: int = 0


@dataclass
class UpstreamChannel(BaseModelCompat):
    """DOCSIS SC-QAM upstream bonded channel statistics."""
    channel: int
    lock_status: str
    modulation: str
    channel_id: int
    frequency_hz: int
    frequency_mhz: float
    power_dbmv: float


@dataclass
class OFDMChannel(BaseModelCompat):
    """DOCSIS 3.1 Downstream OFDM channel statistics."""
    channel: int
    lock_status: str
    modulation_profile: str
    channel_id: int
    frequency_hz: int
    frequency_mhz: float
    power_dbmv: float
    snr_mer_db: float
    active_subcarrier_range: str = ""
    unerrored_codewords: int = 0
    correctable_codewords: int = 0
    uncorrectable_codewords: int = 0


@dataclass
class OFDMAChannel(BaseModelCompat):
    """DOCSIS 3.1 Upstream OFDMA channel statistics."""
    channel: int
    lock_status: str
    modulation_profile: str
    channel_id: int
    frequency_hz: int
    frequency_mhz: float
    power_dbmv: float
    active_subcarrier_range: str = ""


@dataclass
class CableStatusResponse(BaseModelCompat):
    """Complete DOCSIS cable connection diagnostic state."""
    startup_procedure: List[StartupProcedureItem] = field(default_factory=list)
    downstream_channels: List[DownstreamChannel] = field(default_factory=list)
    upstream_channels: List[UpstreamChannel] = field(default_factory=list)
    ofdm_channels: List[OFDMChannel] = field(default_factory=list)
    ofdma_channels: List[OFDMAChannel] = field(default_factory=list)
    starting_frequency_hz: int = 0
    starting_frequency_mhz: float = 0.0
    total_locked_downstream: int = 0
    total_locked_upstream: int = 0
    total_locked_ofdm: int = 0
    total_locked_ofdma: int = 0
    system_uptime: str = "Unknown"
    system_uptime_seconds: int = 0
    system_uptime_display: str = "Unknown"
    current_time: str = "Unknown"


@dataclass
class ChannelEvaluation(BaseModelCompat):
    """Diagnostic evaluation for an individual RF channel."""
    channel_id: int
    channel_type: str  # downstream, upstream, ofdm, ofdma
    power_dbmv: float
    snr_db: Optional[float] = None
    uncorrectables: int = 0
    status: str = "GOOD"  # GOOD, WARNING, CRITICAL
    issues: List[str] = field(default_factory=list)


@dataclass
class SignalHealthSummary(BaseModelCompat):
    """DOCSIS RF health analysis across all channels."""
    overall_status: str
    total_downstream: int
    healthy_downstream: int
    total_upstream: int
    healthy_upstream: int
    total_uncorrectable_errors: int
    downstream_power_min: float = 0.0
    downstream_power_max: float = 0.0
    downstream_power_avg: float = 0.0
    downstream_snr_avg: float = 0.0
    upstream_power_min: float = 0.0
    upstream_power_max: float = 0.0
    upstream_power_avg: float = 0.0
    recommendations: List[str] = field(default_factory=list)
    channel_evaluations: List[ChannelEvaluation] = field(default_factory=list)


@dataclass
class EventLogEntry(BaseModelCompat):
    """Individual DOCSIS event log record with decomposed parameters."""
    index: int
    timestamp: str
    priority: str
    priority_level: int
    event_id: str
    counts: int = 1
    description: str = ""
    clean_message: str = ""
    cm_mac: Optional[str] = None
    cmts_mac: Optional[str] = None
    docsis_version: Optional[str] = None
    qos_profile: Optional[str] = None


@dataclass
class EventLogResponse(BaseModelCompat):
    """Set of DOCSIS event logs with priority aggregation."""
    total_entries: int
    returned_entries: int
    priority_breakdown: Dict[str, int] = field(default_factory=dict)
    logs: List[EventLogEntry] = field(default_factory=list)


@dataclass
class DashboardSummaryResponse(BaseModelCompat):
    """Consolidated executive dashboard summary mirroring Netgear Genie UI."""
    model: str
    hardware_version: str
    firmware_version: str
    serial_number: str
    mac_address: str
    certificate_status: str
    connection_status: str
    system_uptime: str
    system_uptime_display: str
    overall_rf_health: str
    health_recommendations: List[str]
    downstream_summary: Dict[str, Any]
    upstream_summary: Dict[str, Any]
    ofdm_summary: Dict[str, Any]
    event_log_summary: Dict[str, Any]


@dataclass
class ActionResponse(BaseModelCompat):
    """Status result of an administrative action (e.g. reboot, clear log)."""
    success: bool
    action: str
    message: str
