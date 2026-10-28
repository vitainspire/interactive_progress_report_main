from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.config import WHATSAPP_TEMPLATE_NAME
from app.core.deps import get_current_user
from app.integrations import sms, whatsapp
from app.integrations.phone import InvalidPhoneNumber, normalize_phone

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/status")
def status(current_user=Depends(get_current_user)):
    """Whether WhatsApp/SMS are wired up on this server right now — lets the
    UI show real status instead of making you guess or try a send to find
    out. whatsapp_template_lang reflects THIS school's own saved choice
    (see PUT /auth/whatsapp-settings), not a single global value — the
    template name is the only part still shared platform-wide."""
    return {
        "whatsapp_configured": whatsapp.is_configured(),
        "whatsapp_template_name": WHATSAPP_TEMPLATE_NAME,
        "whatsapp_template_lang": current_user["whatsapp_language"],
        "sms_configured": sms.is_configured(),
    }


class TestSendRequest(BaseModel):
    phone: str
    channel: Literal["whatsapp", "sms"]


@router.post("/test-send")
def test_send(req: TestSendRequest, current_user=Depends(get_current_user)):
    """Sends one real message using fake placeholder data (no real student
    or batch involved) — for confirming the provider credentials actually
    work the moment they're set, without needing a real upload first. Uses
    this account's own saved language/country-code settings, same as a
    real send would."""
    try:
        phone = normalize_phone(req.phone, current_user["default_country_code"])
    except InvalidPhoneNumber as exc:
        raise HTTPException(422, str(exc))

    if req.channel == "whatsapp":
        try:
            whatsapp.send_report_whatsapp(phone, "Test Student", "test-token", language=current_user["whatsapp_language"])
        except whatsapp.WhatsAppNotConfigured as exc:
            raise HTTPException(422, str(exc))
        except whatsapp.WhatsAppSendError as exc:
            raise HTTPException(502, str(exc))
    else:
        try:
            sms.send_report_sms(phone, "Test Student", "https://example.com/test-report-link")
        except sms.SmsNotConfigured as exc:
            raise HTTPException(422, str(exc))
        except sms.SmsSendError as exc:
            raise HTTPException(502, str(exc))

    return {"ok": True}
