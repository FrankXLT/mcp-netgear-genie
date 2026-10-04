"""HTTP Web Scraping Client for Netgear Genie Cable Modems."""

import re
import logging
from typing import Dict, List, Optional, Tuple, Any
import xml.etree.ElementTree as ET

import httpx
from bs4 import BeautifulSoup

from .config import NetgearConfig
from .models import (
    ModemInfoResponse,
    CableStatusResponse,
    StartupProcedureItem,
    DownstreamChannel,
    UpstreamChannel,
    OFDMChannel,
    OFDMAChannel,
    EventLogEntry,
    EventLogResponse,
    DashboardSummaryResponse,
    ActionResponse,
)

logger = logging.getLogger(__name__)


def parse_uptime(raw_uptime: str) -> Tuple[int, str]:
    """Convert raw uptime (e.g. '484:35:10' or '21 days 02:40:02') into (seconds, display_str)."""
    if not raw_uptime or raw_uptime == "Unknown":
        return 0, "Unknown"

    raw_uptime = raw_uptime.strip()

    # Case 1: HH:MM:SS format (e.g. 484:35:10)
    if ":" in raw_uptime and "day" not in raw_uptime.lower():
        parts = raw_uptime.split(":")
        if len(parts) == 3:
            try:
                hours = int(parts[0])
                mins = int(parts[1])
                secs = int(parts[2])
                total_secs = hours * 3600 + mins * 60 + secs
                days = hours // 24
                rem_hours = hours % 24

                parts_str = []
                if days > 0:
                    parts_str.append(f"{days} day{'s' if days != 1 else ''}")
                if rem_hours > 0 or days > 0:
                    parts_str.append(f"{rem_hours} hr{'s' if rem_hours != 1 else ''}")
                parts_str.append(f"{mins} min{'s' if mins != 1 else ''}")
                return total_secs, ", ".join(parts_str)
            except ValueError:
                pass

    # Case 2: '21 days 02:40:02' format
    m = re.search(r"(\d+)\s+day[s]?\s+(\d+):(\d+):(\d+)", raw_uptime, re.IGNORECASE)
    if m:
        days, hours, mins, secs = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        total_secs = days * 86400 + hours * 3600 + mins * 60 + secs
        return total_secs, f"{days} days, {hours} hrs, {mins} mins"

    return 0, raw_uptime

# Severity mapping for DOCSIS MIB levels
PRIORITY_MAP = {
    1: "Emergency (1)",
    2: "Alert (2)",
    3: "Critical (3)",
    4: "Error (4)",
    5: "Warning (5)",
    6: "Notice (6)",
    7: "Information (7)",
    8: "Debug (8)",
}

PRIORITY_NAME_TO_LEVEL = {
    "emergency": 1,
    "alert": 2,
    "critical": 3,
    "error": 4,
    "warning": 5,
    "notice": 6,
    "info": 7,
    "information": 7,
    "debug": 8,
}


