from web3 import Web3
from web3.providers.base import BaseProvider
from web3.exceptions import ProviderConnectionError
from web3.contract import Contract
import time, os
from dotenv import load_dotenv
from typing import List, Dict, TypeVar, Callable
from .chains import Chain

load_dotenv()

T = TypeVar("T")  # Generic type for return values


class RetryProvider(BaseProvider):
    def __init__(
        self, providers: List[Web3.HTTPProvider], max_retries=3, backoff_factor=0.3
    ):
        self.providers = providers
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.current_provider_index = 0

    def make_request(self, method, params):
        retries = 0
        last_error = None

        while retries < self.max_retries:
            current_provider = self.providers[self.current_provider_index]
            try:
                response = current_provider.make_request(method, params)
                if "error" in response:
                    raise ProviderConnectionError(response["error"])
                return response
            except (ProviderConnectionError, IOError) as e:
                last_error = e
                retries += 1
                wait_time = self.backoff_factor * (2 ** (retries - 1))
                print(
                    f"Provider {self.current_provider_index + 1} failed with {e}. Retrying in {wait_time} seconds..."
                )
                time.sleep(wait_time)
                self.current_provider_index = (self.current_provider_index + 1) % len(
                    self.providers
                )

        raise ProviderConnectionError(
            f"All providers failed after {self.max_retries} retries. Last error: {last_error}"
        )


class BatchRequest:
    def __init__(self, web3_client: "Web3Client"):
        self._web3_client = web3_client
        self._calls = []

    def add(self, contract_function):
        """Add a contract function call to the batch"""
        self._calls.append(contract_function)

    def execute(self):
        """Execute all calls in the batch with retry logic"""
        results = []
        for call in self._calls:
            try:
                result = self._web3_client.execute(call.call)
                results.append(result)
            except Exception as e:
                print(f"Error in batch call: {e}")
                results.append(None)
        return results


class Web3Client:
    def __init__(self, chain: Chain):
        self.chain = chain
        self.w3 = self._initialize_web3()

    def _initialize_web3(self) -> Web3:
        """Initialize Web3 with retry provider for the specified chain"""
        providers = self._get_providers()
        retry_provider = RetryProvider(providers)
        return Web3(retry_provider)

    def _get_providers(self) -> List[Web3.HTTPProvider]:
        """Get providers for the chain from environment variables"""
        providers = []
        # try to get the default provider
        env_key = f"PROVIDER_URL_{self.chain.name.upper()}"
        url = os.getenv(env_key)
        if url:
            providers.append(Web3.HTTPProvider(url))
        #
        for i in range(1, 3):
            env_key = f"PROVIDER_URL_{self.chain.name.upper()}_{i}"
            url = os.getenv(env_key)
            if url:
                providers.append(Web3.HTTPProvider(url))

        if not providers:
            raise ValueError(f"No providers found for chain {self.chain.name}")
        return providers

    def execute(self, operation: Callable[..., T], *args, **kwargs) -> T:
        """Execute any Web3 operation with retry logic"""
        try:
            return operation(*args, **kwargs)
        except Exception as e:
            raise ProviderConnectionError(
                f"Operation failed on {self.chain.name}: {str(e)}"
            )

    @property
    def eth(self):
        """Access to eth namespace"""
        return self.w3.eth

    def get_contract(self, address: str, abi: List[Dict]) -> Contract:
        """Get contract instance"""
        return self.w3.eth.contract(address=address, abi=abi)

    def batch_requests(self) -> BatchRequest:
        """Create a new batch request with retry logic"""
        return BatchRequest(self)


class ChainManager:
    _instances: Dict[Chain, Web3Client] = {}

    @classmethod
    def get_client(cls, chain: Chain) -> Web3Client:
        """Get or create Web3Client instance for specified chain"""
        if chain not in cls._instances:
            cls._instances[chain] = Web3Client(chain)
        return cls._instances[chain]
