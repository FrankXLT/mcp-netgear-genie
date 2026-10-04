# `mcp-netgear-genie`

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP Specification](https://img.shields.io/badge/MCP-2024--11--05-brightgreen.svg)](https://modelcontextprotocol.io/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A production-grade **Model Context Protocol (MCP)** server that connects AI assistants (Claude, Cursor, Antigravity, VS Code, Goose) directly to **Netgear Genie cable modems** (specifically the **CM1000 DOCSIS 3.1** and compatible CM-series modems).

It transforms the modem's embedded ASP, JavaScript, and XML administrative web interface into strongly-typed tools, executive dashboards, and real-time RF signal diagnostics.

---

## Supported Hardware

Tested and verified against physical hardware:
- **Netgear CM1000** (DOCSIS 3.1, Hardware 2.02, Firmware V7.01.01+)
- **Netgear CM1100 / CM1150V / CM1200**
- **Netgear CM2000 / CM2050V**
- **Netgear CM500 / CM600 / CM700** (DOCSIS 3.0 mode)
- **Netgear CAX30 / CAX80** (Cable modem gateway status pages)

---

## Key Features

- 🌐 **Single-Call Executive Dashboard (`get_dashboard_summary`)**:
  - Combines modem hardware identity, connection state, RF signal span, OFDM telemetry, and event log breakdown into a single call.
- 📡 **Full DOCSIS 3.1 OFDM Channel Telemetry**:
  - Extracts active subcarrier ranges (e.g. `296 ~ 7895`), modulation profiles (`0, 1, 2, 3`), starting frequency (`447.0 MHz`), power levels, and SNR/MER.
- ⚙️ **Startup Procedure Verification**:
  - Parses the 6-step initialization procedure (Acquire Downstream Channel, Connectivity State, Boot State, Configuration File, Security, IP Provisioning Mode).
- 🩺 **Automated RF Signal Health Diagnostics**:
  - Evaluates downstream and upstream RF power against CableLabs industry specifications.
  - Flags hot/overdriven downstream power (> +10 dBmV), weak signals (< -10 dBmV), low SNR (< 33 dB), and excessive upstream transmit power (> 48 dBmV).
  - Provides actionable cabling and splitter remediation recommendations.
- 📜 **Structured Event Log Decomposition**:
  - Extracts clean error messages stripped of internal semicolon-separated parameters.
  - Parses CM MAC, CMTS MAC, and DOCSIS version into structured fields.
  - Produces an aggregate summary count of events by severity level (`Critical`, `Error`, `Warning`, `Notice`).
- 📊 **Dual Visual Markdown & Programmatic JSON Output**:
  - All tools accept `format: "table" | "json" | "both"`.
  - Default `"table"` format renders rich GitHub-flavored Markdown tables mirroring the Netgear Web UI layout for AI conversations.
- 🔒 **Zero-Config Authentication & Session Management**:
  - Handles dynamic `webToken` extraction from `GenieLogin.asp`, HTTP 302 redirects, and `SessionID` cookie caching.
  - Automatically bypasses system proxy intercepts for `192.168.100.1` and `.lan` domains.
- 🛠️ **Administrative Safety Guards**:
  - Modem reboot and log-clearing tools require explicit `confirm=True` confirmation.

---

## Installation

### From Source / Git
```bash
pip install git+https://github.com/FrankXLT/mcp-netgear-genie.git
```

### Local Development
```bash
git clone https://github.com/FrankXLT/mcp-netgear-genie.git
cd mcp-netgear-genie
pip install -e .
```

---

## Quickstart & Client Configuration

### 1. Claude Desktop
Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "netgear-genie": {
      "command": "python3",
      "args": ["-m", "mcp_netgear_genie.server"],
      "env": {
        "NETGEAR_HOST": "http://192.168.100.1",
        "NETGEAR_USERNAME": "admin",
        "NETGEAR_PASSWORD": "your_modem_password"
      }
    }
  }
}
```

### 2. Cursor
Add to your project's `.cursor/mcp.json` or user settings:

```json
{
  "mcpServers": {
    "netgear-genie": {
      "command": "python3",
      "args": ["-m", "mcp_netgear_genie.server"],
      "env": {
        "NETGEAR_HOST": "http://192.168.100.1",
        "NETGEAR_USERNAME": "admin",
        "NETGEAR_PASSWORD": "your_modem_password"
      }
    }
  }
}
```

### 3. Antigravity IDE
Add to `~/.gemini/config/mcp_config.json`:

```json
{
  "mcpServers": {
    "netgear-genie": {
      "command": "python3",
      "args": ["-m", "mcp_netgear_genie.server"],
      "env": {
        "NETGEAR_HOST": "http://192.168.100.1",
        "NETGEAR_USERNAME": "admin",
        "NETGEAR_PASSWORD": "your_modem_password"
      }
    }
  }
}
```

---

## Remote Docker & SSE Gateway Deployment

You can host `mcp-netgear-genie` centrally on a NAS (Synology, Unraid, TrueNAS) or server using [Supergateway](https://github.com/supercorp-ai/supergateway) for network-wide access via Streamable HTTP / Server-Sent Events (SSE).

### `docker-compose.yml`
```yaml
version: '3.9'

