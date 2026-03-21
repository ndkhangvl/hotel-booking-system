from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape

from app.core.config import settings


CHECK_IN_TIME = "14:00"
CHECK_OUT_TIME = "12:00"


def _get_sender_email() -> str:
    return settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME


def _is_smtp_configured() -> bool:
    return all(
        [
            settings.SMTP_HOST,
            settings.SMTP_PORT,
      _get_sender_email(),
        ]
    )


def _build_booking_confirmation_html(booking: dict) -> str:
    customer_name = escape(booking.get("customer_name") or "Quý khách")
    booking_code = escape(booking.get("booking_code") or str(booking.get("booking_id") or ""))
    branch_name = escape(booking.get("branch_name") or "Aurora Hotel")
    room_type_name = escape(booking.get("room_type_name") or "Hạng phòng đã chọn")
    room_number = escape(booking.get("room_number") or "Sẽ được xác nhận sau")
    from_date = escape(str(booking.get("from_date") or ""))
    to_date = escape(str(booking.get("to_date") or ""))
    total_price = escape(str(booking.get("formatted_total_price") or booking.get("total_price") or ""))

    return f"""
<!DOCTYPE html>
<html lang="vi">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Xác nhận đặt phòng</title>
  </head>
  <body style="margin:0;padding:0;background:#f3f7f6;font-family:Arial,Helvetica,sans-serif;color:#0f172a;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f3f7f6;padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="640" cellspacing="0" cellpadding="0" style="max-width:640px;width:100%;background:#ffffff;border-radius:24px;overflow:hidden;box-shadow:0 18px 50px rgba(15,23,42,0.08);">
            <tr>
              <td style="background:linear-gradient(135deg,#0f766e,#34d399);padding:36px 40px;color:#ffffff;">
                <div style="font-size:13px;letter-spacing:2px;text-transform:uppercase;opacity:0.8;margin-bottom:12px;">Aurora Hotel</div>
                <div style="font-size:30px;font-weight:700;line-height:1.25;margin:0 0 10px;">Xác nhận đặt phòng thành công</div>
                <div style="font-size:16px;line-height:1.6;opacity:0.92;">Cảm ơn {customer_name} đã lựa chọn Aurora Hotel cho kỳ nghỉ sắp tới.</div>
              </td>
            </tr>

            <tr>
              <td style="padding:32px 40px 16px;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border:1px solid #d1fae5;border-radius:18px;background:#ecfdf5;">
                  <tr>
                    <td style="padding:20px 24px;">
                      <div style="font-size:13px;text-transform:uppercase;letter-spacing:1.6px;color:#065f46;margin-bottom:8px;">Mã đặt phòng</div>
                      <div style="font-size:28px;font-weight:800;color:#065f46;letter-spacing:1px;">{booking_code}</div>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

            <tr>
              <td style="padding:8px 40px 16px;">
                <div style="font-size:20px;font-weight:700;color:#0f172a;margin-bottom:16px;">Thông tin lưu trú</div>
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:separate;border-spacing:0 12px;">
                  <tr>
                    <td width="50%" style="padding:16px 18px;background:#f8fafc;border-radius:16px;vertical-align:top;">
                      <div style="font-size:12px;text-transform:uppercase;letter-spacing:1.4px;color:#64748b;margin-bottom:6px;">Chi nhánh</div>
                      <div style="font-size:16px;font-weight:700;color:#0f172a;">{branch_name}</div>
                    </td>
                    <td width="50%" style="padding:16px 18px;background:#f8fafc;border-radius:16px;vertical-align:top;">
                      <div style="font-size:12px;text-transform:uppercase;letter-spacing:1.4px;color:#64748b;margin-bottom:6px;">Loại phòng</div>
                      <div style="font-size:16px;font-weight:700;color:#0f172a;">{room_type_name}</div>
                      <div style="font-size:13px;color:#475569;margin-top:4px;">Phòng: {room_number}</div>
                    </td>
                  </tr>
                  <tr>
                    <td width="50%" style="padding:16px 18px;background:#f8fafc;border-radius:16px;vertical-align:top;">
                      <div style="font-size:12px;text-transform:uppercase;letter-spacing:1.4px;color:#64748b;margin-bottom:6px;">Check-in</div>
                      <div style="font-size:16px;font-weight:700;color:#0f172a;">{from_date}</div>
                      <div style="font-size:13px;color:#475569;margin-top:4px;">Từ {CHECK_IN_TIME}</div>
                    </td>
                    <td width="50%" style="padding:16px 18px;background:#f8fafc;border-radius:16px;vertical-align:top;">
                      <div style="font-size:12px;text-transform:uppercase;letter-spacing:1.4px;color:#64748b;margin-bottom:6px;">Check-out</div>
                      <div style="font-size:16px;font-weight:700;color:#0f172a;">{to_date}</div>
                      <div style="font-size:13px;color:#475569;margin-top:4px;">Trước {CHECK_OUT_TIME}</div>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

            <tr>
              <td style="padding:8px 40px 20px;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-top:1px solid #e2e8f0;padding-top:18px;">
                  <tr>
                    <td style="font-size:14px;color:#64748b;">Tổng tiền tạm tính</td>
                    <td align="right" style="font-size:22px;font-weight:800;color:#0f766e;">{total_price}</td>
                  </tr>
                </table>
              </td>
            </tr>

            <tr>
              <td style="padding:0 40px 28px;">
                <div style="padding:18px 20px;border-radius:16px;background:#fff7ed;color:#9a3412;font-size:14px;line-height:1.7;">
                  Vui lòng mang theo email này khi làm thủ tục nhận phòng. Nếu cần hỗ trợ thay đổi lịch lưu trú hoặc thông tin khách, hãy liên hệ trực tiếp với khách sạn sớm nhất có thể.
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:20px 40px 34px;border-top:1px solid #e2e8f0;color:#64748b;font-size:13px;line-height:1.7;">
                Aurora Hotel<br />
                Email này được gửi tự động từ hệ thống xác nhận đặt phòng.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""


def _build_booking_confirmation_text(booking: dict) -> str:
    booking_code = booking.get("booking_code") or booking.get("booking_id")
    branch_name = booking.get("branch_name") or "Aurora Hotel"
    room_type_name = booking.get("room_type_name") or "Hạng phòng đã chọn"
    room_number = booking.get("room_number") or "Sẽ được xác nhận sau"

    return (
        f"Xác nhận đặt phòng thành công\n\n"
        f"Mã đặt phòng: {booking_code}\n"
        f"Chi nhánh: {branch_name}\n"
        f"Loại phòng: {room_type_name}\n"
        f"Phòng: {room_number}\n"
        f"Check-in: {booking.get('from_date')} lúc {CHECK_IN_TIME}\n"
        f"Check-out: {booking.get('to_date')} trước {CHECK_OUT_TIME}\n"
        f"Tổng tiền: {booking.get('formatted_total_price') or booking.get('total_price')}\n"
    )


def send_booking_confirmation_email(booking: dict) -> None:
    if not _is_smtp_configured():
        print("[booking-email] SMTP is not configured; skip sending confirmation email")
        return

    recipient = booking.get("customer_email")
    if not recipient:
        print("[booking-email] Missing recipient email; skip sending confirmation email")
        return

    sender_email = _get_sender_email()

    message = MIMEMultipart("alternative")
    message["Subject"] = f"[Aurora Hotel] Xác nhận đặt phòng {booking.get('booking_code') or booking.get('booking_id')}"
    message["From"] = f"{settings.SMTP_FROM_NAME} <{sender_email}>"
    message["To"] = recipient

    message.attach(MIMEText(_build_booking_confirmation_text(booking), "plain", "utf-8"))
    message.attach(MIMEText(_build_booking_confirmation_html(booking), "html", "utf-8"))

    if settings.SMTP_USE_SSL:
      with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
        if settings.SMTP_USERNAME:
          server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.sendmail(sender_email, [recipient], message.as_string())
      return

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
      if settings.SMTP_USE_TLS:
        server.starttls()
      if settings.SMTP_USERNAME:
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
      server.sendmail(sender_email, [recipient], message.as_string())