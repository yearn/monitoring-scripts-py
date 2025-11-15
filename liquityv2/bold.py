MULTI_TROVE_GETTER = 0xFA61dB085510C64B83056Db3A7Acf3b6f631D235
COLLATERAL_REGISTRY = 0xf949982B91C8c61e952B3bA942cbbfaef5386684

import logging
from decimal import Decimal

from web3.exceptions import ContractCustomError

# Adapted to project utils
from utils.web3_wrapper import Chain, ChainManager
from utils.abi import load_abi
from utils.config import Config

# Local placeholders for values expected from original chain.config
# You may wish to move these to an env or config file if needed
ADMIN_ADDRESS = Config.get_env("ADMIN_ADDRESS", "0x0000000000000000000000000000000000000000")
BOLD_REDEMPTION_EXECUTOR_ADDRESS = Config.get_env(
    "BOLD_REDEMPTION_EXECUTOR_ADDRESS", "0x0000000000000000000000000000000000000000"
)
DECIMAL_PRECISION = 10**18

# Collateral type mapping can be provided via env as JSON or hardcoded mapping
import json
_coll_map_raw = Config.get_env("LIQUITYV2_COLLATERAL_TYPE_TO_INDEX", "{}")
try:
    COLLATERAL_TYPE_TO_INDEX = json.loads(_coll_map_raw)
except Exception:
    COLLATERAL_TYPE_TO_INDEX = {}


# Helper adapters to replace chain.read and chain.utils
def _get_client():
    return ChainManager.get_client(Chain.MAINNET)


# Expose web3 client instance similar to prior usage
web3 = _get_client().w3


def get_dynamic_gas_price() -> int:
    return _get_client().eth.gas_price


def estimate_gas(tx_params: dict) -> int:
    return _get_client().eth.estimate_gas(tx_params)


def load_contract(name: str, address: str):
    # Name left for compatibility; caller passes address explicitly.
    # ABI resolution can be improved if standardised names/paths are known.
    # For now assume ABIs live under liquityv2/ or common-abi/ with exact filenames.
    # Users should adjust abi_path mapping below as needed.
    abi_path_map = {
        "ERC20": "common-abi/ERC20.json",
        "troveNFT": "liquityv2/abi/troveNFT.json",
        "boldRedemptionsExecutor": "liquityv2/abi/boldRedemptionsExecutor.json",
        # add other contracts as needed
    }
    abi_path = abi_path_map.get(name)
    if abi_path is None:
        raise ValueError(f"ABI path for contract {name} is not configured")
    abi = load_abi(abi_path)
    return _get_client().w3.eth.contract(address=address, abi=abi)


def decode_custom_error(abi, exception: Exception) -> str:
    # Minimal placeholder; proper decoding would parse error selector against ABI
    return str(exception)


# Curve helpers – require pool ABI compatibility with get_dy and coins/underlying tokens
CURVE_POOL_ABI = load_abi("common-abi/CurvePool.json")


def get_token_address_from_curve_pool(index: int, pool_address: str) -> str:
    pool = _get_client().w3.eth.contract(address=pool_address, abi=CURVE_POOL_ABI)
    try:
        return pool.functions.coins(index).call()
    except Exception:
        # Some pools expose underlying_coins
        return pool.functions.underlying_coins(index).call()


def get_decimals(token_address: str) -> int:
    erc20 = _get_client().w3.eth.contract(address=token_address, abi=load_abi("common-abi/ERC20.json"))
    return erc20.functions.decimals().call()


def get_dy(curve_pool_address: str, i: int, j: int, dx: int) -> int:
    pool = _get_client().w3.eth.contract(address=curve_pool_address, abi=CURVE_POOL_ABI)
    return pool.functions.get_dy(i, j, int(dx)).call()


# --- LiquityV2-specific helpers (stubs to be implemented with proper ABIs) ---

def get_eth_balance(address: str) -> Decimal:
    wei = _get_client().eth.get_balance(address)
    return Decimal(wei) / Decimal(10**18)


