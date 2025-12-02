# app/core/local_storage.py

import os
import uuid
from cryptography.fernet import Fernet

BASE_DIR = "storage"
os.makedirs(f"{BASE_DIR}/incoming", exist_ok=True)
os.makedirs(f"{BASE_DIR}/flagged", exist_ok=True)


def generate_key():
    return Fernet.generate_key()


def store_encrypted(file_obj, prefix="incoming"):
    """
    Encrypt a file using a unique per-file key.
    Store both the encrypted file and its key.
    """
    file_id = str(uuid.uuid4())
    enc_key = generate_key()
    fernet = Fernet(enc_key)

    # Paths
    enc_path = f"{BASE_DIR}/{prefix}/{file_id}.csv.enc"
    key_path = f"{BASE_DIR}/{prefix}/{file_id}.key"

    print(f"[DEBUG] store_encrypted file_id: {file_id}")
    print(f"[DEBUG] Storing encrypted file at: {enc_path}")
    print(f"[DEBUG] Storing key file at: {key_path}")

    # Encrypt data
    data = file_obj.read()
    encrypted = fernet.encrypt(data)

    # Save encrypted file
    with open(enc_path, "wb") as f:
        f.write(encrypted)

    # Save key
    with open(key_path, "wb") as f:
        f.write(enc_key)

    print(f"[DEBUG] Encryption and storage complete.")
    print(f"[DEBUG] Returning key: {prefix}/{file_id}.csv.enc")

    # Return both pieces
    return f"{prefix}/{file_id}.csv.enc"


def _get_key_path(enc_key: str):
    key_base = enc_key.replace(".csv.enc", ".key")
    return f"{BASE_DIR}/{key_base}"


def load_decrypted(enc_key: str):
    """
    Decrypt a per-file encrypted blob using its matching key file.
    """
    print(f"[DEBUG] load_decrypted received: {enc_key}")

    enc_path = f"{BASE_DIR}/{enc_key}"
    key_path = _get_key_path(enc_key)

    print(f"[DEBUG] Encrypted path: {enc_path}")
    print(f"[DEBUG] Key path: {key_path}")  

    if not os.path.exists(enc_path):
        raise FileNotFoundError(f"Encrypted file not found at: {enc_path}")

    if not os.path.exists(key_path):
        raise FileNotFoundError(f"Key file not found at: {key_path}")

    # Load key
    with open(key_path, "rb") as f:
        key = f.read()
    fernet = Fernet(key)

    # Load encrypted data
    with open(enc_path, "rb") as f:
        encrypted = f.read()

    print(f"[DEBUG] Decryption OK — returning raw bytes")

    # Decrypt
    return fernet.decrypt(encrypted)


def write_encrypted_output(data: bytes, prefix="flagged"):
    """
    Encrypt ML output using a *new* per-file key.
    Returns <prefix>/<uuid>.csv.enc
    """
    file_id = str(uuid.uuid4())
    enc_key = generate_key()
    fernet = Fernet(enc_key)

    enc_path = f"{BASE_DIR}/{prefix}/{file_id}.csv.enc"
    key_path = f"{BASE_DIR}/{prefix}/{file_id}.key"

    encrypted = fernet.encrypt(data)

    # Save encrypted output
    with open(enc_path, "wb") as f:
        f.write(encrypted)

    # Save the per-file key
    with open(key_path, "wb") as f:
        f.write(enc_key)

    return f"{prefix}/{file_id}.csv.enc"


def delete_key(enc_key: str):
    """
    Delete both the encrypted file and key file.
    """
    enc_path = f"{BASE_DIR}/{enc_key}"
    key_path = _get_key_path(enc_key)

    if os.path.exists(enc_path):
        os.remove(enc_path)

    if os.path.exists(key_path):
        os.remove(key_path)
