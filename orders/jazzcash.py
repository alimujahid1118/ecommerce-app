"""
JazzCash hosted checkout (HTTP POST redirect).

Hash algorithm matches the common PHP integration pattern (see zfhassaan/jazzcash
and JazzCash Payment Gateway Integration Guide). Configure credentials in settings
or environment variables; see main/settings.py.

Official docs: https://sandbox.jazzcash.com.pk/SandboxDocumentation/
"""

from __future__ import annotations

import hashlib
import hmac
import random
import string
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from django.conf import settings

PK_TZ = ZoneInfo("Asia/Karachi")


def is_configured() -> bool:
    return bool(
        getattr(settings, "JAZZCASH_MERCHANT_ID", "")
        and getattr(settings, "JAZZCASH_PASSWORD", "")
        and getattr(settings, "JAZZCASH_HASH_KEY", "")
        and _api_url()
    )


def _api_url() -> str:
    mode = getattr(settings, "JAZZCASH_MODE", "sandbox")
    if mode == "production":
        return getattr(settings, "JAZZCASH_PRODUCTION_URL", "")
    return getattr(settings, "JAZZCASH_SANDBOX_URL", "")


def _txn_datetime() -> tuple[str, str]:
    now = datetime.now(PK_TZ)
    txn = now.strftime("%Y%m%d%H%M%S")
    exp = (now + timedelta(days=getattr(settings, "JAZZCASH_TXN_EXPIRY_DAYS", 7))).strftime(
        "%Y%m%d%H%M%S"
    )
    return txn, exp


def _txn_ref() -> str:
    suffix = "".join(random.choices(string.digits, k=3))
    return f"TR{datetime.now(PK_TZ).strftime('%Y%m%d%H%M%S')}{suffix}"


def _amount_int(order_total: float) -> int:
    """PKR amount as integer minor units (last two digits are decimals)."""
    return int(round(float(order_total) * 100))


def compute_secure_hash(data: dict[str, Any], hash_key: str) -> str:
    """HMAC-SHA256 per JazzCash hosted-checkout hash ordering."""
    fields = [
        data.get("pp_Amount", ""),
        data.get("pp_BankID", ""),
        data.get("pp_BillReference", ""),
        data.get("pp_Description", ""),
        data.get("pp_IsRegisteredCustomer", ""),
        data.get("pp_Language", ""),
        data.get("pp_MerchantID", ""),
        data.get("pp_Password", ""),
        data.get("pp_ProductID", ""),
        data.get("pp_ReturnURL", ""),
        data.get("pp_TxnCurrency", ""),
        data.get("pp_TxnDateTime", ""),
        data.get("pp_TxnExpiryDateTime", ""),
        data.get("pp_TxnRefNo", ""),
        data.get("pp_TxnType", ""),
        data.get("pp_Version", ""),
        data.get("ppmpf_1", ""),
        data.get("ppmpf_2", ""),
        data.get("ppmpf_3", ""),
        data.get("ppmpf_4", ""),
        data.get("ppmpf_5", ""),
    ]
    msg = hash_key
    for value in fields:
        if value is None or value == "" or str(value).lower() == "undefined":
            continue
        msg += "&" + str(value)
    key = hash_key.encode("utf-8")
    body = msg.encode("utf-8")
    return hmac.new(key, body, hashlib.sha256).hexdigest()


def build_checkout_payload(
    *,
    order,
    mobile_number: str,
    return_url: str,
) -> tuple[str, dict[str, str]]:
    """
    Returns (post_url, flat form fields including pp_SecureHash).
    pp_BillReference is order.pk for matching on return.
    """
    merchant_id = settings.JAZZCASH_MERCHANT_ID
    password = settings.JAZZCASH_PASSWORD
    hash_key = settings.JAZZCASH_HASH_KEY

    txn_time, txn_exp = _txn_datetime()
    txn_ref = _txn_ref()
    amount = str(_amount_int(order.order_total))

    # Hosted checkout fields (see zfhassaan/jazzcash / JazzCash docs)
    data: dict[str, Any] = {
        "pp_Version": "1.1",
        "pp_TxnType": "",
        "pp_Language": "EN",
        "pp_MerchantID": merchant_id,
        "pp_SubMerchantID": "",
        "pp_Password": password,
        "pp_TxnRefNo": txn_ref,
        "pp_Amount": amount,
        "pp_TxnCurrency": "PKR",
        "pp_TxnDateTime": txn_time,
        "pp_BillReference": str(order.pk),
        "pp_Description": f"Order {order.order_number}"[:200],
        "pp_IsRegisteredCustomer": "No",
        "pp_BankID": "",
        "pp_ProductID": "",
        "pp_TxnExpiryDateTime": txn_exp,
        "pp_ReturnURL": return_url,
        "ppmpf_1": mobile_number.replace(" ", "").strip(),
        "ppmpf_2": "",
        "ppmpf_3": "",
        "ppmpf_4": "",
        "ppmpf_5": "",
    }
    data["pp_SecureHash"] = compute_secure_hash(data, hash_key)
    flat = {k: str(v) if v is not None else "" for k, v in data.items()}
    return _api_url(), flat
