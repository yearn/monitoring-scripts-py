"""AI-powered transaction explainer.

Combines Tenderly simulation results with decoded calldata and sends
them to an LLM to produce human-readable explanations for governance
transactions (timelocks and Safe multisigs).
"""

from timelock.calldata_decoder import DecodedCall, decode_calldata
from utils.llm import get_llm_provider
from utils.llm.base import LLMError
from utils.logging import get_logger
from utils.proxy import build_diff_url, detect_proxy_upgrade, get_current_implementation
from utils.telegram import get_github_run_url
from utils.tenderly.simulation import SimulationResult, simulate_transaction

logger = get_logger("utils.llm.ai_explainer")

SYSTEM_PROMPT = """You are a DeFi risk analyst explaining governance transactions to a monitoring team.
Given the decoded calldata and simulation results, write a concise sentence explanation, max 5 sentences.
Always try to find the last change that happens in the transaction.
Focus on: what the transaction does, what assets/parameters change, and any risk implications."""


def _get_proxy_upgrade_info(calldata: str, target: str, chain_id: int) -> str:
    """Detect proxy upgrade and return context string for the LLM prompt."""
    new_impl = detect_proxy_upgrade(calldata)
    if not new_impl:
        return ""

    old_impl = get_current_implementation(target, chain_id)
    if old_impl:
        info = (
            f"This is a PROXY UPGRADE on {target}.\nCurrent implementation: {old_impl}\nNew implementation: {new_impl}"
        )
        diff_url = build_diff_url(old_impl, new_impl, chain_id)
        if diff_url:
            info += f"\nDiff: {diff_url}"
        return info

    return f"This is a PROXY UPGRADE on {target}.\nNew implementation: {new_impl}"


