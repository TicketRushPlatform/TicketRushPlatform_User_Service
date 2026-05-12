import io
import logging
import socket
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from html import escape

import qrcode


class EmailService:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)

    def send_password_reset(self, to_email: str, reset_url: str, full_name: str | None = None) -> bool:
        name = full_name or "TicketRush user"
        html = f"""
        <div style="font-family:Arial,sans-serif;line-height:1.5;color:#111827">
          <h2>Reset your TicketRush password</h2>
          <p>Hi {escape(name)},</p>
          <p>Use the button below to set a new password. This link expires soon.</p>
          <p><a href="{escape(reset_url)}" style="display:inline-block;padding:12px 18px;background:#111827;color:#fff;text-decoration:none;border-radius:8px">Reset password</a></p>
          <p>If you did not request this, you can ignore this email.</p>
        </div>
        """
        text = f"Hi {name},\n\nReset your TicketRush password: {reset_url}\n\nIf you did not request this, ignore this email."
        return self._send(to_email, "Reset your TicketRush password", text, html)

    def send_booking_confirmation(self, to_email: str, payload: dict) -> bool:
        event = payload.get("event") or {}
        showtime = payload.get("showtime") or {}
        booking = payload.get("booking") or {}
        seats = payload.get("seats") or []
        tickets = payload.get("tickets") or []

        event_name = str(event.get("name") or "TicketRush event")
        seat_labels = ", ".join(str(seat.get("label") or "") for seat in seats if seat.get("label")) or "See ticket details"
        total_amount = str(booking.get("total_amount") or "")
        showtime_line = " ".join(
            value
            for value in [
                str(showtime.get("date") or ""),
                str(showtime.get("time") or ""),
                str(showtime.get("venue") or ""),
            ]
            if value
        )

        attachments = []
        ticket_rows = []
        for index, ticket in enumerate(tickets, start=1):
            code = str(ticket.get("ticket_code") or f"Ticket {index}")
            qr_payload = str(ticket.get("qr_payload") or code)
            content_id = f"ticket-{index}-qr"
            attachments.append((content_id, self._qr_png(qr_payload)))
            ticket_rows.append(
                f"""
                <tr>
                  <td style="padding:12px;border-top:1px solid #e5e7eb">{escape(code)}</td>
                  <td style="padding:12px;border-top:1px solid #e5e7eb"><img src="cid:{content_id}" width="144" height="144" alt="QR code for {escape(code)}" /></td>
                </tr>
                """
            )

        html = f"""
        <div style="font-family:Arial,sans-serif;line-height:1.5;color:#111827">
          <h2>Booking confirmed</h2>
          <p>Your TicketRush checkout for <strong>{escape(event_name)}</strong> was successful.</p>
          <ul>
            <li><strong>Booking:</strong> {escape(str(booking.get("id") or ""))}</li>
            <li><strong>Showtime:</strong> {escape(showtime_line)}</li>
            <li><strong>Seats:</strong> {escape(seat_labels)}</li>
            <li><strong>Total:</strong> {escape(total_amount)}</li>
          </ul>
          <table style="border-collapse:collapse;margin-top:16px">
            <tbody>{''.join(ticket_rows)}</tbody>
          </table>
        </div>
        """
        text = (
            f"Booking confirmed\n\nEvent: {event_name}\nBooking: {booking.get('id') or ''}\n"
            f"Showtime: {showtime_line}\nSeats: {seat_labels}\nTotal: {total_amount}\n"
        )
        return self._send(to_email, f"Your TicketRush tickets for {event_name}", text, html, attachments)

    def _send(self, to_email: str, subject: str, text: str, html: str, inline_pngs: list[tuple[str, bytes]] | None = None) -> bool:
        if not getattr(self.config, "SMTP_HOST", ""):
            self.logger.info("SMTP is not configured; email skipped", extra={"to": to_email, "subject": subject})
            return False

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = formataddr((getattr(self.config, "SMTP_FROM_NAME", "TicketRush"), self.config.SMTP_FROM_EMAIL))
        message["To"] = to_email
        message.set_content(text)
        message.add_alternative(html, subtype="html")

        html_part = message.get_payload()[-1]
        for content_id, data in inline_pngs or []:
            html_part.add_related(data, maintype="image", subtype="png", cid=f"<{content_id}>")

        try:
            with smtplib.SMTP(self.config.SMTP_HOST, self.config.SMTP_PORT, timeout=10) as smtp:
                if getattr(self.config, "SMTP_USE_TLS", True):
                    smtp.starttls()
                if getattr(self.config, "SMTP_USERNAME", ""):
                    smtp.login(self.config.SMTP_USERNAME, self.config.SMTP_PASSWORD)
                smtp.send_message(message)
        except (OSError, TimeoutError, socket.timeout, smtplib.SMTPException) as exc:
            self.logger.warning(
                "Email delivery failed",
                extra={
                    "to": to_email,
                    "subject": subject,
                    "smtp_host": getattr(self.config, "SMTP_HOST", ""),
                    "smtp_port": getattr(self.config, "SMTP_PORT", ""),
                    "error": str(exc),
                },
            )
            return False

        return True

    @staticmethod
    def _qr_png(payload: str) -> bytes:
        image = qrcode.make(payload)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()
