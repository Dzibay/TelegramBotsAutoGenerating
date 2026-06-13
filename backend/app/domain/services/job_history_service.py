"""Снимки задач создания ботов: входные данные, результаты, повтор неудачных."""
import json
import shutil
from pathlib import Path
from typing import Any

from app.config import Config
from app.core.exceptions import BadRequestError
from app.domain.models.campaign_models import (
    ManualBotItem,
    ManualSharedTexts,
    StartManualBulkRequest,
)


def snapshot_dir(job_id: int) -> Path:
    return Config.STORAGE_ROOT / "job_snapshots" / str(job_id)


def _relative_storage_path(path: Path) -> str:
    root = Config.STORAGE_ROOT.resolve()
    return str(path.resolve().relative_to(root)).replace("\\", "/")


def _copy_avatar_to_snapshot(job_id: int, row_id: int, source: Path) -> str | None:
    if not source.is_file():
        return None
    dest_dir = snapshot_dir(job_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{row_id}.jpg"
    shutil.copy2(source, dest)
    return _relative_storage_path(dest)


def build_manual_input_snapshot(
    *,
    job_id: int,
    body: StartManualBulkRequest,
    manual_plans: list[dict[str, Any]],
    link_source: str,
    use_referral: bool,
    default_url: str,
) -> dict[str, Any]:
    bots: list[dict[str, Any]] = []
    for plan in manual_plans:
        row_id = int(plan["row_id"])
        entry: dict[str, Any] = {
            "row_id": row_id,
            "display_name": plan["display_name"],
            "username": plan["username"],
            "target_url": plan.get("target_url") or "",
        }
        avatar_path = plan.get("avatar_path")
        if avatar_path:
            stored = _copy_avatar_to_snapshot(job_id, row_id, Path(avatar_path))
            if stored:
                entry["avatar_storage_path"] = stored
        bots.append(entry)

    return {
        "mode": "manual_multi" if body.multi_account else "manual",
        "multi_account": bool(body.multi_account),
        "telegram_account_id": body.telegram_account_id,
        "link_source": link_source,
        "link_mode": body.link_mode,
        "auto_start": body.auto_start,
        "use_referral_api": use_referral,
        "default_target_url": default_url,
        "shared_texts": body.shared_texts.model_dump(),
        "bots": bots,
    }


def build_planned_input_snapshot(plans: list[dict[str, Any]]) -> dict[str, Any]:
    return {"mode": "planned", "plans": plans}


def build_auto_input_snapshot() -> dict[str, Any]:
    return {"mode": "auto"}


async def persist_input_snapshot(
    job_id: int,
    *,
    job_mode: str,
    snapshot: dict[str, Any],
) -> None:
    from app.infrastructure.database import repository as db

    await db.execute(
        """
        UPDATE creation_jobs
        SET job_mode = $2,
            input_snapshot = $3::jsonb,
            updated_at = NOW()
        WHERE id = $1
        """,
        job_id,
        job_mode,
        json.dumps(snapshot, ensure_ascii=False),
    )


def _count_row_statuses(row_results: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"done": 0, "error": 0, "skipped": 0, "pending": 0}
    for row in row_results:
        status = row.get("status") or "pending"
        if status in counts:
            counts[status] += 1
        else:
            counts["pending"] += 1
    return counts


def build_result_snapshot(
    *,
    input_snapshot: dict[str, Any] | None,
    row_results: list[dict[str, Any]],
    total_created: int,
    finished_status: str,
    error_message: str | None = None,
) -> dict[str, Any]:
    counts = _count_row_statuses(row_results)
    planned = len(row_results)
    if not planned and input_snapshot and input_snapshot.get("bots"):
        planned = len(input_snapshot["bots"])

    result: dict[str, Any] = {
        "finished_status": finished_status,
        "mode": (input_snapshot or {}).get("mode"),
        "total_planned": planned,
        "total_created": total_created,
        "total_failed": counts["error"],
        "total_skipped": counts["skipped"],
        "row_results": row_results,
    }
    if error_message:
        result["error_message"] = error_message[:500]

    if input_snapshot and input_snapshot.get("mode") in ("manual", "manual_multi"):
        done_ids = {
            int(r["row_id"])
            for r in row_results
            if r.get("status") == "done" and r.get("row_id") is not None
        }
        failed_bots = [
            bot
            for bot in input_snapshot.get("bots", [])
            if int(bot.get("row_id", 0)) not in done_ids
        ]
        if failed_bots:
            retry_payload = {k: v for k, v in input_snapshot.items() if k != "bots"}
            retry_payload["bots"] = failed_bots
            result["retry_payload"] = retry_payload
            result["retry_count"] = len(failed_bots)
    elif input_snapshot and input_snapshot.get("mode") == "planned":
        result["total_planned"] = len(input_snapshot.get("plans") or [])

    return result


async def save_result_snapshot(
    job_id: int,
    *,
    row_results: list[dict[str, Any]],
    total_created: int,
    finished_status: str,
    error_message: str | None = None,
) -> None:
    from app.infrastructure.database import repository as db

    row = await db.fetch_one(
        "SELECT input_snapshot FROM creation_jobs WHERE id = $1",
        job_id,
    )
    if not row:
        return
    input_snapshot = parse_json_field(row.get("input_snapshot"))
    snapshot = build_result_snapshot(
        input_snapshot=input_snapshot,
        row_results=row_results,
        total_created=total_created,
        finished_status=finished_status,
        error_message=error_message,
    )
    await db.execute(
        """
        UPDATE creation_jobs
        SET result_snapshot = $2::jsonb,
            updated_at = NOW()
        WHERE id = $1
        """,
        job_id,
        json.dumps(snapshot, ensure_ascii=False),
    )


def resolve_snapshot_avatar_path(
    job_id: int,
    row_id: int,
    *,
    input_snapshot: dict[str, Any] | None = None,
    retry_payload: dict[str, Any] | None = None,
) -> Path | None:
    sources: list[dict[str, Any]] = []
    if retry_payload:
        sources.append(retry_payload)
    if input_snapshot:
        sources.append(input_snapshot)
    for source in sources:
        for bot in source.get("bots") or []:
            if int(bot.get("row_id", 0)) != int(row_id):
                continue
            rel = bot.get("avatar_storage_path")
            if rel:
                path = Config.STORAGE_ROOT / rel
                if path.is_file():
                    return path
            fallback = snapshot_dir(job_id) / f"{row_id}.jpg"
            if fallback.is_file():
                return fallback
    fallback = snapshot_dir(job_id) / f"{row_id}.jpg"
    return fallback if fallback.is_file() else None


def load_retry_avatars(retry_payload: dict[str, Any]) -> dict[int, bytes]:
    avatars: dict[int, bytes] = {}
    for bot in retry_payload.get("bots") or []:
        rel = bot.get("avatar_storage_path")
        if not rel:
            continue
        path = Config.STORAGE_ROOT / rel
        if path.is_file():
            avatars[int(bot["row_id"])] = path.read_bytes()
    return avatars


def retry_payload_to_request(retry_payload: dict[str, Any]) -> StartManualBulkRequest:
    bots = retry_payload.get("bots") or []
    if not bots:
        raise BadRequestError("В снимке задачи нет ботов для повтора")
    shared = retry_payload.get("shared_texts") or {}
    return StartManualBulkRequest(
        telegram_account_id=retry_payload.get("telegram_account_id"),
        multi_account=bool(retry_payload.get("multi_account")),
        default_target_url=retry_payload.get("default_target_url"),
        link_mode=retry_payload.get("link_mode") or "redirect",
        auto_start=bool(retry_payload.get("auto_start", True)),
        use_referral_api=retry_payload.get("use_referral_api"),
        link_source=retry_payload.get("link_source"),
        shared_texts=ManualSharedTexts.model_validate(shared),
        bots=[ManualBotItem.model_validate(bot) for bot in bots],
    )


def parse_json_field(value: Any) -> dict[str, Any] | None:
    if not value:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return json.loads(value)
    return None


def job_history_summary(row: dict[str, Any]) -> dict[str, Any]:
    result = parse_json_field(row.get("result_snapshot"))
    retry_count = 0
    if result:
        retry_count = int(result.get("retry_count") or 0)
        if not retry_count and result.get("retry_payload"):
            retry_count = len(result["retry_payload"].get("bots") or [])
    return {
        "retry_available": retry_count > 0,
        "retry_count": retry_count,
        "total_failed": int((result or {}).get("total_failed") or 0),
        "total_skipped": int((result or {}).get("total_skipped") or 0),
    }
