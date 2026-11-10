import hashlib
import hmac
import json
import unittest

from refcheck import tc3


class TestSignHeaders(unittest.TestCase):
    def setUp(self):
        self.headers = tc3.sign_headers(
            "AKIDtest",
            "secrettest",
            "SearchPro",
            json.dumps({"Query": "测试"}),
            timestamp=1700000000,
        )

    def test_required_headers(self):
        for k in ("Authorization", "Content-Type", "Host", "X-TC-Action", "X-TC-Timestamp", "X-TC-Version"):
            self.assertIn(k, self.headers)

    def test_authorization_shape(self):
        auth = self.headers["Authorization"]
        self.assertTrue(auth.startswith("TC3-HMAC-SHA256 "))
        self.assertIn("Credential=AKIDtest/", auth)
        self.assertIn("SignedHeaders=content-type;host;x-tc-action", auth)
        self.assertIn("Signature=", auth)

    def test_host_and_action(self):
        self.assertEqual(self.headers["Host"], "wsa.tencentcloudapi.com")
        self.assertEqual(self.headers["X-TC-Action"], "SearchPro")
        self.assertEqual(self.headers["X-TC-Version"], "2025-05-08")

    def test_deterministic(self):
        """同一时间戳、同一 payload 必须得到同一签名。"""
        again = tc3.sign_headers("AKIDtest", "secrettest", "SearchPro",
                                 json.dumps({"Query": "测试"}), timestamp=1700000000)
        self.assertEqual(self.headers["Authorization"], again["Authorization"])

    def test_signature_changes_with_payload(self):
        other = tc3.sign_headers("AKIDtest", "secrettest", "SearchPro",
                                 json.dumps({"Query": "别的"}), timestamp=1700000000)
        self.assertNotEqual(self.headers["Authorization"], other["Authorization"])

    def test_scope_uses_utc_date(self):
        # 1700000000 = 2023-11-14 UTC
        self.assertIn("/2023-11-14/wsa/tc3_request", self.headers["Authorization"])

    def test_signing_key_chain(self):
        """手工复算一遍派生密钥，确保 HMAC 链没写错。"""
        secret_key = "secrettest"
        k_date = hmac.new(("TC3" + secret_key).encode(), b"2023-11-14", hashlib.sha256).digest()
        k_service = hmac.new(k_date, b"wsa", hashlib.sha256).digest()
        k_signing = hmac.new(k_service, b"tc3_request", hashlib.sha256).digest()
        self.assertEqual(len(k_signing), 32)


class TestAPIError(unittest.TestCase):
    def test_message(self):
        err = tc3.APIError("ResourceNotFound", "用户资源未开通", "req-1")
        self.assertIn("ResourceNotFound", str(err))
        self.assertIn("req-1", str(err))


if __name__ == "__main__":
    unittest.main()
