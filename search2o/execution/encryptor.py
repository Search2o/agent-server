# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

import base64
import os
from typing import TYPE_CHECKING

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from starlette.requests import Request

from search2o.common.exceptions import ShowMessage, error_message
from search2o.models.systemconfig import EncryptionSource

if TYPE_CHECKING:
    from search2o.execution.runtime import RuntimeState


class Encryptor:
    NONCE_SIZE: int = 12

    Encrypt_Agent_State_Func = "encrypt"
    Decrypt_Agent_State_Func = "decrypt"

    _current_encrypted_key: str | None = None
    _known_keys: dict[str, bytes] = {} # Encrypted key to plaintext key mapping

    @staticmethod
    def bytes2str(b: bytes) -> str:
        return base64.b64encode(b).decode("ascii")

    @staticmethod
    def str2bytes(s: str) -> bytes:
        return base64.b64decode(s.encode("ascii"))

    @staticmethod
    def is_valid_key(k: str | bytes) -> bool:
        if k:
            try:
                _ = AESGCM(k)
                return True
            except Exception:
                ...
        return False


    @classmethod
    async def _get_encryption_key(cls, request: Request | None, encrypted_key: str) -> bytes:
        from search2o.common.rest_call import RestCall
        k = cls._known_keys.get(encrypted_key)
        if k:
            return k
        else:
            kstr = (await RestCall.call_method(request, "getPlaintextKey", {"encryptedKey": encrypted_key})).get("plaintextKey")
            k = cls.str2bytes(kstr)
            cls._known_keys[encrypted_key] = k
            return k

    CLIENT_ENCRYPTION_MARKER = "C"
    SERVER_ENCRYPTION_MARKER = "S"

    @classmethod
    def _split_marker(cls, s: str) -> tuple[str, str, str, str]:
        parts: list[str] = s.split("|")
        if len(parts) != 4:
            raise ShowMessage("Encryption is not in the right format.")
        marker, version, key_to_key, payload = parts
        return marker, version, key_to_key, payload

    @classmethod
    async def _get_current_encrypted_key(cls, request: Request) -> str:
        from search2o.common.rest_call import RestCall
        if not cls._current_encrypted_key:
            cls._current_encrypted_key = (await RestCall.call_method(request, "getCurrentEncryptedKey", {})).get("encryptedKey")
        return cls._current_encrypted_key


    @classmethod
    async def encrypt(
            cls,
            request: Request | None,
            runtime: RuntimeState,
            plaintext: str
    ) -> str:
        try:
            model = runtime.encryption_model
            if model.encryptionSource == EncryptionSource.client:
                marker = cls.CLIENT_ENCRYPTION_MARKER
                try:
                    key_to_key: str = model.keys[-1].keyName
                except IndexError:
                    raise ShowMessage("No encryption key defined")
                kf = runtime.allowlist.eval_allowlist.get(model.keyFunction)
                if kf:
                    key = await kf(key_to_key)
                else:
                    raise ShowMessage("Unexpected encryption error - Bad key function")
            else:
                marker = cls.SERVER_ENCRYPTION_MARKER
                key_to_key: str = await cls._get_current_encrypted_key(request)
                key = await cls._get_encryption_key(request, key_to_key)

            aesgcm = AESGCM(key)
            nonce = os.urandom(cls.NONCE_SIZE)
            ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
            return f"{marker}|1|{key_to_key}|{cls.bytes2str(nonce + ct)}"
        except ShowMessage:
            raise
        except Exception as e:
            raise ShowMessage(f"Unexpected encryption error: {error_message(e)}")

    @classmethod
    def _aesgcm_decrypt_to_text(cls, key: bytes, token_bytes: bytes) -> str:
        min_len = cls.NONCE_SIZE + 16  # nonce + GCM tag
        if len(token_bytes) < min_len:
            raise ShowMessage("Unexpected decryption error - Bad length")

        nonce = token_bytes[: cls.NONCE_SIZE]
        ciphertext = token_bytes[cls.NONCE_SIZE :]
        aesgcm = AESGCM(key)
        pt = aesgcm.decrypt(nonce, ciphertext, None)
        return pt.decode("utf-8")

    @classmethod
    async def decrypt(
            cls,
            request: Request | None,
            runtime: RuntimeState,
            encrypted_text: str
    ) -> str:
        try:
            marker, version, key_to_key, payload = cls._split_marker(encrypted_text)
            if marker == cls.CLIENT_ENCRYPTION_MARKER:
                kf = runtime.allowlist.eval_allowlist.get(runtime.encryption_model.keyFunction)
                if kf:
                    key = await kf(key_to_key)
                else:
                    raise ShowMessage("Unexpected encryption error - Bad key function")
            else:
                key = await cls._get_encryption_key(request, key_to_key)

            token_bytes = cls.str2bytes(payload)
            return cls._aesgcm_decrypt_to_text(key, token_bytes)

        except ShowMessage:
            raise
        except Exception as e:
            raise ShowMessage(f"Unexpected decryption error: {error_message(e)}")

    @classmethod
    async def decrypt_query(
            cls,
            request: Request,
            encrypted_text: str
    ) -> str:
        from search2o.execution.runtime import Runtime
        return await cls.decrypt(request, Runtime.current(), encrypted_text)

    @classmethod
    async def encrypt_query(
            cls,
            request: Request,
            plaintext: str
    ) -> str:
        from search2o.execution.runtime import Runtime
        return await cls.encrypt(request, Runtime.current(), plaintext)
