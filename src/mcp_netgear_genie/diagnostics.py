"""DOCSIS RF health analysis and diagnostics engine."""

from typing import List
from .models import (
    CableStatusResponse,
    SignalHealthSummary,
    ChannelEvaluation,
)


def evaluate_signal_health(status: CableStatusResponse) -> SignalHealthSummary:
    """
    Evaluates DOCSIS RF levels against CableLabs & industry standard specifications:
    - Downstream Power: Optimal [-7, +7] dBmV; Acceptable [-10, +10] dBmV.
    - Downstream SNR: Optimal >= 35 dB; Minimum 33 dB.
    - Upstream Power: Optimal [38, 48] dBmV; Acceptable [35, 51] dBmV.
    - Uncorrectable Errors: 0 is ideal; elevated counts indicate coax/splitter noise.
    """
    evaluations: List[ChannelEvaluation] = []
    recommendations: List[str] = []

    healthy_ds = 0
    total_ds = len(status.downstream_channels) + len(status.ofdm_channels)

    healthy_us = 0
    total_us = len(status.upstream_channels) + len(status.ofdma_channels)

    total_uncorrectables = 0

    # Evaluate standard downstream channels
    for ch in status.downstream_channels:
        issues = []
        ch_status = "GOOD"
        total_uncorrectables += ch.uncorrectable_codewords

        # Check power
        if ch.power_dbmv < -10.0 or ch.power_dbmv > 10.0:
            issues.append(f"Power out of acceptable spec: {ch.power_dbmv} dBmV (Spec: -10 to +10 dBmV)")
            ch_status = "CRITICAL"
        elif ch.power_dbmv < -7.0 or ch.power_dbmv > 7.0:
            issues.append(f"Power sub-optimal: {ch.power_dbmv} dBmV (Optimal: -7 to +7 dBmV)")
            if ch_status == "GOOD":
                ch_status = "WARNING"

        # Check SNR
        if ch.snr_mer_db < 30.0:
            issues.append(f"Critically low SNR/MER: {ch.snr_mer_db} dB (< 30 dB)")
            ch_status = "CRITICAL"
        elif ch.snr_mer_db < 33.0:
            issues.append(f"Low SNR/MER: {ch.snr_mer_db} dB (< 33 dB)")
            if ch_status == "GOOD":
                ch_status = "WARNING"

        # Check uncorrectables
        if ch.uncorrectable_codewords > 100:
            issues.append(f"Elevated uncorrectable codewords: {ch.uncorrectable_codewords}")
            if ch_status == "GOOD":
                ch_status = "WARNING"

        if ch_status == "GOOD":
            healthy_ds += 1

        evaluations.append(ChannelEvaluation(
            channel_id=ch.channel_id,
            channel_type="downstream",
            power_dbmv=ch.power_dbmv,
            snr_db=ch.snr_mer_db,
            uncorrectables=ch.uncorrectable_codewords,
            status=ch_status,
            issues=issues
        ))

    # Evaluate OFDM downstream channels
    for ch in status.ofdm_channels:
        issues = []
        ch_status = "GOOD"
        total_uncorrectables += ch.uncorrectable_codewords

        if ch.power_dbmv < -10.0 or ch.power_dbmv > 10.0:
            issues.append(f"OFDM power out of spec: {ch.power_dbmv} dBmV")
            ch_status = "CRITICAL"
        elif ch.power_dbmv < -7.0 or ch.power_dbmv > 7.0:
            issues.append(f"OFDM power sub-optimal: {ch.power_dbmv} dBmV")
            if ch_status == "GOOD":
                ch_status = "WARNING"

        if ch.snr_mer_db < 33.0:
            issues.append(f"OFDM SNR/MER low: {ch.snr_mer_db} dB (< 33 dB)")
            ch_status = "CRITICAL"

        if ch.uncorrectable_codewords > 500:
            issues.append(f"Elevated OFDM uncorrectables: {ch.uncorrectable_codewords}")
            if ch_status == "GOOD":
                ch_status = "WARNING"

        if ch_status == "GOOD":
            healthy_ds += 1

        evaluations.append(ChannelEvaluation(
            channel_id=ch.channel_id,
            channel_type="ofdm",
            power_dbmv=ch.power_dbmv,
            snr_db=ch.snr_mer_db,
            uncorrectables=ch.uncorrectable_codewords,
            status=ch_status,
            issues=issues
        ))

    # Evaluate standard upstream channels
    for ch in status.upstream_channels:
        issues = []
        ch_status = "GOOD"

        if ch.power_dbmv > 51.0:
            issues.append(f"Critically high upstream transmit power: {ch.power_dbmv} dBmV (> 51 dBmV, risk of T3/T4 drop)")
            ch_status = "CRITICAL"
        elif ch.power_dbmv > 48.0:
            issues.append(f"High upstream transmit power: {ch.power_dbmv} dBmV (> 48 dBmV)")
            ch_status = "WARNING"
        elif ch.power_dbmv < 35.0:
            issues.append(f"Low upstream transmit power: {ch.power_dbmv} dBmV (< 35 dBmV)")
            ch_status = "WARNING"

        if ch_status == "GOOD":
            healthy_us += 1

        evaluations.append(ChannelEvaluation(
            channel_id=ch.channel_id,
            channel_type="upstream",
            power_dbmv=ch.power_dbmv,
            snr_db=None,
            uncorrectables=0,
            status=ch_status,
            issues=issues
        ))

    # Calculate power and SNR statistics
    ds_powers = [ch.power_dbmv for ch in status.downstream_channels]
    ds_snrs = [ch.snr_mer_db for ch in status.downstream_channels if ch.snr_mer_db > 0]
    us_powers = [ch.power_dbmv for ch in status.upstream_channels if ch.power_dbmv > 0]

    ds_pwr_min = min(ds_powers) if ds_powers else 0.0
    ds_pwr_max = max(ds_powers) if ds_powers else 0.0
    ds_pwr_avg = round(sum(ds_powers) / len(ds_powers), 2) if ds_powers else 0.0
    ds_snr_avg = round(sum(ds_snrs) / len(ds_snrs), 2) if ds_snrs else 0.0

    us_pwr_min = min(us_powers) if us_powers else 0.0
    us_pwr_max = max(us_powers) if us_powers else 0.0
    us_pwr_avg = round(sum(us_powers) / len(us_powers), 2) if us_powers else 0.0

    # Synthesize overall status and recommendations
    critical_count = sum(1 for e in evaluations if e.status == "CRITICAL")
    warning_count = sum(1 for e in evaluations if e.status == "WARNING")

    if critical_count > 0:
        overall = "CRITICAL"
        recommendations.append("Immediate physical RF line inspection recommended. High risk of packet loss or disconnects.")
    elif warning_count > 0 or total_uncorrectables > 1000:
        overall = "ATTENTION_NEEDED"
    else:
        overall = "HEALTHY"
        recommendations.append("All DOCSIS RF channels are operating within optimal operating margins.")

    # High downstream power recommendation (e.g. +15 dBmV)
    high_ds = [e for e in evaluations if e.channel_type in ("downstream", "ofdm") and e.power_dbmv > 10.0]
    if high_ds:
        recommendations.append(
            f"Downstream power is hot/high (max {ds_pwr_max:+.1f} dBmV, ideal is -7 to +7 dBmV). "
            f"Adding an inline forward coax attenuator (-6 dB) or a 2-way splitter (-3.5 dB) will bring signal levels into optimal spec."
        )

    # High upstream power recommendation
    high_us = [e for e in evaluations if e.channel_type == "upstream" and e.power_dbmv > 48.0]
    if high_us:
        recommendations.append(
            "Upstream transmit power is high (>48 dBmV). Removing unnecessary coax splitters between the modem and the street drop can lower transmit power by 3.5-7 dB."
        )

    if total_uncorrectables > 0:
        recommendations.append(
            f"Detected {total_uncorrectables:,} total uncorrectable codewords. Check for loose coax connectors, damaged splitters, or moisture ingress."
        )

    return SignalHealthSummary(
        overall_status=overall,
        total_downstream=total_ds,
        healthy_downstream=healthy_ds,
        total_upstream=total_us,
        healthy_upstream=healthy_us,
        total_uncorrectable_errors=total_uncorrectables,
        downstream_power_min=ds_pwr_min,
        downstream_power_max=ds_pwr_max,
        downstream_power_avg=ds_pwr_avg,
        downstream_snr_avg=ds_snr_avg,
        upstream_power_min=us_pwr_min,
        upstream_power_max=us_pwr_max,
        upstream_power_avg=us_pwr_avg,
        recommendations=recommendations,
        channel_evaluations=evaluations
    )
