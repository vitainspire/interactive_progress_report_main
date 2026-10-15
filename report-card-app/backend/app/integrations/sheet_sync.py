"""Background auto-sync for batches created from a Google Sheet link.

Google Sheets has no push/webhook story this app uses (that would need
real Drive API OAuth and a renewable watch subscription — see the
conversation this was scoped from); instead this polls. Every
POLL_INTERVAL_SECONDS, every batch that was created from a sheet link
(app/db/batches.py's sync_batch_from_parsed is the "update in place"
counterpart to create_batch's "always a new batch") gets re-fetched via
the exact same Google export endpoint already used at upload time. A
sha256 of the raw bytes is compared against what's stored — if it matches,
nothing happened since last check and the cycle moves on; if it differs,
the sheet is reparsed and the batch's data is updated in place.

Runs as a single asyncio background task for the whole process (started
from main.py's lifespan), not a per-request action — a teacher never
waits on this, and one slow/broken sheet can't block anyone else's request.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import logging

from app.db.database import session
from app.db import batches as repo
from app.integrations.google_sheets import GoogleSheetFetchError, fetch_google_sheet_as_xlsx
from app.parsing.sheet_parser import SheetParseError, parse_workbook_file

POLL_INTERVAL_SECONDS = 15 * 60

logger = logging.getLogger("sheet_sync")


async def _sync_one(batch: dict) -> None:
    try:
        raw = await asyncio.to_thread(fetch_google_sheet_as_xlsx, batch["sheet_url"])
    except GoogleSheetFetchError as exc:
        # Sheet unshared, deleted, or temporarily unreachable — try again
        # next cycle rather than giving up on this batch permanently.
        logger.info("sheet_sync: batch %s unreachable this cycle: %s", batch["id"], exc)
        return

    new_hash = hashlib.sha256(raw).hexdigest()
    if new_hash == batch["sheet_content_hash"]:
        return  # unchanged since last check — nothing to do

    try:
        parsed = parse_workbook_file(io.BytesIO(raw))
    except SheetParseError as exc:
        # Most likely caught mid-edit (a half-finished header row, say) —
        # skip this cycle and let the next one see the settled result,
        # rather than ever writing a broken parse into real data.
        logger.info("sheet_sync: batch %s sheet didn't parse this cycle: %s", batch["id"], exc)
        return

    with session() as conn:
        result = repo.sync_batch_from_parsed(conn, batch["id"], parsed)
        repo.update_batch_sheet_hash(conn, batch["id"], new_hash)
    logger.info("sheet_sync: batch %s synced — %s", batch["id"], result)


async def poll_once() -> None:
    with session() as conn:
        due = repo.list_batches_with_sheet_url(conn)
    for batch in due:
        try:
            await _sync_one(batch)
        except Exception:
            # One batch's unexpected failure (a transient DB hiccup, a
            # genuinely malformed response, anything) must never take the
            # whole poller down with it — every other batch still gets its
            # turn this cycle, and this one gets retried next cycle.
            logger.exception("sheet_sync: unexpected error syncing batch %s", batch["id"])


async def poll_loop() -> None:
    while True:
        try:
            await poll_once()
        except Exception:
            logger.exception("sheet_sync: poll cycle failed")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
