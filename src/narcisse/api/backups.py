"""Backing up all of Narcisse's data, and restoring a backup, from the settings page."""

import asyncio
import base64
import binascii

from fastapi import APIRouter, Response
from sqlalchemy import select

from narcisse.api.deps import ServicesDep
from narcisse.domain import ScanStatus
from narcisse.errors import AppError
from narcisse.schemas import BackupIn, RestoreIn, RestoreOut
from narcisse.storage import backup
from narcisse.storage.models import Scan

router = APIRouter(tags=["backups"])


@router.post("/backup")
async def make_backup(body: BackupIn, s: ServicesDep) -> Response:
    """The backup file (sealed with the passphrase, if one is given), to download."""
    now = s.engine.clock.now()
    passphrase = body.passphrase or None
    data = await asyncio.to_thread(backup.create, s.settings, now, passphrase)
    name = backup.file_name(now, encrypted=bool(passphrase))
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.post("/restore")
async def restore_backup(body: RestoreIn, s: ServicesDep) -> RestoreOut:
    """Replaces all of Narcisse's data with the backup's, after keeping the current data in a
    backup of its own. Refused while a scan runs."""
    try:
        data = base64.b64decode(body.data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise AppError("backup_invalid", status=422) from exc
    restored = await asyncio.to_thread(backup.read, data, body.passphrase or None)
    async with s.db.snapshot() as session:
        running = await session.scalar(
            select(Scan.id).where(Scan.status == ScanStatus.RUNNING).limit(1)
        )
    if running is not None:
        raise AppError("restore_while_scanning", status=409)

    now = s.engine.clock.now()
    safety = backup.safety_path(s.settings, now)
    safety.write_bytes(await asyncio.to_thread(backup.create, s.settings, now))
    await s.reopen(lambda: backup.replace_data(s.settings, restored))
    return RestoreOut(
        profiles=restored.manifest.profiles,
        created_at=restored.manifest.created_at,
        narcisse=restored.manifest.narcisse,
        safety=str(safety),
    )
