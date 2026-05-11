from flask import Blueprint, current_app, g, request

from app.decorators import require_auth
from app.errors import AppError
from app.extensions import db
from app.repositories import NotificationRepository
from app.schemas import BookingConfirmationEmailSchema
from app.services.email_service import EmailService

bp = Blueprint("notifications", __name__, url_prefix="/notifications")


def notification_to_dict(notification):
    return {
        "id": str(notification.id),
        "user_id": str(notification.user_id),
        "title": notification.title,
        "message": notification.message,
        "tone": notification.tone,
        "read": notification.read,
        "link": notification.link,
        "created_at": notification.created_at.isoformat(),
    }


@bp.get("")
@require_auth()
def list_notifications():
    """List notifications for the current user."""
    repo = NotificationRepository()
    notifications = repo.list_for_user(g.current_user.id)
    return [notification_to_dict(n) for n in notifications]


@bp.get("/unread-count")
@require_auth()
def unread_count():
    """Get unread notification count for the current user."""
    repo = NotificationRepository()
    count = repo.count_unread(g.current_user.id)
    return {"count": count}


@bp.post("/booking-confirmation-email")
@require_auth()
def send_booking_confirmation_email():
    """Email QR tickets and booking details to the current user."""
    if not g.current_user.email:
        raise AppError("EMAIL_NOT_AVAILABLE", "Current user does not have an email address.", 400)
    data = BookingConfirmationEmailSchema().load(request.get_json(silent=True) or {})
    EmailService(current_app.config["APP_CONFIG"]).send_booking_confirmation(g.current_user.email, data)
    return {"message": "Booking confirmation email sent."}


@bp.patch("/<uuid:notification_id>/read")
@require_auth()
def mark_read(notification_id):
    """Mark a notification as read."""
    repo = NotificationRepository()
    notification = repo.get_by_id(notification_id)
    if notification is None:
        raise AppError("NOT_FOUND", "Notification was not found.", 404)
    if notification.user_id != g.current_user.id:
        raise AppError("FORBIDDEN", "You can only manage your own notifications.", 403)

    repo.mark_read(notification)
    db.session.commit()
    return notification_to_dict(notification)


@bp.patch("/read-all")
@require_auth()
def mark_all_read():
    """Mark all notifications as read for the current user."""
    from app.models import Notification
    Notification.query.filter_by(user_id=g.current_user.id, read=False).update({"read": True})
    db.session.commit()
    return {"status": "ok"}


@bp.delete("/<uuid:notification_id>")
@require_auth()
def delete_notification(notification_id):
    """Delete a notification."""
    repo = NotificationRepository()
    notification = repo.get_by_id(notification_id)
    if notification is None:
        raise AppError("NOT_FOUND", "Notification was not found.", 404)
    if notification.user_id != g.current_user.id:
        raise AppError("FORBIDDEN", "You can only manage your own notifications.", 403)

    repo.delete(notification)
    db.session.commit()
    return "", 204


@bp.delete("/all")
@require_auth()
def delete_all_notifications():
    """Delete all notifications for the current user."""
    repo = NotificationRepository()
    repo.delete_all_for_user(g.current_user.id)
    db.session.commit()
    return "", 204
