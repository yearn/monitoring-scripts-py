#!/usr/bin/env python3
import argparse
import json
import logging
import os
import sys
import time
import urllib.parse
import urllib.request
from decimal import Decimal, getcontext

getcontext().prec = 40

ENVIO_GRAPHQL_URL = os.getenv("ENVIO_GRAPHQL_URL")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")
COINGECKO_MIN_SECONDS_BETWEEN_CALLS = float(os.getenv("COINGECKO_MIN_SECONDS_BETWEEN_CALLS", "1.0"))
COINGECKO_MAX_RETRIES = int(os.getenv("COINGECKO_MAX_RETRIES", "4"))
COINGECKO_BACKOFF_BASE_SECONDS = float(os.getenv("COINGECKO_BACKOFF_BASE_SECONDS", "1.5"))
DEFAULT_LOG_LEVEL = os.getenv("ALERT_LARGE_FLOWS_LOG_LEVEL", "WARNING")
IGNORED_FROM_ADDRESS = "0x283132390ea87d6ecc20255b59ba94329ee17961"

VAULTS = {
    "0xbe53a109b494e5c9f97b9cd39fe969be68bf6204": {
        "symbol": "USDC",
        "decimals": 6,
        "chain_id": 1,
        "token_address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
    },
    "0x028ec7330ff87667b6dfb0d94b954c820195336c": {
        "symbol": "DAI",
        "decimals": 18,
        "chain_id": 1,
        "token_address": "0x6b175474e89094c44da98b954eedeac495271d0f",
    },
    "0x310b7ea7475a0b449cfd73be81522f1b88efafaa": {
        "symbol": "USDT",
        "decimals": 6,
        "chain_id": 1,
        "token_address": "0xdac17f958d2ee523a2206206994597c13d831ec7",
    },
    "0x182863131f9a4630ff9e27830d945b1413e347e8": {
        "symbol": "USDS",
        "decimals": 18,
        "chain_id": 1,
        "token_address": "0xdc035d45d973e3ec169d2276ddab16f1e407384f",
    },
    "0xbf319ddc2edc1eb6fdf9910e39b37be221c8805f": {
        "symbol": "CRVUSD",
        "decimals": 18,
        "chain_id": 1,
        "token_address": "0xf939e0a03fb07f59a73314e73794be0e57ac1b4e",
    },
    "0xc56413869c6cdf96496f2b1ef801fedbdfa7ddb0": {
        "symbol": "WETH",
        "decimals": 18,
        "chain_id": 1,
        "token_address": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
    },
    "0xb13cf163d916917d9cd6e836905ca5f12a1def4b": {
        "symbol": "USDC",
        "decimals": 6,
        "chain_id": 8453,
        "token_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
    },
    "0xc3bd0a2193c8f027b82dde3611d18589ef3f62a9": {
        "symbol": "USDC",
        "decimals": 6,
        "chain_id": 8453,
        "token_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
    },
    "0x4d81c7d534d703e0a0aecadf668c0e0253e1f1c3": {
        "symbol": "WETH",
        "decimals": 18,
        "chain_id": 8453,
        "token_address": "0x4200000000000000000000000000000000000006",
    },
    "0x25f32ec89ce7732a4e9f8f3340a09259f823b7d3": {
        "symbol": "cbBTC",
        "decimals": 8,
        "chain_id": 8453,
        "token_address": "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf",
    },
}

COINGECKO_PLATFORM = {
    1: "ethereum",
    8453: "base",
}

STABLES = {"USDC", "USDT", "DAI", "USDS", "CRVUSD"}

_price_cache: dict[tuple[int, str], tuple[float, Decimal]] = {}
_last_cg_call_ts = 0.0
_logger = logging.getLogger("alert_large_flows")


def http_json(url: str, method: str = "GET", body: dict | None = None, headers: dict | None = None):
    _logger.info("http_json %s %s", method, url)
    data = None
    req_headers = {"Accept": "application/json"}
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


def gql_request(query: str, variables: dict):
    if not ENVIO_GRAPHQL_URL:
        raise RuntimeError(
            "ENVIO_GRAPHQL_URL is not set. Set it to the Envio GraphQL endpoint, "
            "e.g. export ENVIO_GRAPHQL_URL='https://.../graphql'."
        )
    _logger.info("gql_request")
    payload = {"query": query, "variables": variables}
    return http_json(ENVIO_GRAPHQL_URL, method="POST", body=payload)


def format_units(value: str, decimals: int) -> Decimal:
    return Decimal(value) / (Decimal(10) ** Decimal(decimals))


def _coingecko_get_price_usd(chain_id: int, token_address: str) -> Decimal:
    global _last_cg_call_ts
    platform = COINGECKO_PLATFORM.get(chain_id)
    if not platform:
        raise RuntimeError(f"Unsupported chain for pricing: {chain_id}")
    _logger.info(
        "coingecko price request chain_id=%s token=%s",
        chain_id,
        token_address,
    )

    now = time.time()
    delta = now - _last_cg_call_ts
    if delta < COINGECKO_MIN_SECONDS_BETWEEN_CALLS:
        time.sleep(COINGECKO_MIN_SECONDS_BETWEEN_CALLS - delta)

    params = {
        "contract_addresses": token_address,
        "vs_currencies": "usd",
    }
    url = f"https://api.coingecko.com/api/v3/simple/token_price/{platform}?{urllib.parse.urlencode(params)}"
    headers = {}
    if COINGECKO_API_KEY:
        headers["x-cg-pro-api-key"] = COINGECKO_API_KEY

    data = http_json(url, headers=headers)
    _last_cg_call_ts = time.time()
    price = data.get(token_address.lower(), {}).get("usd")
    if price is None:
        raise RuntimeError(f"Missing price for {token_address} on {platform}")
    return Decimal(str(price))