services:
  mcp-netgear-genie:
    image: ghcr.io/supercorp-ai/supergateway:latest
    container_name: mcp-netgear-genie
    restart: unless-stopped
    entrypoint:
      - "sh"
      - "-c"
      - |
        which python3 >/dev/null 2>&1 || apk add --no-cache python3 py3-pip git
        pip list | grep -q mcp-netgear-genie || pip install --break-system-packages "git+https://github.com/FrankXLT/mcp-netgear-genie.git"
        exec node /usr/local/bin/supergateway --port 8000 --cors --outputTransport streamableHttp --streamableHttpPath /sse --stateful --stdio 'python3 -m mcp_netgear_genie.server'
    environment:
      - NETGEAR_HOST=http://192.168.100.1
      - NETGEAR_USERNAME=admin
      - NETGEAR_PASSWORD=your_modem_password
    ports:
      - "8000:8000"
```

Once running, AI clients can connect over SSE:
```
http://<your-server-ip>:8000/sse
```

---

## Standalone CLI Usage

`mcp-netgear-genie` includes a full CLI for quick checks and scripting:

```bash
# Display modem hardware info
mcp-netgear-genie info

# Display active DOCSIS bonded channels & startup state
mcp-netgear-genie status

# Display automated RF health evaluation and recommendations
mcp-netgear-genie health

# View recent event logs filtered by priority
mcp-netgear-genie logs --priority Warning --limit 10

# Output raw JSON for scripts or piping to jq
mcp-netgear-genie status --json | jq '.downstream_channels[0]'
```

---

## MCP Tools Reference

| Tool Name | Parameters | Default Format | Description |
| :--- | :--- | :---: | :--- |
| `get_dashboard_summary` | `format` (`table`\|`json`\|`both`) | `table` | **Consolidated Executive Overview**: Returns modem hardware status, RF power span, OFDM channels, and event log breakdown in a single call. |
| `get_modem_info` | `format` (`table`\|`json`\|`both`) | `table` | Returns model name, hardware revision, firmware version, serial number, MAC address, certificate state, and uptime. |
| `get_cable_status` | `active_only` (bool), `format` | `table` | Returns bonded downstream channels (1-32), upstream channels (1-8), OFDM channels, and the 6-step startup procedure. |
| `get_signal_health` | `format` (`table`\|`json`\|`both`) | `table` | Evaluates RF line health, flags out-of-spec power/SNR, counts uncorrectable codewords, and provides remediation advice. |
| `get_event_logs` | `min_priority` (str), `limit` (int), `format` | `table` | Scrapes and decomposes DOCSIS event logs, extracting clean error messages, CMTS MACs, and severity breakdowns. |
| `clear_event_logs` | `confirm` (bool = False) | `json` | Clears the cable modem internal event log (requires `confirm=True`). |
| `reboot_modem` | `confirm` (bool = False) | `json` | Initiates a software reboot of the cable modem (requires `confirm=True`). |

### Resources Exposed
- `netgear://modem/info`: Static hardware and firmware identity.
- `netgear://modem/cable-status`: Live DOCSIS connection and channel status.
- `netgear://modem/event-logs`: Recent DOCSIS event logs.

---

## Configuration Reference

| Environment Variable | Default | Description |
| :--- | :--- | :--- |
| `NETGEAR_HOST` | `http://192.168.100.1` | Modem management URL or hostname (e.g. `http://modem.lan`). |
| `NETGEAR_USERNAME` | `admin` | Web administrative username. |
| `NETGEAR_PASSWORD` | `password` | Web administrative password. |
| `NETGEAR_TIMEOUT` | `10.0` | HTTP request timeout in seconds. |
| `NETGEAR_VERIFY_SSL`| `false` | SSL certificate verification flag. |
| `NETGEAR_PORT` | `8000` | Port for SSE gateway deployments. |

---

## DOCSIS RF Signal Reference Guide

The diagnostic engine evaluates your physical RF line using CableLabs and DOCSIS 3.0 / 3.1 standards:

| Metric | Optimal Range | Acceptable Range | Critical / Warning Risk |
| :--- | :---: | :---: | :--- |
| **Downstream Power (QAM)** | `-7.0` to `+7.0 dBmV` | `-10.0` to `+10.0 dBmV` | `> +10 dBmV` (hot/overdriving, clipping)<br>`< -10 dBmV` (weak signal, packet loss) |
| **Downstream SNR / MER** | `≥ 35.0 dB` | `≥ 33.0 dB` | `< 30 dB` (severe noise, uncorrectables) |
| **OFDM Power (3.1)** | `-7.0` to `+7.0 dBmV` | `-10.0` to `+10.0 dBmV` | `> +10 dBmV` or `< -10 dBmV` |
| **Upstream Power (ATDMA)**| `38.0` to `48.0 dBmV` | `35.0` to `51.0 dBmV` | `> 51 dBmV` (risk of T3 timeouts and drops)<br>`< 35 dBmV` (sub-optimal SNR at CMTS) |
| **Uncorrectable Codewords**| `0` | `< 100` | Elevated counts indicate damaged coax, loose fittings, or failing splitters. |

---

## Network Topology & DNS Setup (`modem.lan`)

Cable modems respond on `192.168.100.1` across their internal management interface. To map a clean local hostname like `http://modem.lan`:

### Firewalla
1. Open the **Firewalla App**.
2. Navigate to **Network** -> **DNS Service** -> **Custom DNS Rules**.
3. Tap **Add Rule**:
   - **Domain**: `modem.lan`
   - **IP Address**: `192.168.100.1`
4. Save and configure `NETGEAR_HOST=http://modem.lan`.

### Pi-hole / pfSense / OPNsense / dnsmasq
Add an `A` record or static DNS host override:
```text
address=/modem.lan/192.168.100.1
```

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details on code style, testing, and PR submissions.