def get_collateral_price(collateral_index: int) -> int:
    raise NotImplementedError("Implement get_collateral_price using LiquityV2 price feed ABI")


def get_minimum_collateral_ratio(collateral_index: int) -> int:
    raise NotImplementedError("Implement get_minimum_collateral_ratio from TroveManager or system params")


def get_multiple_sorted_troves(collateral_index: int) -> list:
    raise NotImplementedError("Implement get_multiple_sorted_troves via MultiTroveGetter ABI")


def get_trove_manager_address(collateral_index: int) -> str:
    raise NotImplementedError("Implement get_trove_manager_address via registry/config")


def get_current_icr(trove_manager_address: str, trove_id: int, collateral_price: int) -> int:
    raise NotImplementedError("Implement get_current_icr via TroveManager ABI")


def get_trove_nft_address(collateral_index: int) -> str:
    raise NotImplementedError("Implement get_trove_nft_address via registry/config")


def get_redemption_fee_rate_for_amount(redeem_amount_wei: int) -> int:
    raise NotImplementedError("Implement get_redemption_fee_rate_for_amount via stability pool/fee model ABI")

MINIMUM_ETH_REQUIRED = Decimal("0.001")


def has_sufficient_eth(address: str, threshold: Decimal = MINIMUM_ETH_REQUIRED) -> bool:
    """
    Checks if a given address has sufficient ETH for gas.

    Args:
        address (str): The Ethereum address to check.
        threshold (Decimal): The minimum ETH required.

    Returns:
        bool: True if the address has sufficient ETH, False otherwise.
    """
    balance = get_eth_balance(address)
    return balance >= threshold


def find_collateral_index(collateral_type: str) -> int:
    """
    Find the collateral index for a given collateral type.

    Args:
        collateral_type (str): The collateral type to check.

    Returns:
        int: The collateral index.
    """
    collateral_index = COLLATERAL_TYPE_TO_INDEX[collateral_type]
    if collateral_index is None:
        raise Exception(f"Invalid collateral type: {collateral_type}")

    return collateral_index


def find_liquidatable_troves(collateral_type: str) -> list:
    """
    Find the liquidatable troves for a given collateral type.

    Args:
        collateral_type (str): The collateral type to check.

    Returns:
        list: The liquidatable trove IDs.
    """
    collateral_index = find_collateral_index(collateral_type=collateral_type)

    collateral_price = get_collateral_price(collateral_index=collateral_index)
    minimum_collateral_ratio = get_minimum_collateral_ratio(
        collateral_index=collateral_index
    )

    liquidatable_troves = []
    troves = get_multiple_sorted_troves(collateral_index=collateral_index)
    trove_manager_address = get_trove_manager_address(collateral_index=collateral_index)
    for trove in troves:
        trove_id = trove["id"]
        if (
            get_current_icr(
                trove_manager_address=trove_manager_address,
                trove_id=trove_id,
                collateral_price=collateral_price,
            )
            < minimum_collateral_ratio
        ):
            liquidatable_troves.append(trove_id)
        else:
            pass

    return liquidatable_troves


def is_trove_liquidatable(
    collateral_price: int,
    minimum_collateral_ratio: int,
    entire_debt: int,
    entire_coll: int,
) -> bool:
    """
    Checks if a trove is liquidatable.

    Args:
        collateral_price (Decimal): The price of the collateral.
        minimum_collateral_ratio (Decimal): The minimum collateral ratio.
        entire_debt (Decimal): The entire debt of the trove.
        entire_coll (Decimal): The entire collateral of the trove.

    Returns:
        bool: True if the trove is liquidatable, False otherwise.
    """
    entire_coll_in_usd = entire_coll * collateral_price // 10**18
    required_collateral_in_usd = minimum_collateral_ratio * entire_debt // 10**18
    return entire_coll_in_usd < required_collateral_in_usd


