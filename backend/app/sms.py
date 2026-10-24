import base64
import logging
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import settings

logger = logging.getLogger(__name__)


class SmsConfigurationError(RuntimeError):
    pass


class SmsDeliveryError(RuntimeError):
    pass


def send_twilio_sms(phone_number: str, message: str) -> None:
    account_sid = settings.TWILIO_ACCOUNT_SID.strip()
    auth_token = settings.TWILIO_AUTH_TOKEN.strip()
    messaging_service_sid = settings.TWILIO_MESSAGING_SERVICE_SID.strip()
    from_number = settings.TWILIO_FROM_NUMBER.strip()
    if not account_sid or not auth_token or not (
        messaging_service_sid or from_number
    ):
        raise SmsConfigurationError(
            "Twilio SMS is not configured on the backend."
        )

    digits = re.sub(r"\D", "", phone_number)
    if not phone_number.strip().startswith("+") or not 8 <= len(digits) <= 15:
        raise SmsDeliveryError(
            "Use an international phone number beginning with +."
        )

    payload = {"To": f"+{digits}", "Body": message}
    if messaging_service_sid:
        payload["MessagingServiceSid"] = messaging_service_sid
    else:
        payload["From"] = from_number

    credentials = base64.b64encode(
        f"{account_sid}:{auth_token}".encode("utf-8")
    ).decode("ascii")
    request = Request(
        f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
        data=urlencode(payload).encode("utf-8"),
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=10) as response:
            if not 200 <= response.status < 300:
                raise SmsDeliveryError("The SMS provider rejected the message.")
    except HTTPError as error:
        logger.warning("Twilio rejected an SMS request with HTTP %s", error.code)
        raise SmsDeliveryError(
            "The SMS provider rejected the message."
        ) from error
    except (URLError, OSError) as error:
        logger.warning("Twilio SMS request failed: %s", type(error).__name__)
        raise SmsDeliveryError("The SMS provider could not be reached.") from error