class NetgearGenieClient:
    """Session-managed scraper for Netgear Genie DOCSIS web interface."""

    def __init__(self, config: Optional[NetgearConfig] = None):
        self.config = config or NetgearConfig()
        # Explicitly disable proxy to prevent sandbox / enterprise proxy interception of 192.168.100.1
        self._client = httpx.AsyncClient(
            timeout=self.config.timeout,
            verify=self.config.verify_ssl,
            trust_env=False,
            follow_redirects=False,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )
        self._session_id: Optional[str] = None
        self._web_token: Optional[str] = None

    async def close(self):
        """Close underlying HTTP client connection."""
        await self._client.aclose()

    async def login(self) -> bool:
        """
        Executes the Netgear Genie authentication flow:
        1. GET /GenieLogin.asp -> extract hidden webToken
        2. POST /goform/GenieLogin with credentials and webToken (allow_redirects=False)
        3. GET /Index.asp or /GenieIndex.asp to acquire SessionID cookie
        """
        logger.info(f"Authenticating with Netgear Genie at {self.config.host}...")

        # Step 1: Fetch login page to extract dynamic webToken
        login_url = self.config.get_url("GenieLogin.asp")
        try:
            resp = await self._client.get(login_url)
        except Exception as e:
            logger.error(f"Failed to reach login page {login_url}: {e}")
            raise ConnectionError(f"Could not connect to modem at {login_url}: {e}")

        # Extract webToken value: <input type="hidden" name="webToken" value=1641040522 />
        token_match = re.search(r'<input\s+[^>]*name=["\']webToken["\'][^>]*value=["\']?([0-9]+)["\']?', resp.text, re.IGNORECASE)
        if not token_match:
            # Fallback regex if value precedes name
            token_match = re.search(r'<input\s+[^>]*value=["\']?([0-9]+)["\']?[^>]*name=["\']webToken["\']', resp.text, re.IGNORECASE)

        if not token_match:
            logger.warning("Could not find webToken in GenieLogin.asp. Proceeding without webToken.")
            web_token = ""
        else:
            web_token = token_match.group(1)

        self._web_token = web_token

        # Step 2: POST credentials to /goform/GenieLogin
        post_url = self.config.get_url("goform/GenieLogin")
        payload = {
            "loginUsername": self.config.username,
            "loginPassword": self.config.password,
            "login": "1",
            "webToken": web_token,
        }

        try:
            post_resp = await self._client.post(
                post_url,
                data=payload,
                headers={"Referer": login_url}
            )
        except httpx.RemoteProtocolError:
            # Netgear embedded web server often slams socket shut after sending 302
            logger.debug("Socket closed immediately after POST (normal Netgear CM behavior).")

        # Step 3: GET Index.asp / GenieIndex.asp to retrieve session cookies
        index_url = self.config.get_url("GenieIndex.asp")
        resp_index = await self._client.get(index_url)

        # Check for SessionID in response cookies or client cookie jar
        self._session_id = self._client.cookies.get("SessionID") or resp_index.cookies.get("SessionID")
        logger.info(f"Authentication complete. SessionID: {'Acquired' if self._session_id else 'None'}")
        return True

    async def _authenticated_get(self, endpoint: str) -> httpx.Response:
        """Helper to execute an authenticated GET with auto-relogin on session timeout."""
        url = self.config.get_url(endpoint)
        resp = await self._client.get(url)

        # Detect session expiration / redirect to login page
        if resp.status_code in (302, 401, 403) or "GenieLogin.asp" in resp.text:
            logger.info("Session expired or unauthenticated. Re-authenticating...")
            await self.login()
            resp = await self._client.get(url)

        return resp

    async def get_modem_info(self) -> ModemInfoResponse:
        """Scrapes hardware revision, firmware version, serial number, and MAC address."""
        info = ModemInfoResponse()

        # Step 1: Check RouterStatus.asp which holds Netgear tagValueList (CM1000 standard)
        try:
            r_resp = await self._authenticated_get("RouterStatus.asp")
            tag_match = re.search(r"var\s+tagValueList\s*=\s*'([^']+)'", r_resp.text)
            if tag_match:
                parts = tag_match.group(1).split("|")
                if len(parts) > 0 and parts[0]:
                    info.hardware_version = parts[0].strip()
                if len(parts) > 1 and parts[1]:
                    info.firmware_version = parts[1].strip()
                if len(parts) > 2 and parts[2]:
                    info.serial_number = parts[2].strip()
                if len(parts) > 3 and parts[3]:
                    info.certificate_status = parts[3].strip()
                if len(parts) > 4 and parts[4]:
                    info.mac_address = parts[4].strip()
        except Exception as e:
            logger.debug(f"RouterStatus.asp query failed: {e}")

        # Step 2: Fetch DocsisStatus.asp for System Up Time
        try:
            d_resp = await self._authenticated_get("DocsisStatus.asp")
            d_html = d_resp.text
            up_match = re.search(r"System\s+Up\s*Time:(?:&nbsp;|\s*)</b>\s*([0-9:]+)", d_html, re.IGNORECASE)
            if up_match:
                info.system_uptime = up_match.group(1).strip()
        except Exception as e:
            logger.debug(f"DocsisStatus.asp query for uptime failed: {e}")

        # Step 3: Fallback parsing across GenieIndex.asp or ModemStatus.asp
        if info.hardware_version == "Unknown" or info.serial_number == "Unknown" or info.firmware_version == "Unknown":
            try:
                resp = await self._authenticated_get("GenieIndex.asp")
                html = resp.text

                fw_match = re.search(r"Firmware\s+Version[:\s]*([Vv0-9\._]+)", html, re.IGNORECASE)
                if fw_match and info.firmware_version == "Unknown":
                    info.firmware_version = fw_match.group(1).strip()

                hw_match = re.search(r"Hardware\s+Version[:\s]*([0-9\._]+)", html, re.IGNORECASE)
                if hw_match and info.hardware_version == "Unknown":
                    info.hardware_version = hw_match.group(1).strip()

                sn_match = re.search(r"Serial\s+Number[:\s]*([A-Za-z0-9]+)", html, re.IGNORECASE)
                if sn_match and info.serial_number == "Unknown":
                    info.serial_number = sn_match.group(1).strip()

                mac_match = re.search(r"(?:CM\s+MAC|MAC\s+Address)[:\s]*([0-9A-Fa-f:]{17}|[0-9A-Fa-f]{12})", html, re.IGNORECASE)
                if mac_match and info.mac_address == "Unknown":
                    info.mac_address = mac_match.group(1).strip()
            except Exception:
                pass

        # Populate human-readable uptime
        info.system_uptime_seconds, info.system_uptime_display = parse_uptime(info.system_uptime)
        return info

    async def get_cable_status(self, active_only: bool = True) -> CableStatusResponse:
        """Scrapes DocsisStatus.asp for downstream, upstream, OFDM, and OFDMA channel data."""
        resp = await self._authenticated_get("DocsisStatus.asp")
        html = resp.text

        response = CableStatusResponse()

        # Extract Starting Frequency
        freq_m = (
            re.search(r"name=[\"']Startupfreq[\"'][^>]*value=[\"'](\d+)[\"']", html, re.IGNORECASE)
            or re.search(r"value=[\"'](\d+)[\"'][^>]*name=[\"']Startupfreq[\"']", html, re.IGNORECASE)
            or re.search(r"Starting\s+Frequency[:\s]*(\d+)", html, re.IGNORECASE)
        )
        if freq_m:
            response.starting_frequency_hz = int(freq_m.group(1))
            response.starting_frequency_mhz = round(response.starting_frequency_hz / 1_000_000, 2)

        # Extract system uptime and current time
        uptime_match = re.search(r"System\s+Up\s*Time:(?:&nbsp;|\s*)</b>\s*([0-9:]+)", html, re.IGNORECASE) or re.search(r"System\s+Up\s*Time[:\s]*([0-9:]+)", html, re.IGNORECASE)
        if uptime_match:
            response.system_uptime = uptime_match.group(1).strip()
            response.system_uptime_seconds, response.system_uptime_display = parse_uptime(response.system_uptime)

        time_match = re.search(r"Current\s+System\s+Time[:\s]*([^\n<]+)", html, re.IGNORECASE)
        if time_match:
            response.current_time = time_match.group(1).strip()

        # Strategy 1: Check for embedded XML tables in JavaScript
        xml_matches = re.findall(r"var\s+xmlFormat\s*=\s*'([^']+)'", html)
        if xml_matches:
            for xml_str in xml_matches:
                self._parse_docsis_xml(xml_str, response, active_only=active_only)

        # Strategy 2: If XML didn't populate channels, parse HTML tables using BeautifulSoup
        if not response.downstream_channels and not response.upstream_channels:
            self._parse_docsis_html_tables(html, response, active_only=active_only)

        response.total_locked_downstream = len([c for c in response.downstream_channels if c.lock_status.lower() == "locked"])
        response.total_locked_upstream = len([c for c in response.upstream_channels if c.lock_status.lower() == "locked"])
        response.total_locked_ofdm = len([c for c in response.ofdm_channels if c.lock_status.lower() == "locked"])
        response.total_locked_ofdma = len([c for c in response.ofdma_channels if c.lock_status.lower() == "locked"])

        return response

    def _parse_docsis_xml(self, xml_str: str, response: CableStatusResponse, active_only: bool = True):
        """Parses embedded XML data structures used in some Netgear firmware builds."""
        try:
            root = ET.fromstring(xml_str)
            # Downstream channel table
            for tr in root.findall(".//docsIfDownstreamChannelTable/tr") or root.findall(".//downstream/tr"):
                cells = {child.tag.lower(): (child.text or "").strip() for child in tr}
                if "channel" in cells or "docsifdownstreamchannelid" in cells:
                    freq = int(cells.get("frequency", "0").replace("Hz", "").strip() or 0)
                    lock = cells.get("lockstatus", cells.get("lock", "Locked"))
                    if active_only and (lock.lower() in ("not locked", "unknown") or freq == 0):
                        continue

                    response.downstream_channels.append(DownstreamChannel(
                        channel=int(cells.get("channel", len(response.downstream_channels) + 1)),
                        lock_status=lock,
                        modulation=cells.get("modulation", "QAM256"),
                        channel_id=int(cells.get("channelid", cells.get("docsifdownstreamchannelid", 0))),
                        frequency_hz=freq,
                        frequency_mhz=round(freq / 1_000_000, 2),
                        power_dbmv=float(re.search(r"[-+]?\d*\.?\d+", cells.get("power", "0")).group() if re.search(r"[-+]?\d*\.?\d+", cells.get("power", "0")) else 0),
                        snr_mer_db=float(m.group() if (m := re.search(r"[-+]?\d*\.?\d+", cells.get("snr", cells.get("mer", "0")))) else 0.0),
                        unerrored_codewords=int(cells.get("unerroredcodewords", 0)),
                        correctable_codewords=int(cells.get("correctablecodewords", 0)),
                        uncorrectable_codewords=int(cells.get("uncorrectablecodewords", 0)),
                    ))
        except Exception as e:
            logger.debug(f"XML parse fallback: {e}")

    def _parse_docsis_html_tables(self, html: str, response: CableStatusResponse, active_only: bool = True):
        """Parses standard HTML tables from DocsisStatus.asp matching CM1000 layout."""
        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table")

        for table in tables:
            # Process only innermost leaf tables (skip outer containers)
            if table.find("table") is not None:
                continue

            headers = [th.get_text(strip=True).lower() for th in table.find_all(["th", "td"])[:12]]
            header_text = " ".join(headers)

            # Check if this is the Startup Procedure table
            if ("startup procedure" in header_text or "connectivity state" in header_text or "acquire downstream channel" in header_text) and "bonded channels" not in header_text:
                seen_procedures = set()
                for row in table.find_all("tr")[1:]:
                    cols = [td.get_text(strip=True) for td in row.find_all("td")]
                    if len(cols) >= 2 and cols[0] and cols[0].lower() != "procedure":
                        if cols[0] not in seen_procedures:
                            seen_procedures.add(cols[0])
                            response.startup_procedure.append(StartupProcedureItem(
                                procedure=cols[0],
                                status=cols[1],
                                comment=cols[2] if len(cols) > 2 else ""
                            ))

            # Check if this is Downstream OFDM Channels table (check OFDM before standard downstream)
            elif "ofdm" in header_text or "subcarrier" in header_text:
                for row in table.find_all("tr")[1:]:
                    cols = [td.get_text(strip=True) for td in row.find_all("td")]
                    if len(cols) >= 8:
                        try:
                            ch_idx = int(cols[0])
                            lock = cols[1]
                            if active_only and lock.lower() in ("not locked", "unknown"):
                                continue
                            mod_profile = cols[2]
                            ch_id = int(cols[3])
                            freq_hz = int(re.sub(r"[^\d]", "", cols[4]) or 0)
                            pwr = float(re.search(r"[-+]?\d*\.?\d+", cols[5]).group())
                            snr = float(re.search(r"[-+]?\d*\.?\d+", cols[6]).group())
                            subcarrier_range = cols[7] if len(cols) > 7 else ""
                            unerrored = int(re.sub(r"[^\d]", "", cols[8]) or 0) if len(cols) > 8 else 0
                            correctable = int(re.sub(r"[^\d]", "", cols[9]) or 0) if len(cols) > 9 else 0
                            uncorrectable = int(re.sub(r"[^\d]", "", cols[10]) or 0) if len(cols) > 10 else 0

                            response.ofdm_channels.append(OFDMChannel(
                                channel=ch_idx,
                                lock_status=lock,
                                modulation_profile=mod_profile,
                                channel_id=ch_id,
                                frequency_hz=freq_hz,
                                frequency_mhz=round(freq_hz / 1_000_000, 2),
                                power_dbmv=pwr,
                                snr_mer_db=snr,
                                active_subcarrier_range=subcarrier_range,
                                unerrored_codewords=unerrored,
                                correctable_codewords=correctable,
                                uncorrectable_codewords=uncorrectable
                            ))
                        except (ValueError, AttributeError):
                            continue

            # Check if this is Downstream Bonded Channels table
            elif "unerrored" in header_text or ("snr" in header_text and "modulation" in header_text):
                for row in table.find_all("tr")[1:]:
                    cols = [td.get_text(strip=True) for td in row.find_all("td")]
                    if len(cols) >= 9:
                        try:
                            ch_idx = int(cols[0])
                            lock = cols[1]
                            freq_hz = int(re.sub(r"[^\d]", "", cols[4]) or 0)
                            if active_only and (lock.lower() in ("not locked", "unknown") or freq_hz == 0):
                                continue

                            mod = cols[2]
                            ch_id = int(cols[3])
                            pwr = float(re.search(r"[-+]?\d*\.?\d+", cols[5]).group())
                            snr = float(re.search(r"[-+]?\d*\.?\d+", cols[6]).group())
                            unerrored = int(re.sub(r"[^\d]", "", cols[7]) or 0)
                            correctable = int(re.sub(r"[^\d]", "", cols[8]) or 0)
                            uncorrectable = int(re.sub(r"[^\d]", "", cols[9]) or 0) if len(cols) > 9 else 0

                            response.downstream_channels.append(DownstreamChannel(
                                channel=ch_idx,
                                lock_status=lock,
                                modulation=mod,
                                channel_id=ch_id,
                                frequency_hz=freq_hz,
                                frequency_mhz=round(freq_hz / 1_000_000, 2),
                                power_dbmv=pwr,
                                snr_mer_db=snr,
                                unerrored_codewords=unerrored,
                                correctable_codewords=correctable,
                                uncorrectable_codewords=uncorrectable
                            ))
                        except (ValueError, AttributeError):
                            continue

            # Check if this is Upstream Bonded Channels table (has modulation + channel id, but no snr/unerrored)
            elif "channel id" in header_text and "power" in header_text and "snr" not in header_text and "unerrored" not in header_text and "ofdm" not in header_text:
                for row in table.find_all("tr")[1:]:
                    cols = [td.get_text(strip=True) for td in row.find_all("td")]
                    if len(cols) >= 6:
                        try:
                            ch_idx = int(cols[0])
                            lock = cols[1]
                            freq_hz = int(re.sub(r"[^\d]", "", cols[4]) or 0)
                            if active_only and (lock.lower() in ("not locked", "unknown") or freq_hz == 0):
                                continue

                            mod = cols[2]
                            ch_id = int(cols[3])
                            pwr = float(re.search(r"[-+]?\d*\.?\d+", cols[5]).group())

                            response.upstream_channels.append(UpstreamChannel(
                                channel=ch_idx,
                                lock_status=lock,
                                modulation=mod,
                                channel_id=ch_id,
                                frequency_hz=freq_hz,
                                frequency_mhz=round(freq_hz / 1_000_000, 2),
                                power_dbmv=pwr
                            ))
                        except (ValueError, AttributeError):
                            continue

            # Check if this is Upstream OFDMA Channels table
            elif "upstream ofdma" in header_text:
                for row in table.find_all("tr")[1:]:
                    cols = [td.get_text(strip=True) for td in row.find_all("td")]
                    if len(cols) >= 5:
                        try:
                            ch_idx = int(cols[0])
                            lock = cols[1]
                            if active_only and lock.lower() in ("not locked", "unknown"):
                                continue
                            mod_profile = cols[2]
                            ch_id = int(cols[3])
                            freq_hz = int(re.sub(r"[^\d]", "", cols[4]) or 0)
                            pwr = float(re.search(r"[-+]?\d*\.?\d+", cols[5]).group()) if len(cols) > 5 else 0.0
                            subcarrier_range = cols[6] if len(cols) > 6 else ""

                            response.ofdma_channels.append(OFDMAChannel(
                                channel=ch_idx,
                                lock_status=lock,
                                modulation_profile=mod_profile,
                                channel_id=ch_id,
                                frequency_hz=freq_hz,
                                frequency_mhz=round(freq_hz / 1_000_000, 2),
                                power_dbmv=pwr,
                                active_subcarrier_range=subcarrier_range
                            ))
                        except (ValueError, AttributeError):
                            continue

    async def get_event_logs(
        self,
        min_priority: Optional[str] = None,
        limit: int = 50,
        keyword: Optional[str] = None
    ) -> EventLogResponse:
        """Scrapes EventLog.asp and parses the embedded XML/HTML log entries."""
        resp = await self._authenticated_get("EventLog.asp")
        html = resp.text

        entries: List[EventLogEntry] = []

        # Step 1: Look for embedded XML in JavaScript: var xmlFormat = '<docsDevEventTable><tr>...'
        xml_matches = re.findall(r"var\s+xmlFormat\s*=\s*'([^']+)'", html)
        if xml_matches:
            try:
                xml_str = xml_matches[0]
                root = ET.fromstring(xml_str)
                for tr in root.findall(".//tr"):
                    data = {}
                    for child in tr:
                        tag = child.tag
                        val = (child.text or "").strip()
                        data[tag] = val

                    # Extract fields matching reference Gist
                    idx_str = data.get("docsDevEvIndex", "0")
                    idx = int(idx_str) if idx_str.isdigit() else len(entries) + 1
                    first_time = data.get("docsDevEvFirstTime", "")
                    last_time = data.get("docsDevEvLastTime", "")
                    timestamp = last_time or first_time or "Unknown"

                    level_val = int(data.get("docsDevEvLevel", "6")) if data.get("docsDevEvLevel", "").isdigit() else 6
                    priority_label = PRIORITY_MAP.get(level_val, f"Level {level_val}")
                    event_id = data.get("docsDevEvId", "0")
                    counts = int(data.get("docsDevEvCounts", "1")) if data.get("docsDevEvCounts", "").isdigit() else 1
                    description = data.get("docsDevEvText", "")

                    # Decompose DOCSIS MIB string
                    cm_mac = (m.group(1).lower()) if (m := re.search(r"CM-MAC=([0-9A-Fa-f:]{17}|[0-9A-Fa-f]{12})", description, re.IGNORECASE)) else None
                    cmts_mac = (m.group(1).lower()) if (m := re.search(r"CMTS-MAC=([0-9A-Fa-f:]{17}|[0-9A-Fa-f]{12})", description, re.IGNORECASE)) else None
                    docsis_ver = (m.group(1)) if (m := re.search(r"CM-VER=([0-9\.]+)", description, re.IGNORECASE)) else None
                    qos_prof = (m.group(1)) if (m := re.search(r"CM-QOS=([0-9\.]+)", description, re.IGNORECASE)) else None
                    clean_msg = re.sub(r";\s*CM-[^;]+=[^;]+", "", description, flags=re.IGNORECASE)
                    clean_msg = re.sub(r";\s*CMTS-[^;]+=[^;]+", "", clean_msg, flags=re.IGNORECASE).strip("; ")

                    entries.append(EventLogEntry(
                        index=idx,
                        timestamp=timestamp,
                        priority=priority_label,
                        priority_level=level_val,
                        event_id=event_id,
                        counts=counts,
                        description=description,
                        clean_message=clean_msg,
                        cm_mac=cm_mac,
                        cmts_mac=cmts_mac,
                        docsis_version=docsis_ver,
                        qos_profile=qos_prof
                    ))
            except Exception as e:
                logger.warning(f"Error parsing EventLog XML: {e}")

        # Step 2: Fallback to HTML table parsing if XML is not present
        if not entries:
            soup = BeautifulSoup(html, "html.parser")
            table = soup.find("table")
            if table:
                for row in table.find_all("tr")[1:]:
                    cols = [td.get_text(strip=True) for td in row.find_all("td")]
                    if len(cols) >= 3:
                        time_str = cols[0]
                        prio_str = cols[1]
                        desc_str = cols[2]

                        # Extract priority number if present like "Critical (3)"
                        lvl_match = re.search(r"\((\d+)\)", prio_str)
                        lvl = int(lvl_match.group(1)) if lvl_match else 6

                        cm_mac = (m.group(1).lower()) if (m := re.search(r"CM-MAC=([0-9A-Fa-f:]{17}|[0-9A-Fa-f]{12})", desc_str, re.IGNORECASE)) else None
                        cmts_mac = (m.group(1).lower()) if (m := re.search(r"CMTS-MAC=([0-9A-Fa-f:]{17}|[0-9A-Fa-f]{12})", desc_str, re.IGNORECASE)) else None
                        docsis_ver = (m.group(1)) if (m := re.search(r"CM-VER=([0-9\.]+)", desc_str, re.IGNORECASE)) else None
                        qos_prof = (m.group(1)) if (m := re.search(r"CM-QOS=([0-9\.]+)", desc_str, re.IGNORECASE)) else None
                        clean_msg = re.sub(r";\s*CM-[^;]+=[^;]+", "", desc_str, flags=re.IGNORECASE)
                        clean_msg = re.sub(r";\s*CMTS-[^;]+=[^;]+", "", clean_msg, flags=re.IGNORECASE).strip("; ")

                        entries.append(EventLogEntry(
                            index=len(entries) + 1,
                            timestamp=time_str,
                            priority=prio_str,
                            priority_level=lvl,
                            event_id="",
                            counts=1,
                            description=desc_str,
                            clean_message=clean_msg,
                            cm_mac=cm_mac,
                            cmts_mac=cmts_mac,
                            docsis_version=docsis_ver,
                            qos_profile=qos_prof
                        ))

        total_available = len(entries)

        # Calculate priority breakdown across all available logs
        priority_breakdown: Dict[str, int] = {}
        for e in entries:
            priority_breakdown[e.priority] = priority_breakdown.get(e.priority, 0) + 1

        # Apply filtering
        filtered = entries

        # Filter by min_priority level
        if min_priority:
            min_lvl = PRIORITY_NAME_TO_LEVEL.get(min_priority.lower().strip())
            if min_lvl is not None:
                filtered = [e for e in filtered if e.priority_level <= min_lvl]

        # Filter by keyword
        if keyword:
            kw = keyword.lower().strip()
            filtered = [e for e in filtered if kw in e.description.lower()]

        # Apply limit
        sliced = filtered[:limit]

        return EventLogResponse(
            total_entries=total_available,
            returned_entries=len(sliced),
            priority_breakdown=priority_breakdown,
            logs=sliced
        )

    async def get_dashboard_summary(self) -> DashboardSummaryResponse:
        """Consolidated executive dashboard summary mirroring Netgear Genie UI."""
        from .diagnostics import evaluate_signal_health

        info = await self.get_modem_info()
        cable = await self.get_cable_status(active_only=True)
        health = evaluate_signal_health(cable)
        logs = await self.get_event_logs(limit=100)

        ds_summary = {
            "count": cable.total_locked_downstream,
            "power_min": health.downstream_power_min,
            "power_max": health.downstream_power_max,
            "power_avg": health.downstream_power_avg,
            "snr_avg": health.downstream_snr_avg,
            "uncorrectables": health.total_uncorrectable_errors,
        }
        us_summary = {
            "count": cable.total_locked_upstream,
            "power_min": health.upstream_power_min,
            "power_max": health.upstream_power_max,
            "power_avg": health.upstream_power_avg,
        }
        ofdm_summary = {
            "count": cable.total_locked_ofdm,
            "channels": [ch.channel_id for ch in cable.ofdm_channels],
            "power_avg": round(sum(ch.power_dbmv for ch in cable.ofdm_channels) / len(cable.ofdm_channels), 1) if cable.ofdm_channels else 0.0,
            "subcarrier_ranges": [ch.active_subcarrier_range for ch in cable.ofdm_channels if ch.active_subcarrier_range],
        }
        event_summary = {
            "total": logs.total_entries,
            "critical": logs.priority_breakdown.get("Critical (3)", 0) + logs.priority_breakdown.get("Critical", 0),
            "error": logs.priority_breakdown.get("Error (4)", 0) + logs.priority_breakdown.get("Error", 0),
            "warning": logs.priority_breakdown.get("Warning (5)", 0) + logs.priority_breakdown.get("Warning", 0),
            "notice": logs.priority_breakdown.get("Notice (6)", 0) + logs.priority_breakdown.get("Notice", 0),
        }

        return DashboardSummaryResponse(
            model=info.model,
            hardware_version=info.hardware_version,
            firmware_version=info.firmware_version,
            serial_number=info.serial_number,
            mac_address=info.mac_address,
            certificate_status=info.certificate_status,
            connection_status=info.connection_status,
            system_uptime=info.system_uptime,
            system_uptime_display=info.system_uptime_display,
            overall_rf_health=health.overall_status,
            health_recommendations=health.recommendations,
            downstream_summary=ds_summary,
            upstream_summary=us_summary,
            ofdm_summary=ofdm_summary,
            event_log_summary=event_summary,
        )

    async def clear_event_logs(self) -> ActionResponse:
        """Issues command to clear the modem event log."""
        url = self.config.get_url("goform/EventLog")
        try:
            resp = await self._client.post(url, data={"ClearLog": "1"})
            return ActionResponse(
                success=True,
                action="clear_event_logs",
                message="Successfully cleared modem event logs."
            )
        except Exception as e:
            return ActionResponse(
                success=False,
                action="clear_event_logs",
                message=f"Failed to clear event logs: {e}"
            )

    async def reboot_modem(self) -> ActionResponse:
        """Issues software reboot command to the modem."""
        url = self.config.get_url("goform/ModemStatus")
        try:
            resp = await self._client.post(url, data={"Reboot": "1"})
            return ActionResponse(
                success=True,
                action="reboot_modem",
                message="Reboot signal transmitted to modem. Device will restart within 60 seconds."
            )
        except Exception as e:
            return ActionResponse(
                success=False,
                action="reboot_modem",
                message=f"Failed to transmit reboot signal: {e}"
            )
