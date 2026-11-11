import uuid
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.api.deps import SessionDep, CurrentUserDep
from app.models.attachment import Attachment
from app.services.storage_service import storage_service

router = APIRouter(prefix="/attachments", tags=["Archivos y Evidencias"])


@router.get("/{attachment_id}/download")
async def download_attachment(
    attachment_id: uuid.UUID,
    session: SessionDep,
    _current_user: CurrentUserDep,
):
    """Safely retrieves and downloads an evidence receipt or statement file."""
    stmt = select(Attachment).where(Attachment.id == attachment_id)
    att = (await session.execute(stmt)).scalar_one_or_none()
    if not att:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archivo adjunto no encontrado.",
        )

    try:
        abs_path = storage_service.get_absolute_path(att.file_path)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ruta de archivo no autorizada o inválida.",
        )

    if not abs_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El archivo físico no existe en el almacenamiento.",
        )

    return FileResponse(
        path=str(abs_path),
        media_type=att.mime_type,
        filename=att.file_name,
    )