def _format_decoded_calls(calls: list[DecodedCall]) -> str:
    """Format decoded calls into a readable string for the LLM prompt."""
    parts: list[str] = []
    for i, call in enumerate(calls):
        lines = [f"Call {i + 1}: {call.signature}"]
        for type_str, value in call.params:
            lines.append(f"  {type_str}: {value}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def _format_simulation_context(sim: SimulationResult) -> str:
    """Format simulation results into a readable string for the LLM prompt."""
    parts: list[str] = []

    parts.append(f"Simulation: {'SUCCESS' if sim.success else 'FAILED'}")
    if sim.error_message:
        parts.append(f"Error: {sim.error_message}")
    parts.append(f"Gas used: {sim.gas_used:,}")

    if sim.asset_changes:
        parts.append("\nToken transfers:")
        for change in sim.asset_changes:
            amount = change.amount
            parts.append(f"  {amount} {change.token_symbol} from {change.from_address} to {change.to_address}")

    if sim.state_changes:
        # Show up to 10 most relevant state changes to avoid prompt bloat
        shown = sim.state_changes[:10]
        parts.append(f"\nState changes ({len(sim.state_changes)} total, showing {len(shown)}):")
        for sc in shown:
            parts.append(f"  Contract {sc.contract_address}: {sc.key}")
            parts.append(f"    {sc.original} -> {sc.dirty}")

    if sim.logs:
        shown_logs = sim.logs[:10]
        parts.append(f"\nEvents emitted ({len(sim.logs)} total, showing {len(shown_logs)}):")
        for log_entry in shown_logs:
            name = log_entry.get("name", "Unknown")
            inputs = log_entry.get("inputs", [])
            input_strs = [f"{inp.get('soltype', {}).get('name', '?')}={inp.get('value', '?')}" for inp in inputs]
            parts.append(f"  {name}({', '.join(input_strs)})")

    return "\n".join(parts)


def _build_prompt(
    target: str,
    value: int,
    decoded_calls: list[DecodedCall],
    simulation: SimulationResult | None,
    protocol: str = "",
    label: str = "",
    proxy_upgrade_info: str = "",
) -> str:
    """Build the full prompt for the LLM."""
    parts: list[str] = [SYSTEM_PROMPT, ""]

    if protocol:
        parts.append(f"Protocol: {protocol}")
    if label:
        parts.append(f"Contract: {label}")
    parts.append(f"Target: {target}")
    if value > 0:
        parts.append(f"ETH Value: {value / 1e18:.6f} ETH")

    parts.append(f"\n--- Decoded Calldata ---\n{_format_decoded_calls(decoded_calls)}")

    if proxy_upgrade_info:
        parts.append(f"\n--- Proxy Upgrade ---\n{proxy_upgrade_info}")

    if simulation:
        parts.append(f"\n--- Simulation Results ---\n{_format_simulation_context(simulation)}")

    return "\n".join(parts)


def explain_transaction(
    target: str,
    calldata: str,
    chain_id: int,
    value: int = 0,
    protocol: str = "",
    label: str = "",
    from_address: str = "0x0000000000000000000000000000000000000000",
) -> str | None:
    """Generate an AI explanation for a governance transaction.

    Decodes calldata, simulates via Tenderly, and sends context to the LLM.
    Returns None if explanation cannot be generated (missing API keys, errors, etc.).

    Args:
        target: Target contract address.
        calldata: Hex-encoded calldata (with 0x prefix).
        chain_id: Chain ID (e.g. 1 for mainnet).
        value: ETH value in wei.
        protocol: Protocol name for context (e.g. "AAVE").
        label: Human-readable label for the contract.
        from_address: Sender address for simulation.

    Returns:
        AI-generated explanation string, or None on failure.
    """
    if not calldata or len(calldata) < 10:
        return None

    # Step 1: Decode calldata (reuse existing decoder)
    decoded = decode_calldata(calldata)
    if not decoded:
        logger.info("Could not decode calldata for %s, skipping AI explanation", target)
        return None

    decoded_calls = [decoded]

    # Step 2: Detect proxy upgrade (best-effort)
    proxy_upgrade_info = _get_proxy_upgrade_info(calldata, target, chain_id)

    # Step 3: Simulate via Tenderly (best-effort)
    simulation = simulate_transaction(
        target=target,
        calldata=calldata,
        chain_id=chain_id,
        value=value,
        from_address=from_address,
    )
    if simulation:
        logger.info("Simulation completed: success=%s gas=%s", simulation.success, simulation.gas_used)
    else:
        logger.info("Simulation unavailable, proceeding with decoded calldata only")

    # Step 4: Build prompt and call LLM
    prompt = _build_prompt(
        target=target,
        value=value,
        decoded_calls=decoded_calls,
        simulation=simulation,
        protocol=protocol,
        label=label,
        proxy_upgrade_info=proxy_upgrade_info,
    )
    logger.info("Full AI context for %s:\n%s", target, prompt)

    try:
        provider = get_llm_provider()
        explanation = provider.complete(prompt)
        logger.info("AI explanation generated using %s:\n%s", provider.model_name, explanation)
        return explanation
    except LLMError as e:
        logger.error("Failed to generate AI explanation: %s", e)
        return None


def explain_batch_transaction(
    calls: list[dict[str, str]],
    chain_id: int,
    protocol: str = "",
    label: str = "",
    from_address: str = "0x0000000000000000000000000000000000000000",
) -> str | None:
    """Generate an AI explanation for a batch/multicall governance transaction.

    Args:
        calls: List of dicts with keys: target, data, value.
        chain_id: Chain ID.
        protocol: Protocol name for context.
        label: Human-readable label for the timelock/safe.
        from_address: Sender address for simulations.

    Returns:
        AI-generated explanation string, or None on failure.
    """
    if not calls:
        return None

    decoded_calls: list[DecodedCall] = []
    simulations: list[SimulationResult | None] = []

    for call in calls:
        target = call.get("target", "")
        data = call.get("data", "0x")
        value = int(call.get("value", "0"))

        decoded = decode_calldata(data)
        if decoded:
            decoded_calls.append(decoded)

        sim = simulate_transaction(
            target=target,
            calldata=data,
            chain_id=chain_id,
            value=value,
            from_address=from_address,
        )
        simulations.append(sim)

    if not decoded_calls:
        return None

    # Use the first successful simulation for context, or None
    simulation = next((s for s in simulations if s is not None), None)

    # Detect proxy upgrades across all calls
    upgrade_parts: list[str] = []
    for call in calls:
        info = _get_proxy_upgrade_info(call.get("data", "0x"), call.get("target", ""), chain_id)
        if info:
            upgrade_parts.append(info)
    proxy_upgrade_info = "\n".join(upgrade_parts)

    # For batch, show all targets
    targets = ", ".join(c.get("target", "?") for c in calls)
    total_value = sum(int(c.get("value", "0")) for c in calls)

    prompt = _build_prompt(
        target=targets,
        value=total_value,
        decoded_calls=decoded_calls,
        simulation=simulation,
        protocol=protocol,
        label=label,
        proxy_upgrade_info=proxy_upgrade_info,
    )
    logger.info("Full AI context for batch (%s calls):\n%s", len(calls), prompt)

    try:
        provider = get_llm_provider()
        explanation = provider.complete(prompt)
        logger.info("Batch AI explanation generated using %s:\n%s", provider.model_name, explanation)
        return explanation
    except LLMError as e:
        logger.error("Failed to generate batch AI explanation: %s", e)
        return None


def format_explanation_line(explanation: str) -> str:
    """Format the AI explanation for inclusion in a Telegram alert message.

    Includes a link to GitHub Actions logs when running in CI,
    where the full decoded calldata, simulation results, and prompt are logged.
    """
    line = f"\n🤖 *AI Summary:*\n{explanation}"
    run_url = get_github_run_url()
    if run_url:
        line += f"\n[Full details]({run_url})"
    return line
