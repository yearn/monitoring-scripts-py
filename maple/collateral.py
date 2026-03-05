"""
Maple Finance syrupUSDC loan collateral monitoring.

Fetches collateral breakdown from the Maple Finance GraphQL API and calculates
a weighted risk score based on predefined asset risk ratings.

Alerts when the weighted risk score exceeds the configured threshold.
"""

import requests

from utils.formatting import format_usd
from utils.logging import get_logger
from utils.telegram import send_telegram_message

PROTOCOL = "maple"
logger = get_logger(PROTOCOL)

MAPLE_GRAPHQL_URL = "https://api.maple.finance/v2/graphql"
SYRUP_USDC_POOL_ID = "0x80ac24aa929eaf5013f6436cda2a7ba190f5cc0b"

# Asset risk scores from issue #147
# 1 = low risk, 2 = medium risk, 3 = high risk
ASSET_RISK_SCORES: dict[str, int] = {
    "BTC": 1,
    "XRP": 2,
    "USTB": 3,
    "jitoSOL": 2,
    "LBTC": 2,
    "HYPE": 2,
}

# Default risk score for unknown assets
DEFAULT_RISK_SCORE = 3

# Alert if weighted risk score exceeds this threshold
RISK_SCORE_THRESHOLD = 1.5

COLLATERAL_QUERY = (
    """
{
  poolV2S(where: {id: "%s"}) {
    id
    poolMeta {
      poolCollaterals {
        asset
        assetAmount
        assetDecimals
        assetValueUsd
      }
    }
  }
}
"""
    % SYRUP_USDC_POOL_ID
)


def fetch_collateral_data() -> list[dict]:
    """Fetch collateral data from Maple Finance GraphQL API.

    Returns:
        List of collateral dicts with asset, assetAmount, assetDecimals, assetValueUsd fields.

    Raises:
        ValueError: If the API response is malformed or pool not found.
        requests.RequestException: If the API request fails.
    """
    response = requests.post(
        MAPLE_GRAPHQL_URL,
        json={"query": COLLATERAL_QUERY},
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()
    if "errors" in data:
        raise ValueError(f"Maple GraphQL errors: {data['errors']}")

    pools = data.get("data", {}).get("poolV2S", [])
    if not pools:
        raise ValueError(f"Pool {SYRUP_USDC_POOL_ID} not found in Maple API response")

    return pools[0].get("poolMeta", {}).get("poolCollaterals", [])


def calculate_risk_score(collaterals: list[dict]) -> tuple[float, list[dict]]:
    """Calculate weighted average risk score from collateral data.

    Args:
        collaterals: List of collateral dicts from the Maple API.

    Returns:
        Tuple of (weighted_risk_score, active_collaterals) where active_collaterals
        contains only collaterals with non-zero USD value, enriched with risk info.
    """
    active_collaterals = []
    total_usd_value = 0.0
    weighted_risk_sum = 0.0

    for collateral in collaterals:
        usd_value = float(collateral.get("assetValueUsd", "0"))
        if usd_value <= 0:
            continue

        asset = collateral["asset"]
        risk_score = ASSET_RISK_SCORES.get(asset, DEFAULT_RISK_SCORE)

        # assetValueUsd is in cents (6 decimal USD), convert to dollars
        usd_value_dollars = usd_value / 1e6

        active_collaterals.append(
            {
                "asset": asset,
                "usd_value": usd_value_dollars,
                "risk_score": risk_score,
            }
        )

        total_usd_value += usd_value_dollars
        weighted_risk_sum += risk_score * usd_value_dollars

    if total_usd_value == 0:
        return 0.0, active_collaterals

    weighted_risk = weighted_risk_sum / total_usd_value
    return weighted_risk, active_collaterals


def check_collateral_risk() -> None:
    """Check loan collateral risk and alert if weighted risk score exceeds threshold."""
    collaterals = fetch_collateral_data()
    risk_score, active_collaterals = calculate_risk_score(collaterals)

    if not active_collaterals:
        logger.warning("No active collateral found for syrupUSDC pool")
        return

    total_usd = sum(c["usd_value"] for c in active_collaterals)

    # Log collateral breakdown
    breakdown_lines = []
    for c in sorted(active_collaterals, key=lambda x: x["usd_value"], reverse=True):
        pct = c["usd_value"] / total_usd * 100 if total_usd > 0 else 0
        risk_label = {1: "Low", 2: "Medium", 3: "High"}.get(c["risk_score"], "Unknown")
        breakdown_lines.append(
            f"  {c['asset']}: {format_usd(c['usd_value'])} ({pct:.1f}%) — risk: {c['risk_score']} ({risk_label})"
        )

    logger.info(
        "Collateral risk score: %.2f (threshold: %.2f) | Total: %s\n%s",
        risk_score,
        RISK_SCORE_THRESHOLD,
        format_usd(total_usd),
        "\n".join(breakdown_lines),
    )

    if risk_score > RISK_SCORE_THRESHOLD:
        collateral_lines = []
        for c in sorted(active_collaterals, key=lambda x: x["usd_value"], reverse=True):
            pct = c["usd_value"] / total_usd * 100 if total_usd > 0 else 0
            risk_label = {1: "Low", 2: "Medium", 3: "High"}.get(c["risk_score"], "Unknown")
            collateral_lines.append(
                f"• {c['asset']}: {format_usd(c['usd_value'])} ({pct:.1f}%) — Risk {c['risk_score']} ({risk_label})"
            )

        message = (
            f"🚨 *Maple syrupUSDC Collateral Risk Alert*\n"
            f"📊 Weighted risk score: {risk_score:.2f} (threshold: {RISK_SCORE_THRESHOLD:.1f})\n"
            f"💰 Total collateral: {format_usd(total_usd)}\n\n"
            f"*Collateral Breakdown:*\n" + "\n".join(collateral_lines) + "\n\n"
            "⚠️ High-risk collateral concentration detected\n"
            "🔗 [Pool Details](https://app.maple.finance/earn/details)"
        )
        send_telegram_message(message, PROTOCOL)

    # Also alert on unknown assets (not in our risk mapping)
    unknown_assets = [c for c in active_collaterals if c["asset"] not in ASSET_RISK_SCORES]
    if unknown_assets:
        unknown_lines = [f"• {c['asset']}: {format_usd(c['usd_value'])}" for c in unknown_assets]
        message = (
            "⚠️ *Maple syrupUSDC Unknown Collateral Asset*\n"
            "New collateral assets detected that are not in the risk mapping:\n"
            + "\n".join(unknown_lines)
            + "\n\nPlease update the risk scores in `maple/collateral.py`"
        )
        send_telegram_message(message, PROTOCOL)
