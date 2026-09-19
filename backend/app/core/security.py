"""Password and signed-token helpers."""
from datetime import datetime, timedelta, timezone
import base64, hashlib, hmac, json, os
from app.core.config import get_settings

def hash_password(password: str) -> str:
    salt=os.urandom(16); rounds=310_000
    digest=hashlib.pbkdf2_hmac("sha256",password.encode(),salt,rounds)
    return f"pbkdf2_sha256${rounds}${salt.hex()}${digest.hex()}"
def verify_password(password: str, encoded: str) -> bool:
    try:
        _, rounds, salt, digest=encoded.split("$"); candidate=hashlib.pbkdf2_hmac("sha256",password.encode(),bytes.fromhex(salt),int(rounds))
        return hmac.compare_digest(candidate.hex(),digest)
    except ValueError: return False
def make_token(merchant_id: int, token_type: str, expires: timedelta) -> str:
    settings=get_settings(); now=datetime.now(timezone.utc)
    header=_b64(json.dumps({"alg":"HS256","typ":"JWT"}).encode())
    body=_b64(json.dumps({"sub":str(merchant_id),"typ":token_type,"iat":int(now.timestamp()),"exp":int((now+expires).timestamp())}).encode())
    signing=f"{header}.{body}".encode(); sig=_b64(hmac.new(settings.JWT_SECRET.encode(),signing,hashlib.sha256).digest())
    return f"{header}.{body}.{sig}"
def access_token(merchant_id:int)->str: return make_token(merchant_id,"access",timedelta(minutes=get_settings().ACCESS_TOKEN_MINUTES))
def refresh_token(merchant_id:int)->str: return make_token(merchant_id,"refresh",timedelta(days=get_settings().REFRESH_TOKEN_DAYS))
def _b64(value:bytes)->str: return base64.urlsafe_b64encode(value).rstrip(b"=").decode()
def decode_token(token:str)->dict:
    try:
        header, body, sig=token.split("."); expected=_b64(hmac.new(get_settings().JWT_SECRET.encode(),f"{header}.{body}".encode(),hashlib.sha256).digest())
        if not hmac.compare_digest(sig,expected): raise ValueError("invalid signature")
        payload=json.loads(base64.urlsafe_b64decode(body+"="*(-len(body)%4)))
        if int(payload["exp"]) < int(datetime.now(timezone.utc).timestamp()): raise ValueError("expired")
        return payload
    except (ValueError,KeyError,json.JSONDecodeError): raise ValueError("invalid token")
