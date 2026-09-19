import unittest
from app.core.security import access_token, decode_token, hash_password, verify_password

class SecurityTests(unittest.TestCase):
    def test_password_hash_is_salted_and_verifiable(self):
        digest=hash_password("merchant-password")
        self.assertTrue(verify_password("merchant-password",digest))
        self.assertFalse(verify_password("incorrect",digest))
    def test_access_token_round_trip(self):
        payload=decode_token(access_token(42))
        self.assertEqual(payload["sub"],"42")
        self.assertEqual(payload["typ"],"access")
