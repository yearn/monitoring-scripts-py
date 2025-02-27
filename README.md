# SAM Tools

Monitoring scripts for DeFi protocols to track key metrics and send alerts.

## Supported Protocols

- [Aave V3](./aave/README.md)
- [Compound V3](./compound/README.md)
- [Euler](./euler/README.md)
- [Lido](./lido/README.md)
- [LRTs](./lrt-pegs/README.md)
- [Maker DAO](./maker/README.md)
- [Moonwell](./moonwell/README.md)
- [Morpho](./morpho/README.md)
- [Pendle](./pendle/README.md)
- [Silo](./silo/README.md)
- [Spark](./spark/README.md)
- [Stargate](./stargate/README.md)
- [USD0 - Usual Money](./usd0/README.md)

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yearn/monitoring-scripts-py.git
   cd monitoring-scripts-py
   ```

2. **Set up virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment setup**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

## Usage

Run a specific protocol monitor from the project root:
```bash
python -m <protocol>.main
```

Example:
```bash
python -m aave.main
```

## Code Style

Format code with black:
```bash
black .
```

Sort imports with isort:
```bash
isort .
```
