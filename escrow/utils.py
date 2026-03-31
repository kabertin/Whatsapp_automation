from web3 import Web3
from .models import Trade
import uuid
from decouple import config
import json


def initialize_new_trade(buyer_wa, seller_wa, amount):
    w3 = Web3()
    account = w3.eth.account.create()

    # Create the trade record in our database
    trade = Trade.objects.create(
        trade_id=str(uuid.uuid4())[:8], # Short unique ID
        amount_usd=amount,
        escrow_address=account.address,
        escrow_private_key=account.key.hex(),
        buyer_wa=buyer_wa,
        seller_wa=seller_wa,
        status='AWAITING_PAYMENT'
    )
    return trade

def release_funds(trade_id, destination_wallet):
    """
    Moves USDT from the Escrow Wallet to the Seller/Buyer wallet.
    Requires MATIC in the Escrow Wallet for gas.
    """
    trade = Trade.objects.get(trade_id=trade_id)
    w3 = Web3(Web3.HTTPProvider(config('ALCHEMY_POLYGON_URL')))

    # Setup USDT Contract
    USDT_ADDRESS = "0xc2132D05D31c914a87C6611C10748AEb04B58e8F"
    USDT_ABI = json.loads('[{"constant":false,"inputs":[{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"type":"function"},{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]')

    contract = w3.eth.contract(address=USDT_ADDRESS, abi=USDT_ABI)

    # Get current balance
    balance_raw = contract.functions.balanceOf(trade.escrow_address).call()

    if balance_raw == 0:
        return "Error: Wallet is empty"

    # Build the transaction
    nonce = w3.eth.get_transaction_count(trade.escrow_address)

    # Prepare the transfer
    tx = contract.functions.transfer(
        destination_wallet,
        balance_raw
    ).build_transaction({
        'chainId': 137, # Polygon
        'gas': 100000,
        'gasPrice': w3.to_wei('40', 'gwei'), # Adjust based on network
        'nonce': nonce,
    })

    # Sign with the Escrow Private Key
    signed_tx = w3.eth.account.sign_transaction(tx, trade.escrow_private_key)

    # Send it!
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    trade.status = 'COMPLETED'
    trade.save()

    return w3.to_hex(tx_hash)


def refuel_escrow_with_matic(escrow_address):
    w3 = Web3(Web3.HTTPProvider(config('ALCHEMY_POLYGON_URL')))
    master_key = config('MASTER_VAULT_PRIVATE_KEY')
    master_account = w3.eth.account.from_key(master_key)

    # Send 0.1 MATIC
    tx = {
        'nonce': w3.eth.get_transaction_count(master_account.address),
        'to': escrow_address,
        'value': w3.to_wei(0.1, 'ether'),
        'gas': 21000,
        'gasPrice': w3.eth.gas_price,
        'chainId': 137
    }

    signed_tx = w3.eth.account.sign_transaction(tx, master_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    return w3.to_hex(tx_hash)
