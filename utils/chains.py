from enum import Enum

EXPLORER_URLS: dict[int, str] = {
    1: "https://etherscan.io",
    10: "https://optimistic.etherscan.io",
    137: "https://polygonscan.com",
    8453: "https://basescan.org",
    42161: "https://arbiscan.io",
    747474: "https://katanascan.com",
}


class Chain(Enum):
    MAINNET = (1, "mainnet", "eth")
    OPTIMISM = (10, "optimism", "op")
    BASE = (8453, "base", "base")
    ARBITRUM = (42161, "arbitrum", "arb")
    POLYGON = (137, "polygon", "matic")
    KATANA = (747474, "katana", "kat")

    def __init__(self, chain_id: int, network_name: str, symbol: str):
        self.chain_id = chain_id
        self.network_name = network_name
        self.symbol = symbol

    @property
    def explorer_url(self) -> str | None:
        """Block explorer base URL for this chain (e.g. https://etherscan.io)."""
        return EXPLORER_URLS.get(self.chain_id)

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