def find_troves_close_to_liquidation(
    collateral_type: str, minimum_ltv: int = 50, n: int = 5
) -> list[dict]:
    """
    Find troves close to liquidation for a given collateral type.

    Args:
        collateral_type (str): The collateral type to check.

    Returns:
        list of dict: The troves close to liquidation.
    """
    collateral_index = find_collateral_index(collateral_type=collateral_type)
    collateral_price = get_collateral_price(collateral_index=collateral_index)
    minimum_collateral_ratio = get_minimum_collateral_ratio(
        collateral_index=collateral_index
    )

    troves_close_to_liquidation = []
    troves = get_multiple_sorted_troves(collateral_index=collateral_index)
    for trove in troves:
        trove_id = trove["id"]
        coll = trove["coll"]
        debt = trove["debt"]
        coll_in_usd = coll * collateral_price / 10**18
        ltv = debt / coll_in_usd * 100
        required_collateral_in_usd = minimum_collateral_ratio * debt // 10**18
        liquidation_price = required_collateral_in_usd * 10**18 / coll

        if ltv > minimum_ltv:
            troves_close_to_liquidation.append(
                {
                    "id": trove_id,
                    "collateral": coll,
                    "debt": debt,
                    "ltv": ltv,
                    "collateral_price": collateral_price,
                    "collateral_liquidation_price": liquidation_price,
                }
            )

        troves_close_to_liquidation.sort(key=lambda x: x["ltv"], reverse=True)

    return troves_close_to_liquidation[:n]


def compute_troves_close_to_liquidation(
    troves: list[dict],
    collateral_price: int,
    minimum_collateral_ratio: int,
    minimum_ltv: int = 50,
    n: int = 5,
) -> list[dict]:
    """
    Pure helper: filter and rank troves close to liquidation using provided data.

    Args:
        troves: list of dicts with keys: "id", "coll", "debt"
        collateral_price: price with 18 decimals
        minimum_collateral_ratio: MCR with 18 decimals
        minimum_ltv: threshold in percent
        n: max results

    Returns:
        list[dict]: sorted by ltv descending, top n
    """
    troves_close_to_liquidation = []
    for trove in troves:
        trove_id = trove["id"]
        coll = trove["coll"]
        debt = trove["debt"]
        coll_in_usd = coll * collateral_price / 10**18
        if coll_in_usd == 0:
            continue
        ltv = debt / coll_in_usd * 100
        required_collateral_in_usd = minimum_collateral_ratio * debt // 10**18
        liquidation_price = required_collateral_in_usd * 10**18 / coll if coll != 0 else 0

        if ltv > minimum_ltv:
            troves_close_to_liquidation.append(
                {
                    "id": trove_id,
                    "collateral": coll,
                    "debt": debt,
                    "ltv": ltv,
                    "collateral_price": collateral_price,
                    "collateral_liquidation_price": liquidation_price,
                }
            )

    troves_close_to_liquidation.sort(key=lambda x: x["ltv"], reverse=True)
    return troves_close_to_liquidation[:n]


def find_trove_owner(trove_id: int, collateral_type: str) -> str:
    """
    Fetches the owner of a trove.

    Args:
        trove_id (int): The ID of the trove.

    Returns:
        str: The address of the owner.
    """
    collateral_index = find_collateral_index(collateral_type=collateral_type)
    trove_nft_address = get_trove_nft_address(collateral_index=collateral_index)
    trove_nft_contract = load_contract("troveNFT", trove_nft_address)
    return trove_nft_contract.functions.ownerOf(trove_id).call()


