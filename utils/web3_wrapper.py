import os
import time
from typing import Any, Callable, Dict, List, Tuple, TypeVar
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from web3 import Web3
from web3.exceptions import Web3RPCError
from web3.contract import Contract
from web3.exceptions import ProviderConnectionError
from web3.providers.rpc import HTTPProvider
from web3.types import RPCResponse

from .chains import Chain

load_dotenv()

T = TypeVar("T")  # Generic type for return values


class MultiHTTPProvider(HTTPProvider):
    def __init__(
        self,
        providers: List[str],
        request_kwargs: Dict[str, Any] = None,
        max_retries: int = 3,
        backoff_factor: float = 0.3,
    ):
        self.provider_urls = self._validate_urls(providers)
        if not self.provider_urls:
            raise ValueError("No valid provider URLs provided")

        self.current_provider_index = 0
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.request_kwargs = request_kwargs or {}  # Store request_kwargs

        # Initialize with custom request kwargs
        self.request_kwargs.setdefault("timeout", 100)  # Add default timeout

        super().__init__(
            endpoint_uri=self.provider_urls[0], request_kwargs=self.request_kwargs
        )

    def _validate_urls(self, urls: List[str]) -> List[str]:
        """Validate and filter provider URLs"""
        valid_urls = []
        for url in urls:
            if not url:
                continue
            try:
                parsed = urlparse(url)
                if not parsed.scheme or not parsed.netloc:
                    print(f"Invalid URL format: {url}")
                    continue
                valid_urls.append(url)
            except Exception as e:
                print(f"Error validating URL {url}: {str(e)}")
        return valid_urls

    def _rotate_provider(self) -> None:
        """Switch to the next provider in the list"""
        self.current_provider_index = (self.current_provider_index + 1) % len(
            self.provider_urls
        )
        self.endpoint_uri = self.provider_urls[self.current_provider_index]
        print(f"Switching to provider: {self.endpoint_uri}")
        self.session = requests.Session()
        for key, value in self.request_kwargs.get(
            "session_kwargs", {}
        ).items():  # Use request_kwargs instead of _kwargs
            setattr(self.session, key, value)

    def make_request(self, method: str, params: List[Any]) -> RPCResponse:
        retries = 0
        errors = {}

        while retries < self.max_retries * len(self.provider_urls):
            try:
                return super().make_request(method, params)
            except Exception as e:
                current_url = self.endpoint_uri
                errors[current_url] = str(e)
                retries += 1

                wait_time = self.backoff_factor * (2 ** (retries - 1))
                print(f"Provider {current_url} failed. Error: {str(e)}")
                print(f"Switching provider and retrying in {wait_time} seconds...")

                time.sleep(wait_time)
                self._rotate_provider()

        error_details = "\n".join([f"{url}: {error}" for url, error in errors.items()])
        raise ProviderConnectionError(
            f"All providers failed after {retries} attempts.\nErrors:\n{error_details}"
        )

    def make_batch_request(self, methods: List[Any]) -> List[RPCResponse]:
        retries = 0
        errors = {}

        while retries < self.max_retries * len(self.provider_urls):
            try:
                return super().make_batch_request(methods)
            except (Web3RPCError, Exception) as e:
                current_url = self.endpoint_uri
                errors[current_url] = str(e)
                retries += 1

                wait_time = self.backoff_factor * (2 ** (retries - 1))
                print(f"Batch request failed on {current_url}. Error: {str(e)}")
                print(f"Switching provider and retrying in {wait_time} seconds...")

                time.sleep(wait_time)
                self._rotate_provider()

        error_details = "\n".join([f"{url}: {error}" for url, error in errors.items()])
        raise ProviderConnectionError(
            f"Batch requests failed on all providers after {retries} attempts.\nErrors:\n{error_details}"
        )


class Web3Client:
    def __init__(self, chain: Chain):
        self.chain = chain
        self.w3 = self._initialize_web3()

    def _initialize_web3(self) -> Web3:
        """Initialize Web3 with multi-provider setup"""
        provider_urls = self._get_provider_urls()
        provider = MultiHTTPProvider(
            providers=provider_urls, max_retries=3, backoff_factor=0.3
        )
        return Web3(provider)

    def _get_provider_urls(self) -> List[str]:
        """Get provider URLs for the chain from environment variables"""
        urls = []
        # Get default provider
        env_key = f"PROVIDER_URL_{self.chain.name.upper()}"
        url = os.getenv(env_key)
        if url:
            urls.append(url)

        # Get additional providers
        for i in range(1, 3):
            env_key = f"PROVIDER_URL_{self.chain.name.upper()}_{i}"
            url = os.getenv(env_key)
            if url:
                urls.append(url)

        if not urls:
            raise ValueError(f"No providers found for chain {self.chain.name}")
        return urls

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

    def batch_requests(self):
        return self.w3.batch_requests()


class ChainManager:
    _instances: Dict[Chain, Web3Client] = {}

    @classmethod
    def get_client(cls, chain: Chain) -> Web3Client:
        """Get or create Web3Client instance for specified chain"""
        if chain not in cls._instances:
            cls._instances[chain] = Web3Client(chain)
        return cls._instances[chain]
