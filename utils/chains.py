from enum import Enum


class Chain(Enum):
    MAINNET = (1, "mainnet", "eth")
    OPTIMISM = (10, "optimism", "op")
    BASE = (8453, "base", "base")
    ARBITRUM = (42161, "arbitrum", "arb")
    POLYGON = (137, "polygon", "matic")

    def __init__(self, chain_id: int, network_name: str, symbol: str):
        self.chain_id = chain_id
        self.network_name = network_name
        self.symbol = symbol

    @classmethod
    def from_chain_id(cls, chain_id: int) -> "Chain":
        for chain in cls:
            if chain.chain_id == chain_id:
                return chain
        raise ValueError(f"Unknown chain_id: {chain_id}")

    @classmethod
    def from_name(cls, name: str) -> "Chain":
        name = name.lower()
        for chain in cls:
            if chain.network_name == name:
                return chain
        raise ValueError(f"Unknown chain name: {name}")
