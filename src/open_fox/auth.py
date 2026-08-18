"""用户认证模块：JWT 令牌 + 用户存储。

纯 stdlib 实现 JWT（HS256），无第三方依赖。
用户数据存储在 data/users.json 中。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# User model
# ---------------------------------------------------------------------------

@dataclass
class User:
    """用户数据模型。"""

    username: str
    password_hash: str
    display_name: str = ""
    created_at: str = ""


# ---------------------------------------------------------------------------
# JWT (HS256) — pure stdlib
# ---------------------------------------------------------------------------

class JWT:
    """简易 JWT 实现（HS256），纯 stdlib，无第三方依赖。"""

    def __init__(self, secret: str):
        self._secret = secret.encode()

    @staticmethod
    def _b64url_encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    @staticmethod
    def _b64url_decode(s: str) -> bytes:
        padding = 4 - len(s) % 4
        if padding != 4:
            s += "=" * padding
        return base64.urlsafe_b64decode(s)

    def encode(self, payload: dict, expire_seconds: int = 86400 * 7) -> str:
        """生成 JWT token，默认有效期 7 天。"""
        now = time.time()
        payload.setdefault("iat", now)
        payload.setdefault("exp", now + expire_seconds)
        header_b64 = self._b64url_encode(
            json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode()
        )
        body_b64 = self._b64url_encode(
            json.dumps(payload, separators=(",", ":")).encode()
        )
        sig_b64 = self._b64url_encode(
            hmac.new(
                self._secret,
                f"{header_b64}.{body_b64}".encode(),
                hashlib.sha256,
            ).digest()
        )
        return f"{header_b64}.{body_b64}.{sig_b64}"

    def decode(self, token: str) -> dict | None:
        """解码并验证 JWT token，失败返回 None。"""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None
            header_b64, body_b64, sig_b64 = parts
            expected_sig = self._b64url_encode(
                hmac.new(
                    self._secret,
                    f"{header_b64}.{body_b64}".encode(),
                    hashlib.sha256,
                ).digest()
            )
            if not hmac.compare_digest(sig_b64, expected_sig):
                return None
            payload = json.loads(self._b64url_decode(body_b64))
            if payload.get("exp", 0) < time.time():
                return None
            return payload
        except Exception:
            return None


# ---------------------------------------------------------------------------
# UserStore — JSON file backed
# ---------------------------------------------------------------------------

class UserStore:
    """用户存储（JSON 文件），支持 CRUD + 密码校验。"""

    def __init__(self, data_dir: str | Path, salt: str = "openfox_auth_salt_v1"):
        self._path = Path(data_dir) / "users.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._salt = salt
        if not self._path.exists():
            self._save({})
            logger.info("用户存储已创建：%s", self._path)

    # -- persistence --------------------------------------------------------

    def _load(self) -> dict:
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _save(self, data: dict) -> None:
        self._path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # -- hashing ------------------------------------------------------------

    def _hash_password(self, password: str) -> str:
        return hashlib.sha256(f"{self._salt}:{password}".encode()).hexdigest()

    # -- public API ---------------------------------------------------------

    def create_user(
        self, username: str, password: str, display_name: str = ""
    ) -> User:
        """创建新用户。"""
        users = self._load()
        if username in users:
            raise ValueError(f"用户 '{username}' 已存在")
        user_data = {
            "username": username,
            "password_hash": self._hash_password(password),
            "display_name": display_name or username,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        users[username] = user_data
        self._save(users)
        logger.info("用户已创建：%s", username)
        return User(**user_data)

    def verify(self, username: str, password: str) -> User | None:
        """验证用户名和密码，成功返回 User，失败返回 None。"""
        users = self._load()
        data = users.get(username)
        if data is None:
            return None
        if data["password_hash"] != self._hash_password(password):
            return None
        return User(**data)

    def get(self, username: str) -> User | None:
        users = self._load()
        data = users.get(username)
        return User(**data) if data else None

    def list_users(self) -> list[User]:
        users = self._load()
        return [User(**data) for data in users.values()]

    def update_password(self, username: str, new_password: str) -> None:
        users = self._load()
        if username not in users:
            raise ValueError(f"用户 '{username}' 不存在")
        users[username]["password_hash"] = self._hash_password(new_password)
        self._save(users)

    def delete_user(self, username: str) -> None:
        users = self._load()
        if username not in users:
            raise ValueError(f"用户 '{username}' 不存在")
        del users[username]
        self._save(users)
