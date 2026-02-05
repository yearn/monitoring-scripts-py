#!/usr/bin/env python3
"""Monitor TimelockController CallScheduled events and send Telegram alerts."""

import argparse
import json
import logging
import os
import sys
import time
import urllib.request
from dataclasses import dataclass

from dotenv import load_dotenv

from utils.cache import cache_filename, get_last_value_for_key_from_file, write_last_value_to_file
from utils.chains import EXPLORER_URLS, Chain
from utils.telegram import send_telegram_message

load_dotenv()

ENVIO_GRAPHQL_URL = os.getenv("ENVIO_GRAPHQL_URL")
DEFAULT_LOG_LEVEL = os.getenv("TIMELOCK_ALERTS_LOG_LEVEL", "WARNING")
CACHE_KEY = "TIMELOCK_LAST_TS"


@dataclass(frozen=True)
class TimelockConfig:
    """Configuration for a monitored timelock contract."""

    address: str
    chain_id: int
    protocol: str
    label: str


# All monitored timelocks; address field must be lowercase
TIMELOCK_LIST: list[TimelockConfig] = [
    # Chain 1 - Mainnet
    TimelockConfig("0xd8236031d8279d82e615af2bfab5fc0127a329ab", 1, "CAP", "CAP TimelockController"),
    TimelockConfig("0x5d8a7dc9405f08f14541ba918c1bf7eb2dace556", 1, "RTOKEN", "ETH+ Timelock"),
    TimelockConfig("0x055e84e7fe8955e2781010b866f10ef6e1e77e59", 1, "LRT", "Lombard TimeLock"),
    TimelockConfig("0xe1f03b7b0ebf84e9b9f62a1db40f1efb8faa7d22", 1, "SILO", "Silo TimelockController"),
    TimelockConfig("0x81f6e9914136da1a1d3b1efd14f7e0761c3d4cc7", 1, "LRT", "Renzo(ezETH) TimelockController"),
    TimelockConfig("0x9f26d4c958fd811a1f59b01b86be7dffc9d20761", 1, "LRT", "EtherFi Timelock"),
    TimelockConfig("0x49bd9989e31ad35b0a62c20be86335196a3135b1", 1, "LRT", "KelpDAO(rsETH) Timelock"),
    # Chain 8453 - Base
    TimelockConfig("0xf817cb3092179083c48c014688d98b72fb61464f", 8453, "LRT", "superOETH Timelock"),
]

# Lookup by lowercase address
TIMELOCKS: dict[str, TimelockConfig] = {t.address: t for t in TIMELOCK_LIST}

_logger = logging.getLogger("timelock_alerts")


def http_json(url: str, method: str = "GET", body: dict | None = None, headers: dict | None = None) -> dict:
    """Make an HTTP request and return JSON response."""
    _logger.info("http_json %s %s", method, url)
    data = None
    req_headers: dict[str, str] = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
        _logger.info("http_json status=%s", resp.status)
        return payload


def gql_request(query: str, variables: dict) -> dict:
    """Execute a GraphQL query against the Envio indexer."""
    if not ENVIO_GRAPHQL_URL:
        raise RuntimeError(
            "ENVIO_GRAPHQL_URL is not set. Set it to the Envio GraphQL endpoint, "
            "e.g. export ENVIO_GRAPHQL_URL='https://.../graphql'."
        )
    _logger.info("gql_request")
    payload = {"query": query, "variables": variables}
    return http_json(ENVIO_GRAPHQL_URL, method="POST", body=payload)


def format_delay(seconds: int) -> str:
    """Convert delay in seconds to human-readable format."""
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    parts: list[str] = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 and days == 0:
        parts.append(f"{minutes}m")
    if not parts:
        return f"{seconds}s"
    return " ".join(parts)


def load_events(limit: int, since_ts: int) -> dict:
    """Fetch CallScheduled events from the Envio GraphQL API."""
    addresses = [t.address for t in TIMELOCK_LIST]
    _logger.info("load_events limit=%s since_ts=%s addresses=%s", limit, since_ts, len(addresses))
    query = """
    query GetCallScheduled($limit: Int!, $sinceTs: Int!, $addresses: [String!]!) {
      CallScheduled(
        where: {
          timelockAddress: { _in: $addresses }
          blockTimestamp: { _gt: $sinceTs }
        }
        order_by: { blockTimestamp: asc, blockNumber: asc, logIndex: asc }
        limit: $limit
      ) {
        id
        timelockAddress
        chainId
        blockNumber
        blockTimestamp
        transactionHash
        operationId
        index
        target
        value
        data
        predecessor
        delay
      }
    }
    """
    variables: dict = {"limit": limit, "sinceTs": since_ts, "addresses": addresses}
    return gql_request(query, variables)


