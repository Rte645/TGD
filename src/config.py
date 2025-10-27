import os

class Config:
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    RPC_URL = os.getenv("RPC_URL", "")
    CHAIN_ID = int(os.getenv("CHAIN_ID", "97"))
    DEX_ROUTER_ADDRESS = os.getenv("DEX_ROUTER_ADDRESS", "")
    ENCRYPTION_PASSPHRASE = os.getenv("PRIVATE_KEY_PASSPHRASE", "")
    DATABASE_FILE = os.getenv("DATABASE_FILE", "./data/db.sqlite")
    DEFAULT_SLIPPAGE_BPS = int(os.getenv("DEFAULT_SLIPPAGE_BPS", "300"))  # basis points

config = Config()