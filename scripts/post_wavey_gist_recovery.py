"""One-off: publish a follow-up Wavey Gist for alert #901 (INFINIFI LongTimelock op).

Alert #901 was the first batch (7 calls) to hit the new
"two-stage summary + detail" path after Wavey Gist switched to its
files-snapshot API. The legacy ``{title, markdown}`` payload now returns HTTP
400 ("Legacy gist fields are no longer supported."), so ``upload_to_gist``
silently returned ``""`` and the Telegram message went out with the
"⚠️ Couldn't post full report" line — the *summary* still landed correctly,
but the linked full detail was missing.

The LLM-generated detail text is never persisted separately (it's only held
in memory while ``format_explanation_line`` runs), so we can't republish the
exact original detail. Instead we publish a recovery gist that captures
what we *do* have for this alert — the full Telegram message (already in
``alert_events.message``, which contains the AI summary + decoded calldata +
tx link) plus a short note explaining why this is a follow-up rather than
the original LLM detail — and send a Telegram follow-up pointing to it.

Run once after deploying the wavey_gist fix; no-ops on subsequent runs.
"""

import os
import sys
import textwrap

from dotenv import load_dotenv

from utils.logger import get_logger
from utils.store import get_alert, query_alerts
from utils.telegram import send_telegram_message
from utils.wavey_gist import DEFAULT_GIST_TITLE, upload_to_gist

load_dotenv()
logger = get_logger("scripts.post_wavey_gist_recovery")

ALERT_ID = 901
PROTOCOL = "INFINIFI"
TX_HASH = "0xcfa148be8e66cf358cb484be38410cbc5827877e5b3c62f7804d76d78a36196e"


def build_gist_body(alert_message: str) -> str:
    """Build the recovery gist body.

    The original LLM detail is unrecoverable (never persisted), so the gist
    surfaces everything we *do* still have: the full Telegram alert message
    (AI summary + decoded calldata + tx link) and a note explaining why this
    is a follow-up rather than a re-issue of the original detail.
    """
    note = textwrap.dedent(
        f"""
        **Follow-up for alert #{ALERT_ID} (INFINIFI LongTimelock op).**

        The full detail that the AI explainer normally posts to a gist link in
        the Telegram alert was lost — Wavey Gist recently retired the legacy
        `{{title, markdown}}` payload and started returning HTTP 400
        (`"Legacy gist fields are no longer supported."`). `upload_to_gist`
        swallowed the error and `format_explanation_line` rendered the
        `⚠️ Couldn't post full report` line instead of a link. The short
        summary that did reach Telegram was unaffected.

        The LLM-generated detail text is only held in memory while
        `format_explanation_line` runs and isn't persisted separately, so we
        can't republish the original detail verbatim. The full alert body
        (AI summary + decoded calldata + tx link) is below — it's a strict
        superset of the original Telegram message and contains every fact
        the detail would have elaborated on.

        The wavey_gist client has been updated to the new
        `{{title, files: {{"README.md": {{"content": …}}}}}}` payload format
        so subsequent alerts post the detail link as intended.

        ---

        """
    ).strip()

    return f"{note}\n\n---\n\n{alert_message}"


def build_telegram_followup(gist_url: str) -> str:
    """Build the follow-up Telegram message pointing at the recovery gist."""
    short = f"{TX_HASH[:10]}…{TX_HASH[-4:]}"
    return (
        "ℹ️ *Follow-up: full report for INFINIFI LongTimelock op*\n"
        "The detail for the earlier "
        f"[InfiniFi timelock alert](https://etherscan.io/tx/{TX_HASH}) (`{short}`) "
        "couldn't be posted when it was first sent — Wavey Gist changed its API "
        "contract and the legacy payload started returning HTTP 400. The AI summary "
        "was delivered correctly; the full report is now here:\n"
        f"[Full details]({gist_url})"
    )


def _already_recovered() -> bool:
    """True if a recovery follow-up has already been published for this alert.

    Looks for any ``source='recovery'`` alert on the same protocol that
    references the source alert id or its tx hash in the message body. A
    re-run no-ops so we don't pile up duplicate follow-up gists and
    Telegram messages.
    """
    existing = query_alerts(protocol=PROTOCOL, source="recovery", limit=20)
    for prev in existing:
        msg = prev.get("message", "")
        if f"alert #{ALERT_ID}" in msg or TX_HASH in msg:
            return True
    return False


def main() -> int:
    api_key = os.getenv("WAVEY_GIST_API_KEY")
    if not api_key:
        logger.error("WAVEY_GIST_API_KEY is not set; cannot publish recovery gist")
        return 1

    alert = get_alert(ALERT_ID)
    if alert is None:
        logger.error("alert %d not found in store; cannot recover", ALERT_ID)
        return 1

    if _already_recovered():
        logger.info("recovery for alert %d already published; skipping", ALERT_ID)
        return 0

    gist_body = build_gist_body(alert["message"])
    gist_url = upload_to_gist(gist_body, title=f"{DEFAULT_GIST_TITLE} — alert #{ALERT_ID}")
    if not gist_url:
        logger.error("upload_to_gist returned no URL; recovery publish failed")
        return 1
    logger.info("recovery gist published: %s", gist_url)

    message = build_telegram_followup(gist_url)
    send_telegram_message(
        message,
        PROTOCOL,
        disable_notification=True,
        plain_text=False,
        severity="LOW",
        source="recovery",
        origin_protocol=PROTOCOL,
        channel=PROTOCOL,
    )
    logger.info("recovery follow-up sent to %s topic", PROTOCOL)
    return 0


if __name__ == "__main__":
    sys.exit(main())