def build_alert_message(events: list[dict], timelock_info: TimelockConfig) -> str:
    """Build a Telegram alert message for a group of CallScheduled events (same operationId)."""
    first = events[0]
    chain_id = int(first["chainId"])
    try:
        chain = Chain.from_chain_id(chain_id)
        chain_name = chain.network_name.capitalize()
    except ValueError:
        chain_name = f"Chain {chain_id}"
    explorer = EXPLORER_URLS.get(chain_id)
    tx_hash = first["transactionHash"]
    tx_url = f"{explorer}/tx/{tx_hash}" if explorer else None
    delay_seconds = int(first["delay"])
    timelock_address = first["timelockAddress"]
    timelock_url = f"{explorer}/address/{timelock_address}" if explorer else None

    lines: list[str] = [
        "⏰ *TIMELOCK: New Operation Scheduled*",
        f"🅿️ Protocol: {timelock_info.protocol}",
    ]
    if timelock_url:
        lines.append(f"📋 Timelock: [{timelock_info.label}]({timelock_url})")
    else:
        lines.append(f"📋 Timelock: {timelock_info.label}")
    lines.append(f"🔗 Chain: {chain_name}")
    lines.append(f"⏳ Delay: {format_delay(delay_seconds)}")

    for event in events:
        target = event["target"]
        target_url = f"{explorer}/address/{target}" if explorer else None
        value_wei = int(event["value"])
        data_hex = event.get("data", "0x")
        fn_selector = data_hex[:10] if len(data_hex) >= 10 else data_hex

        if len(events) > 1:
            lines.append(f"--- Call {int(event['index'])} ---")

        if target_url:
            lines.append(f"🎯 Target: [{target}]({target_url})")
        else:
            lines.append(f"🎯 Target: {target}")
        lines.append(f"📝 Function: `{fn_selector}`")
        if value_wei > 0:
            value_eth = value_wei / 1e18
            lines.append(f"💰 Value: {value_eth:.4f} ETH")

    if tx_url:
        lines.append(f"🔗 Tx: [{tx_hash}]({tx_url})")
    else:
        lines.append(f"🔗 Tx: {tx_hash}")

    return "\n".join(lines)


def process_events(events: list[dict], use_cache: bool) -> None:
    """Process CallScheduled events, group by operationId, and send alerts."""
    if not events:
        _logger.info("No new events to process")
        return

    # Group events by operationId (batch operations share the same operationId)
    operations: dict[str, list[dict]] = {}
    for event in events:
        op_id = event["operationId"]
        if op_id not in operations:
            operations[op_id] = []
        operations[op_id].append(event)

    _logger.info("Processing %s operations from %s events", len(operations), len(events))

    max_timestamp = 0
    for op_id, op_events in operations.items():
        # Sort by index within the operation
        op_events.sort(key=lambda e: int(e["index"]))

        timelock_addr = op_events[0]["timelockAddress"].lower()
        timelock_info = TIMELOCKS.get(timelock_addr)
        if not timelock_info:
            _logger.warning("Unknown timelock address: %s", timelock_addr)
            continue

        message = build_alert_message(op_events, timelock_info)
        send_telegram_message(message, timelock_info.protocol)

        # Track max timestamp
        for event in op_events:
            ts = int(event["blockTimestamp"])
            if ts > max_timestamp:
                max_timestamp = ts

    if use_cache and max_timestamp > 0:
        write_last_value_to_file(cache_filename, CACHE_KEY, str(max_timestamp))
        _logger.info("Updated cache: %s = %s", CACHE_KEY, max_timestamp)


def main() -> None:
    parser = argparse.ArgumentParser(description="Alert on TimelockController CallScheduled events.")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument(
        "--since-seconds",
        type=int,
        default=7200,
        help="Fallback lookback window in seconds when no cache exists (default: 2h)",
    )
    parser.add_argument("--no-cache", action="store_true", help="Disable caching of last processed timestamp")
    parser.add_argument(
        "--log-level",
        type=str,
        default=DEFAULT_LOG_LEVEL,
        help="Logging level (DEBUG, INFO, WARNING, ERROR).",
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=args.log_level.upper(),
        format="[%(name)s] %(levelname)s %(message)s",
        stream=sys.stderr,
    )

    use_cache = not args.no_cache

    # Determine the starting timestamp
    since_ts = 0
    if use_cache:
        cached_ts = get_last_value_for_key_from_file(cache_filename, CACHE_KEY)
        if cached_ts and str(cached_ts) != "0":
            since_ts = int(cached_ts)
            _logger.info("Using cached timestamp: %s", since_ts)

    if since_ts == 0:
        since_ts = int(time.time()) - args.since_seconds
        _logger.info("No cached timestamp, using fallback: %s", since_ts)

    _logger.info("Fetching CallScheduled events since timestamp %s", since_ts)

    response = load_events(args.limit, since_ts)
    if "errors" in response:
        _logger.error("GraphQL errors: %s", response["errors"])
        print(json.dumps({"error": response["errors"]}), file=sys.stderr)
        sys.exit(1)

    data = response.get("data", {})
    events = data.get("CallScheduled", [])
    _logger.info("Fetched %s CallScheduled events", len(events))

    process_events(events, use_cache)


if __name__ == "__main__":
    main()
