import json
from typing import Any, Dict, List


def load_abi(file_path: str) -> List[Dict[str, Any]]:
    """
    Load and parse an ABI file.

    Args:
        file_path: Path to the ABI file

    Returns:
        list: The ABI data as a list

    Raises:
        ValueError: If the ABI format is invalid
    """
    with open(file_path) as f:
        abi_data = json.load(f)
        if isinstance(abi_data, dict):
            return abi_data["result"]
        elif isinstance(abi_data, list):
            return abi_data
        else:
            raise ValueError("Invalid ABI format")
