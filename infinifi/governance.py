from web3 import Web3

# Governance monitoring is handled via Tenderly alerts.
# Addresses are listed here for reference.

PROTOCOL = "infinifi"

# Multisig
TEAM_MULTISIG = Web3.to_checksum_address("0x80608f852D152024c0a2087b16939235fEc2400c")

# Timelocks
TIMELOCKS = {
    "TIMELOCK_SHORT": Web3.to_checksum_address("0x4B174afbeD7b98BA01F50E36109EEE5e6d327c32"),
    "TIMELOCK_LONG": Web3.to_checksum_address("0x3D18480CC32B6AB3B833dCabD80E76CfD41c48a9"),
}

# Deployer
DEPLOYER = Web3.to_checksum_address("0xdecaDAc8778D088A30eE811b8Cc4eE72cED9Bf22")

def main():
    print("Governance monitoring is handled via Tenderly alerts.")

if __name__ == "__main__":
    main()
