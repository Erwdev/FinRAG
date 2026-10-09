"""Pengiriman job ke SQS chat-jobs (Architecture.md 3.2). Worker mengklaim job secara atomik."""

import json

import boto3

from app.settings import get_settings


class QueueUnavailable(RuntimeError):
    pass


def enqueue_job(job_id: str) -> None:
    url = get_settings().sqs_queue_url
    if not url:
        raise QueueUnavailable("SQS_QUEUE_URL belum diset")
    try:
        boto3.client("sqs").send_message(QueueUrl=url, MessageBody=json.dumps({"job_id": job_id}))
    except Exception as exc:  # noqa: BLE001 - semua kegagalan AWS diperlakukan sama di sini
        raise QueueUnavailable(str(exc)) from exc