def get_token_price_usd(chain_id: int, token_address: str, symbol: str) -> Decimal:
    if symbol in STABLES:
        return Decimal("1")

    cache_key = (chain_id, token_address.lower())
    cached = _price_cache.get(cache_key)
    if cached:
        cached_ts, cached_price = cached
        if time.time() - cached_ts < 60:
            return cached_price

    for attempt in range(COINGECKO_MAX_RETRIES):
        try:
            price = _coingecko_get_price_usd(chain_id, token_address)
            _price_cache[cache_key] = (time.time(), price)
            return price
        except urllib.error.HTTPError as exc:
            _logger.warning("coingecko HTTPError %s", exc.code)
            if exc.code == 429:
                backoff = COINGECKO_BACKOFF_BASE_SECONDS * (2 ** attempt)
                time.sleep(backoff)
                continue
            raise

    raise RuntimeError("CoinGecko rate limit exceeded; try again later or set COINGECKO_API_KEY.")


def load_events(limit: int, chain_ids: list[int], since_ts: int | None):
    _logger.info(
        "load_events limit=%s chain_ids=%s since_ts=%s",
        limit,
        chain_ids,
        since_ts,
    )
    query = """
    query GetRecentFlows($limit: Int!, $chainIds: [Int!]!, $sinceTs: Int) {
      deposits: Deposit(
        where: { chainId: { _in: $chainIds }, blockTimestamp: { _gte: $sinceTs } }
        order_by: { blockTimestamp: desc, blockNumber: desc, logIndex: desc }
        limit: $limit
      ) {
        id
        assets
        vaultAddress
        chainId
        blockNumber
        blockTimestamp
        transactionHash
        transactionFrom
      }
      withdrawals: Withdraw(
        where: { chainId: { _in: $chainIds }, blockTimestamp: { _gte: $sinceTs } }
        order_by: { blockTimestamp: desc, blockNumber: desc, logIndex: desc }
        limit: $limit
      ) {
        id
        assets
        vaultAddress
        chainId
        blockNumber
        blockTimestamp
        transactionHash
        transactionFrom
      }
    }
    """
    variables = {"limit": limit, "chainIds": chain_ids, "sinceTs": since_ts or 0}
    return gql_request(query, variables)


def alert_on_large_flows(events: list[dict], threshold_usd: Decimal):
    _logger.info("evaluating %s events", len(events))
    for event in events:
        tx_from = event.get("transactionFrom") or ""
        tx_from = tx_from.lower()
        if tx_from == IGNORED_FROM_ADDRESS:
            _logger.info("skip ignored tx.from %s", tx_from)
            continue
        vault = VAULTS.get(event["vaultAddress"].lower())
        if not vault:
            _logger.warning("skip unknown vault %s", event["vaultAddress"])
            continue
        amount = format_units(event["assets"], vault["decimals"])
        price = get_token_price_usd(vault["chain_id"], vault["token_address"], vault["symbol"])
        value = amount * price
        if value >= threshold_usd:
            ts = int(event["blockTimestamp"])
            print(
                json.dumps(
                    {
                        "alert": True,
                        "type": event["type"],
                        "value_usd": f"{value:.2f}",
                        "amount": f"{amount}",
                        "symbol": vault["symbol"],
                        "chain_id": vault["chain_id"],
                        "vault_address": event["vaultAddress"],
                        "from_address": event.get("transactionFrom"),
                        "transaction_hash": event["transactionHash"],
                        "block_timestamp": ts,
                    }
                )
            )


def main():
    parser = argparse.ArgumentParser(description="Alert on large deposit/withdraw events.")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--threshold-usd", type=Decimal, default=Decimal("5000000"))
    parser.add_argument("--since-seconds", type=int, default=7200) # 2 hours is default
    parser.add_argument("--chain-ids", type=str, default="1")
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
    _logger.info(
        "start limit=%s threshold_usd=%s since_seconds=%s chain_ids=%s",
        args.limit,
        args.threshold_usd,
        args.since_seconds,
        args.chain_ids,
    )

    since_ts = None
    if args.since_seconds:
        since_ts = int(time.time()) - args.since_seconds

    chain_ids = [int(x.strip()) for x in args.chain_ids.split(",") if x.strip()]

    response = load_events(args.limit, chain_ids, since_ts)
    if "errors" in response:
        _logger.error("gql errors: %s", response["errors"])
        print(json.dumps({"error": response["errors"]}), file=sys.stderr)
        sys.exit(1)

    data = response.get("data", {})
    deposits = data.get("deposits", [])
    withdrawals = data.get("withdrawals", [])
    _logger.info(
        "fetched deposits=%s withdrawals=%s",
        len(deposits),
        len(withdrawals),
    )

    for event in deposits:
        event["type"] = "deposit"
    for event in withdrawals:
        event["type"] = "withdraw"

    alert_on_large_flows(deposits + withdrawals, args.threshold_usd)


if __name__ == "__main__":
    main()
