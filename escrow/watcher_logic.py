import json
from web3 import Web3
from decouple import config

# Official USDT Contract on Polygon
USDT_ADDRESS = "0xc2132D05D31c914a87C6611C10748AEb04B58e8F"
# Minimal ABI to check a balance
USDT_ABI = json.loads('[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]')

def check_for_payment(wallet_address):
    w3 = Web3(Web3.HTTPProvider(config('ALCHEMY_POLYGON_URL')))
    contract = w3.eth.contract(address=USDT_ADDRESS, abi=USDT_ABI)

    # USDT uses 6 decimals on Polygon
    balance_raw = contract.functions.balanceOf(wallet_address).call()
    balance_usdt = balance_raw / 10**6

    return balance_usdt
