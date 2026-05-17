import shutil
import zipfile
from pathlib import Path

from app.config import Config
from app.core.exceptions import BadRequestError
from app.infrastructure.database import repository as db


async def save_tdata_archives(job_id: int, archive_paths: list[tuple[Path, str | None]]) -> list[dict]:
    results = []
    for archive_path, label in archive_paths:
        if not zipfile.is_zipfile(archive_path):
            raise BadRequestError(f"Ожидается ZIP: {label or archive_path.name}")

        row = await db.fetch_one(
            """
            INSERT INTO account_prep_accounts (job_id, label, tdata_path, status)
            VALUES ($1, $2, '', 'pending')
            RETURNING id, job_id, label, status, created_at
            """,
            job_id,
            label,
        )
        account_id = row["id"]
        dest = Config.PREP_TDATA_DIR / str(job_id) / str(account_id)
        dest.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(dest)

        if not any(dest.rglob("tdata")) and not (dest / "tdata").exists():
            shutil.rmtree(dest, ignore_errors=True)
            await db.execute("DELETE FROM account_prep_accounts WHERE id = $1", account_id)
            raise BadRequestError(f"В архиве нет tdata: {label or archive_path.name}")

        await db.execute(
            """
            UPDATE account_prep_accounts
            SET tdata_path = $2, updated_at = NOW()
            WHERE id = $1
            """,
            account_id,
            str(dest),
        )
        results.append(
            {
                "id": account_id,
                "job_id": job_id,
                "label": label,
                "status": "pending",
            }
        )
    return results
