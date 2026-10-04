# Changelog

All notable changes to `mcp-netgear-genie` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-10-04

### Added
- **Core MCP Server**: FastMCP implementation exposing Netgear Genie cable modem telemetry to AI assistants and LLMs.
- **Executive Dashboard Tool (`get_dashboard_summary`)**: Single-call tool consolidating modem vitals, RF statistics, OFDM channels, and event log counts.
- **DOCSIS 3.1 OFDM Enhancements**:
  - Parsed active subcarrier ranges (e.g. `296 ~ 7895`).
  - Extracted profile IDs (`0, 1, 2, 3`), starting frequency, SNR/MER, and codeword counters.
- **Active Channel Filtering**: Added `active_only` toggle (default: `True`) to filter unbonded/inactive channel slots for clean tabular views.
- **Automated RF Signal Health Diagnostics**:
  - Telecommunication standards-based evaluation for downstream power, downstream SNR, upstream transmit power, and uncorrectable errors.
  - Actionable recommendations for RF attenuation, splitters, and line noise mitigation.
- **Structured DOCSIS Event Log Decomposition**:
  - Extracted clean, human-readable log messages stripped of internal semicolon-separated parameters.
  - Extracted structured fields for CM MAC, CMTS MAC, DOCSIS Version, and QoS profiles.
  - Aggregate severity breakdown table (`Critical`, `Error`, `Warning`, `Notice`).
- **Presentation Layer (`formatters.py`)**:
  - Visual Markdown table presentation mirroring Netgear Genie Web UI layout.
  - Dual output support (`format="table" | "json" | "both"`) across all tools.
- **Human-Readable Uptime**: Formats raw uptime into both total seconds and friendly duration strings (`"20 days, 7 hrs, 51 mins"`).
- **Standalone CLI Diagnostic Tool**: Multi-command CLI (`status`, `health`, `info`, `logs`) with JSON and table flags.
- **Supergateway / Remote Docker Support**: Ready-to-deploy Docker Compose recipes for remote SSE streaming.
