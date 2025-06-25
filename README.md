# SAM Tools

Monitoring scripts for DeFi protocols to track key metrics and send alerts.

## Supported Protocols

- [Aave V3](./aave/README.md)
- [Compound V3](./compound/README.md)
- [Ethena](./ethena/README.md)
- [Euler](./euler/README.md)
- [Lido](./lido/README.md)
- [LRTs](./lrt-pegs/README.md)
- [Maker DAO](./maker/README.md)
- [Moonwell](./moonwell/README.md)
- [Morpho](./morpho/README.md)
- [Pendle](./pendle/README.md)
- [Resolv](./resolv/README.md)
- [RTokens - ETH+](./rtoken/README.md)
- [Silo](./silo/README.md)
- [Spark](./spark/README.md)
- [Stargate](./stargate/README.md)
- [USD0 - Usual Money](./usd0/README.md)

## Telegram Alerts

- Invite SAM alerter bot to Telegram group using handle: `@sam_alerter_bot`

## Installation

1. **Clone the repository**

```bash
git clone https://github.com/yearn/monitoring-scripts-py.git
cd monitoring-scripts-py
```

2. **Set up virtual environment**

```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install dependencies**

```bash
uv pip install -e ".[dev]"
```

> Note: This project uses [uv](https://github.com/astral-sh/uv) for faster dependency installation. If you don't have uv installed, you can install it with `pip install uv` or follow the [installation instructions](https://github.com/astral-sh/uv#installation).

4. **Environment setup**

Copy and edit example environment file:

```bash
cp .env.example .env
```

## Usage

Run a specific script for a protocol. Example:

```bash
uv run aave/main.py
```

## Code Style

Format and lint code with ruff:

```bash
uv run ruff format .
uv run ruff check --fix .
```
