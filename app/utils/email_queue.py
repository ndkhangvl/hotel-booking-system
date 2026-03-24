from __future__ import annotations

import asyncio
from contextlib import suppress

from app.core.config import settings
from app.utils.email import send_booking_confirmation_email


_email_queue: asyncio.Queue[dict] = asyncio.Queue()
_email_worker_task: asyncio.Task | None = None


async def _email_worker() -> None:
    while True:
        first_item = await _email_queue.get()
        batch: list[dict] = [first_item]

        for _ in range(max(0, settings.EMAIL_QUEUE_BATCH_SIZE - 1)):
            try:
                batch.append(_email_queue.get_nowait())
            except asyncio.QueueEmpty:
                break

        for email_payload in batch:
            try:
                await asyncio.to_thread(send_booking_confirmation_email, email_payload)
            except Exception as exc:
                print(f"[booking-email-queue] Failed to send email: {exc}")
            finally:
                _email_queue.task_done()

        if settings.EMAIL_QUEUE_BATCH_DELAY_SECONDS > 0:
            await asyncio.sleep(settings.EMAIL_QUEUE_BATCH_DELAY_SECONDS)


def start_email_queue_worker() -> None:
    global _email_worker_task

    if _email_worker_task and not _email_worker_task.done():
        return

    _email_worker_task = asyncio.create_task(_email_worker())
    print("[booking-email-queue] Worker started")


async def stop_email_queue_worker() -> None:
    global _email_worker_task

    if not _email_worker_task:
        return

    _email_worker_task.cancel()
    with suppress(asyncio.CancelledError):
        await _email_worker_task
    _email_worker_task = None
    print("[booking-email-queue] Worker stopped")


async def enqueue_booking_confirmation_email(booking: dict) -> None:
    # await _email_queue.put(booking)
    print(f"[booking-email-queue] Enqueued booking email: {booking.get('booking_code') or booking.get('booking_id')}")