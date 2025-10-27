import base64
import secrets
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
from src.config import config

SALT_LEN = 16
IV_LEN = 12
ITER = 200000
KEY_LEN = 32

def _derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA512(),
        length=KEY_LEN,
        salt=salt,
        iterations=ITER,
        backend=default_backend()
    )
    return kdf.derive(passphrase.encode())

def encrypt(plain_text: str) -> str:
    passphrase = config.ENCRYPTION_PASSPHRASE
    if not passphrase:
        raise ValueError("ENCRYPTION_PASSPHRASE not set in env")
    salt = secrets.token_bytes(SALT_LEN)
    key = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    iv = secrets.token_bytes(IV_LEN)
    ct = aesgcm.encrypt(iv, plain_text.encode(), None)
    return ".".join([base64.b64encode(x).decode() for x in (salt, iv, ct)])

def decrypt(payload: str) -> str:
    passphrase = config.ENCRYPTION_PASSPHRASE
    if not passphrase:
        raise ValueError("ENCRYPTION_PASSPHRASE not set in env")
    parts = payload.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid payload")
    salt = base64.b64decode(parts[0])
    iv = base64.b64decode(parts[1])
    ct = base64.b64decode(parts[2])
    key = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    pt = aesgcm.decrypt(iv, ct, None)
    return pt.decode()