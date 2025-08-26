import hmac
import hashlib
from fastapi import HTTPException, status
from config import settings

SIGNATURE_HEADER = "X-Broker-Signature"
ALGO_HEADER = "X-Broker-Signature-Alg"
EXPECTED_ALGO = "HMAC-SHA256"


def _candidate_secrets():
    base = []
    if settings.BROKER_WEBHOOK_SECRET:
        base.append(settings.BROKER_WEBHOOK_SECRET)
    if settings.BROKER_WEBHOOK_ADDITIONAL_SECRETS:
        base.extend([s.strip() for s in settings.BROKER_WEBHOOK_ADDITIONAL_SECRETS.split(',') if s.strip()])
    return base

def compute_signature(raw_body: bytes, secret: str | None = None) -> str:
    if secret is None:
        # Use primary if provided (callers for outgoing signing)
        secret = settings.BROKER_WEBHOOK_SECRET or ""
    return hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()


def verify_signature(raw_body: bytes, headers: dict):
    provided = headers.get(SIGNATURE_HEADER)
    algo = headers.get(ALGO_HEADER)
    if not provided:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing signature header")
    if algo and algo != EXPECTED_ALGO:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported signature algorithm")
    # Accept any current or additional (rotated) secret
    for candidate in _candidate_secrets():
        if hmac.compare_digest(compute_signature(raw_body, candidate), provided):
            return
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")
