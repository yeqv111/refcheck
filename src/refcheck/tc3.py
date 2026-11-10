"""腾讯云 API 3.0 客户端（TC3-HMAC-SHA256 签名），仅用标准库。

不依赖 tencentcloud-sdk-python，目的是让这个工具在任何 Python 3.8+ 环境
下都能直接跑起来，不用装包。

签名规范参考腾讯云文档《签名方法 v3》。
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request

HOST = "wsa.tencentcloudapi.com"
SERVICE = "wsa"
VERSION = "2025-05-08"
ACTION = "SearchPro"
ALGORITHM = "TC3-HMAC-SHA256"
CONTENT_TYPE = "application/json; charset=utf-8"


class APIError(RuntimeError):
    """腾讯云接口返回的业务错误。"""

    def __init__(self, code: str, message: str, request_id: str = "") -> None:
        self.code = code
        self.message = message
        self.request_id = request_id
        super().__init__(f"[{code}] {message}" + (f" (RequestId={request_id})" if request_id else ""))


def _hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def sign_headers(secret_id: str, secret_key: str, action: str, payload: str, timestamp: int | None = None) -> dict:
    """按 TC3-HMAC-SHA256 生成请求头。"""
    ts = timestamp or int(time.time())
    date = time.strftime("%Y-%m-%d", time.gmtime(ts))

    canonical_headers = f"content-type:{CONTENT_TYPE}\nhost:{HOST}\nx-tc-action:{action.lower()}\n"
    signed_headers = "content-type;host;x-tc-action"
    hashed_payload = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    canonical_request = "\n".join(
        ["POST", "/", "", canonical_headers, signed_headers, hashed_payload]
    )
    scope = f"{date}/{SERVICE}/tc3_request"
    string_to_sign = "\n".join(
        [
            ALGORITHM,
            str(ts),
            scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )

    k_date = _hmac_sha256(("TC3" + secret_key).encode("utf-8"), date)
    k_service = _hmac_sha256(k_date, SERVICE)
    k_signing = _hmac_sha256(k_service, "tc3_request")
    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = (
        f"{ALGORITHM} Credential={secret_id}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    return {
        "Authorization": authorization,
        "Content-Type": CONTENT_TYPE,
        "Host": HOST,
        "X-TC-Action": action,
        "X-TC-Timestamp": str(ts),
        "X-TC-Version": VERSION,
    }


def call(secret_id: str, secret_key: str, params: dict, timeout: int = 15) -> dict:
    """调用 SearchPro，返回 Response 字典。"""
    body = json.dumps({k: v for k, v in params.items() if v is not None}, ensure_ascii=False)
    headers = sign_headers(secret_id, secret_key, ACTION, body)
    req = urllib.request.Request(
        f"https://{HOST}", data=body.encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")
        try:
            err = json.loads(detail)["Response"]["Error"]
            raise APIError(err.get("Code", ""), err.get("Message", ""), err.get("RequestId", "")) from None
        except (KeyError, ValueError):
            raise APIError(f"HTTP{exc.code}", detail[:200]) from None
    except urllib.error.URLError as exc:
        raise APIError("NetworkError", str(exc.reason)) from None

    payload = result.get("Response", {})
    if "Error" in payload:
        err = payload["Error"]
        raise APIError(err.get("Code", ""), err.get("Message", ""), err.get("RequestId", ""))
    return payload
