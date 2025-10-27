import time
import json
from decimal import Decimal
import sys

from src.config import config

# We'll lazily import web3 to provide a helpful error if ENS/specs are missing.
# This avoids hard crash during 'import' and gives clear pip commands to fix the env.
def _import_web3():
    try:
        from web3 import Web3
        return Web3
    except Exception as e:
        # Common cause: web3 PyPI release missing ens/specs (yanked) or ens/web3 version conflicts.
        msg = """
Cannot import web3 properly. Typical causes:
 - Using a yanked PyPI release of web3 (missing ens/specs)
 - Missing or incompatible 'ens' package versions

Suggested fixes (run inside your virtualenv):

1) Preferred: install web3 from GitHub (includes correct package data):
   pip uninstall web3 ens -y
   pip install --no-cache-dir git+https://github.com/ethereum/web3.py.git

2) Or try a working PyPI release (older):
   pip uninstall web3 ens -y
   pip install --no-cache-dir web3==6.5.0

After installing, re-run your script.

Original import error:
""" + repr(e)
        print(msg, file=sys.stderr)
        raise

# Try importing Web3 now (will raise with helpful message if failing)
Web3 = _import_web3()

# load ABIs from local files (provided below)
with open("src/abis/UniswapV2Router.json") as f:
    ROUTER_ABI = json.load(f)["abi"]
with open("src/abis/ERC20.json") as f:
    ERC20_ABI = json.load(f)["abi"]

from web3 import Web3 as _Web3  # alias for usage
w3 = _Web3(_Web3.HTTPProvider(config.RPC_URL, request_kwargs={"timeout": 30}))
if not w3.is_connected():
    raise RuntimeError("Cannot connect to RPC: " + config.RPC_URL)

router = w3.eth.contract(address=Web3.to_checksum_address(config.DEX_ROUTER_ADDRESS), abi=ROUTER_ABI)

def get_wbnb_address():
    try:
        return router.functions.WETH().call()
    except Exception:
        return None

def get_token_contract(token_address):
    return w3.eth.contract(address=Web3.to_checksum_address(token_address), abi=ERC20_ABI)

def estimate_amounts_out(amount_in_wei: int, path: list):
    return router.functions.getAmountsOut(amount_in_wei, path).call()

def build_swap_exact_eth_for_tokens_tx(amount_out_min, path, to_address, value_wei, gas_price_wei=None):
    deadline = int(time.time()) + 60 * 5
    tx = router.functions.swapExactETHForTokens(
        amount_out_min,
        path,
        to_address,
        deadline
    ).build_transaction({
        "from": to_address,
        "value": value_wei,
        "nonce": w3.eth.get_transaction_count(to_address),
    })
    if gas_price_wei:
        tx["gasPrice"] = gas_price_wei
    else:
        tx["gasPrice"] = w3.eth.gas_price
    tx["gas"] = w3.eth.estimate_gas(tx)
    return tx

def build_swap_exact_tokens_for_eth_tx(amount_in_tokens, amount_out_min, path, to_address, gas_price_wei=None):
    deadline = int(time.time()) + 60 * 5
    tx = router.functions.swapExactTokensForETH(
        amount_in_tokens,
        amount_out_min,
        path,
        to_address,
        deadline
    ).build_transaction({
        "from": to_address,
        "nonce": w3.eth.get_transaction_count(to_address),
    })
    if gas_price_wei:
        tx["gasPrice"] = gas_price_wei
    else:
        tx["gasPrice"] = w3.eth.gas_price
    tx["gas"] = w3.eth.estimate_gas(tx)
    return tx

def sign_and_send_tx(private_key: str, tx: dict):
    signed = w3.eth.account.sign_transaction(tx, private_key=private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    return w3.to_hex(tx_hash)

def native_per_token(token_address: str, decimals: int = 18):
    amt = 10 ** decimals
    path = [Web3.to_checksum_address(token_address), Web3.to_checksum_address(get_wbnb_address())]
    amounts = estimate_amounts_out(amt, path)
    native_amount = amounts[-1]
    return Decimal(native_amount) / Decimal(10 ** 18)
