from web3 import Web3
import os

def create_escrow_wallet():
    """
    Generates a brand new Polygon wallet for a single trade.
    """
    w3 = Web3() # No connection needed just to generate keys
    account = w3.eth.account.create()

    return {
        "address": account.address,
        "private_key": account.key.hex()
    }

# Test the factory
if __name__ == "__main__":
    new_wallet = create_escrow_wallet()
    print("--- New Trade Wallet Generated ---")
    print(f"Public Address (Give to Buyer): {new_wallet['address']}")
    print(f"Private Key (Save to DB): {new_wallet['private_key']}")