def find_max_amount_under_price_binary_curve_pool(
    curve_pool_address,
    i: int,  # index of token-in
    j: int,  # index of token-out
    target_price: int,  # with 18 decimals
    max_token_in: int = 50_000,  # this number will be scaled by `i`'s decimals
    iterations: int = 15,
) -> int:
    """
    Uses a standard binary search (single pass) to find the maximum token-in (dx)
    for which price(dx) <= target_price

    Args:
      - curve_pool_address: Contract address for the Curve pool
      - i, j: token indices in the Curve pool
      - target_price: in wei, e.g. 995 * 10**15 for 0.995
      - max_token_in: upper bound for search, in eth, e.g. 1_000_000 for 1M tokens
      - iterations: how many times to bisect. 20 is plenty for 256-bit range in practice.

    Returns:
      max_dx_scaled: the maximum token-in amount that satisfies the price condition in wei with 18 decimals. 0 if no solution found.
      max_dy_scaled: the corresponding token-out amount in wei with 18 decimals.
    """
    # Get token decimals
    decimals_token_i = get_decimals(
        get_token_address_from_curve_pool(index=i, pool_address=curve_pool_address)
    )
    decimals_token_j = get_decimals(
        get_token_address_from_curve_pool(index=j, pool_address=curve_pool_address)
    )

    # Sanity check: if 1 token-in gives a price >= target_price, return 0
    dx_sanity = 1 * 10**decimals_token_i
    dy_sanity = get_dy(curve_pool_address, i, j, dx_sanity)

    dy_sanity_scaled = dy_sanity
    if decimals_token_j < 18:
        dy_sanity_scaled *= 10 ** (18 - decimals_token_j)

    dx_sanity_scaled = dx_sanity
    if decimals_token_i < 18:
        dx_sanity_scaled *= 10 ** (18 - decimals_token_i)

    price_approx_sanity = dx_sanity_scaled * DECIMAL_PRECISION / dy_sanity_scaled
    if price_approx_sanity >= target_price:
        return 0

    # Binary search
    lower = 0
    upper = max_token_in
    max_dx = 0
    max_dy_scaled = 0
    for _ in range(iterations):
        if lower > upper:
            break

        mid = (lower + upper) // 2
        dy = get_dy(curve_pool_address, i, j, mid * 10**decimals_token_i)
        if dy == 0:
            # overshoot or zero liquidity
            upper = mid - 1
            continue

        dy_scaled = dy
        if decimals_token_j < 18:
            dy_scaled *= 10 ** (18 - decimals_token_j)

        mid_scaled = mid * 10**18
        price_approx = mid_scaled * DECIMAL_PRECISION / dy_scaled
        if price_approx <= target_price:
            # mid is feasible, let's see if we can go higher
            max_dx = mid
            max_dy_scaled = dy_scaled
            lower = mid + 1
        else:
            # mid is too expensive
            upper = mid - 1

    if max_dx == 0:
        # no solution found
        return 0

    max_dx_scaled = max_dx * 10**decimals_token_i
    if decimals_token_i < 18:
        max_dx_scaled *= 10 ** (18 - decimals_token_i)

    return max_dx_scaled, max_dy_scaled


from decimal import Decimal


def find_max_redeem_under_allin_cost(
    stablecoin_purchase_price: int,  # in 18 decimals wei
    total_gas_cost: int,  # gas cost in wei
    max_redeem_tokens: int,  # in 18 decimals wei. upper bound
    swap_cost_rate: int = 0,  # 5 * 10**14,  # 0.05% swap cost (slippage + fees)
    iterations: int = 15,
) -> int:
    """
    Binary-search for the largest redemption amount X in [0..max_redeem_tokens]
    such that (purchase_price + redemption_fee_rate(X) + overhead) < 1.0.

    Returns the redemption amount X (in raw wei) that satisfies the condition.
    If none is feasible, returns 0.
    """
    lower = 0
    upper = max_redeem_tokens
    best = 0
    for _ in range(iterations):
        if lower > upper:
            break

        mid = (lower + upper) // 2
        redemption_fee_rate = get_redemption_fee_rate_for_amount(redeem_amount_wei=mid)
        overhead_per_stablecoin = (total_gas_cost / mid) + (
            mid * swap_cost_rate / DECIMAL_PRECISION
        )
        total_cost = (
            stablecoin_purchase_price + redemption_fee_rate + overhead_per_stablecoin
        )

        if total_cost < 1 * 10**18:
            # feasible, try bigger
            best = mid
            lower = mid + 1
        else:
            # not feasible
            upper = mid - 1

    return best


