import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from web3 import Web3
from src.web3_service import (
    w3,
    get_token_contract,
    get_wbnb_address,
    estimate_amounts_out,
    build_swap_exact_eth_for_tokens_tx,
    sign_and_send_tx,
)
from src.db import conn
from src.encryption import encrypt, decrypt
from decimal import Decimal

logger = logging.getLogger(__name__)

def start(update, context: CallbackContext):
    update.message.reply_text(
        "Welcome to Telegram DEX Bot (Python). Use /check, /setkey, /buy. Test on BSC Testnet first."
    )

def setkey(update, context: CallbackContext):
    # usage: /setkey <private_key>
    args = context.args
    if not args:
        update.message.reply_text("Usage: /setkey <private_key> (use testnet key for testing)")
        return
    pk = args[0].strip()
    if not pk.startswith("0x"):
        update.message.reply_text("Private key should start with 0x")
        return
    try:
        enc = encrypt(pk)
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO users (telegram_id, encrypted_wallet) VALUES (?, ?)",
            (str(update.effective_user.id), enc),
        )
        conn.commit()
        update.message.reply_text("Encrypted private key saved. It will never be shown in plain text.")
    except Exception as e:
        logger.exception("setkey error")
        update.message.reply_text("Error saving key: " + str(e))

def check_contract(update, context,):
    args = context.args
    if not args:
        update.message.reply_text("Usage: /check <contract_address>")
        return
    addr = args[0].strip()
    try:
        t = get_token_contract(addr)
        name = t.functions.name().call()
        symbol = t.functions.symbol().call()
        decimals = t.functions.decimals().call()
    except Exception as e:
        update.message.reply_text("Error reading token info: " + str(e))
        return

    # quick dexscreener API check (non-critical)
    try:
        import requests
        r = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{addr}")
        info = r.json()
        pair = info.get("pairs", [None])[0]
        pair_txt = f"Pair: {pair.get('pairAddress')}, Liquidity USD: {pair.get('liquidityUsd')}" if pair else "No quick pair found"
    except Exception:
        pair_txt = "No quick pair info (dexscreener failed)"

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Buy this token", callback_data=f"buy:{addr}")]])
    update.message.reply_text(f"Name: {name}\nSymbol: {symbol}\nDecimals: {decimals}\n{pair_txt}", reply_markup=keyboard)

def buy_command(update, context: CallbackContext):
    # /buy <token> <amount_native> [profit_percent]
    args = context.args
    if len(args) < 2:
        update.message.reply_text("Usage: /buy <token_address> <amount_native> [profit_percent]")
        return
    token = args[0].strip()
    amount_native = args[1].strip()
    profit = int(args[2]) if len(args) >= 3 else None

    # fetch encrypted key
    cur = conn.cursor()
    row = cur.execute("SELECT id, encrypted_wallet FROM users WHERE telegram_id = ?", (str(update.effective_user.id),)).fetchone()
    if not row:
        update.message.reply_text("No wallet found. Use /setkey to store an encrypted private key.")
        return
    user_id = row[0]
    enc = row[1]
    try:
        pk = decrypt(enc)
    except Exception as e:
        update.message.reply_text("Cannot decrypt wallet: " + str(e))
        return

    account = w3.eth.account.from_key(pk)
    from_address = account.address

    # convert amount_native (in BNB) to wei
    try:
        amount_wei = w3.to_wei(Decimal(amount_native), "ether")
    except Exception:
        update.message.reply_text("Invalid amount_native")
        return

    try:
        wbnb = get_wbnb_address()
        if not wbnb:
            update.message.reply_text("Router WETH/WBNB address not available from router.")
            return
        path = [Web3.to_checksum_address(wbnb), w3.to_checksum_address(token)]
        # estimate amountsOut
        amounts = estimate_amounts_out(int(amount_wei), path)
        expected_token_out = amounts[-1]
        # compute amountOutMin with slippage
        slippage_bps = int(context.bot_data.get("DEFAULT_SLIPPAGE_BPS", 300))
        amount_out_min = int(expected_token_out * (10000 - slippage_bps) / 10000)
        # build tx
        tx = build_swap_exact_eth_for_tokens_tx(amount_out_min, path, from_address, int(amount_wei))
        # sign & send
        tx_hash = sign_and_send_tx(pk, tx)
        update.message.reply_text(f"Buy transaction sent: {tx_hash}\nExpected tokens (approx): {expected_token_out}")
        # Save trade in DB with buy_price_native_per_token estimate
        buy_price = float(Decimal(amount_native) / (Decimal(expected_token_out) / Decimal(10 ** 18)))
        cur.execute(
            """INSERT INTO trades (user_id, tx_hash, token_address, amount_in_native, amount_token, buy_price_native_per_token, profit_target_percent, side, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, tx_hash, token, amount_native, str(expected_token_out), buy_price, profit or 0, "buy", "pending"),
        )
        conn.commit()
    except Exception as e:
        logger.exception("buy error")
        update.message.reply_text("Buy failed: " + str(e))
