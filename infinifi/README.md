# Infinifi Protocol Monitoring

This directory contains monitoring scripts for the Infinifi protocol.

## Structure
- `main.py`: Monitors protocol reserves, backing (strategies vs iUSD supply), and liquid USDC reserves.
- `governance.py`: Monitors governance actions and key addresses.

## Governance Monitoring
The governance script monitors:
1. **Timelock Contracts**:
   - `TIMELOCK_SHORT`: `0x4B174afbeD7b98BA01F50E36109EEE5e6d327c32`
   - `TIMELOCK_LONG`: `0x3D18480CC32B6AB3B833dCabD80E76CfD41c48a9`
   - Alerts on `CallScheduled` and `CallExecuted` events.

2. **Deployer Address**:
   - `0xdecaDAc8778D088A30eE811b8Cc4eE72cED9Bf22`
   - Alerts on any transaction sent from this address.

## Resources
- Docs: https://docs.infinifi.xyz/
- iUSD Token: 0x48f9e38f3070AD8945DFEae3FA70987722E3D89c (Ethereum)