def calc_price_curve_pool(
    curve_pool_address: str,
    amount: int,  # raw amount of token i (this will be scaled by i's decimals)
    i: int,
    j: int,
) -> int:
    """
    Calculate the price of token j in terms of token i in a Curve pool.

    Args:
        curve_pool_address (str): The address of the Curve pool.
        amount (int): The amount of token i.
        i (int): The index of token i.
        j (int): The index of token j.

    Returns:
        int: The price of token j in terms of token i.
    """
    decimals_token_i = get_decimals(
        get_token_address_from_curve_pool(index=i, pool_address=curve_pool_address)
    )
    decimals_token_j = get_decimals(
        get_token_address_from_curve_pool(index=j, pool_address=curve_pool_address)
    )

    amount_scaled = amount * 10**decimals_token_i
    dy = get_dy(
        curve_pool_address=curve_pool_address,
        i=i,
        j=j,
        dx=amount_scaled,
    )

    dy_scaled = dy
    if decimals_token_j < 18:
        dy_scaled *= 10 ** (18 - decimals_token_j)

    if decimals_token_i < 18:
        amount_scaled *= 10 ** (18 - decimals_token_i)

    return amount_scaled * DECIMAL_PRECISION / dy_scaled


def estimate_gas_cost_for_redeem(amount: int) -> int:
    """
    Estimates the gas cost for redeeming collateral.

    Returns:
        int: The estimated gas cost.
    """
    gas_price = get_dynamic_gas_price()
    boldRedemptionExecutor_contract = load_contract(
        "boldRedemptionsExecutor", BOLD_REDEMPTION_EXECUTOR_ADDRESS
    )
    try:
        redeem_tx = boldRedemptionExecutor_contract.functions.iloveshrooms(
            amount, 0  # amount to redeem  # gas cost
        ).build_transaction(
            {
                "from": ADMIN_ADDRESS,
                "nonce": web3.eth.get_transaction_count(ADMIN_ADDRESS),
                "gasPrice": gas_price,
            }
        )
    except ContractCustomError as e:
        print(e)
        raise ValueError(decode_custom_error(boldRedemptionExecutor_contract.abi, e))

    return estimate_gas(redeem_tx)


def find_max_redemption_executor_amount(
    start_amount: int = 2500 * 1 * 10**6,
    end_amount: int = 50000 * 1 * 10**6,
    gas_used_estimate: int = 1_400_000,
    iterations: int = 10,
) -> tuple[int, int]:
    """
    Binary-search for the largest redemption amount X in [start_amount..end_amount]
    such that iloveshrooms(X) does not revert.

    Args:
        start_amount: minimum amount to search
        end_amount: maximum amount to search
        gas_used_estimate: gas used by iloveshrooms
        iterations: number of binary search iterations

    Returns:
        best_feasible: the largest amount that does not revert
        gas_cost_wei: the gas cost in wei
    """
    gas_price_wei = get_dynamic_gas_price()
    gas_cost_wei = gas_used_estimate * gas_price_wei

    boldRedemptionExecutor_contract = load_contract(
        "boldRedemptionsExecutor", BOLD_REDEMPTION_EXECUTOR_ADDRESS
    )
    nonce = web3.eth.get_transaction_count(ADMIN_ADDRESS)

    lower = start_amount
    upper = end_amount
    best_feasible = 0

    for _ in range(iterations):
        if lower > upper:
            break
        mid = (lower + upper) // 2

        try:
            boldRedemptionExecutor_contract.functions.iloveshrooms(
                mid, gas_cost_wei
            ).build_transaction(
                {
                    "from": ADMIN_ADDRESS,
                    "nonce": nonce,
                }
            )

            # if we get here => no revert => feasible
            best_feasible = mid
            lower = mid + 1
        except:
            # revert => mid is too big
            upper = mid - 1

    return best_feasible, gas_cost_wei