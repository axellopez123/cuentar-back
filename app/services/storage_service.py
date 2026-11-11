import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import puremagic

from app.core.config import settings
from app.core.exceptions import InvalidFileException


@dataclass(frozen=True)
class SavedFileInfo:
    original_name: str
    relative_path: str
    mime_type: str
    file_size_bytes: int


# Mapping from recognized MIME types to standard safe extensions
SAFE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}


class StorageService:
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir or settings.UPLOAD_DIR)

    def validate_file(self, filename: str, content: bytes) -> str:
        """
        Validates size and true content MIME type using magic bytes.
        Returns the validated mime type.
        """
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        file_size = len(content)

        if file_size == 0:
            raise InvalidFileException("El archivo está vacío.")

        if file_size > max_bytes:
            raise InvalidFileException(
                f"El archivo ({file_size / (1024 * 1024):.2f} MB) excede el tamaño máximo permitido de {settings.MAX_UPLOAD_SIZE_MB} MB."
            )

        # Detect MIME type from header magic bytes
        try:
            detected_mime = puremagic.from_string(content[:4096], mime=True)
        except puremagic.PureError:
            raise InvalidFileException("No se pudo identificar el tipo de contenido del archivo.")

        # Handle variations (e.g. image/x-png -> image/png)
        if detected_mime == "image/x-png":
            detected_mime = "image/png"
        elif detected_mime in ("image/pjpeg", "image/jpg"):
            detected_mime = "image/jpeg"

        if detected_mime not in settings.ALLOWED_MIME_TYPES:
            raise InvalidFileException(
                f"Tipo de archivo no permitido: '{detected_mime}'. Solo se permiten imágenes (JPEG, PNG, WebP) o PDFs."
            )

        return detected_mime

    async def save_file(
        self,
        original_filename: str,
        content: bytes,
        subfolder: str = "receipts",
    ) -> SavedFileInfo:
        """
        Validates and saves a file securely with a UUID name in an organized directory structure.
        """
        mime_type = self.validate_file(original_filename, content)
        extension = SAFE_EXTENSIONS.get(mime_type, Path(original_filename).suffix.lower() or ".bin")

        # Create standardized relative path: subfolder/YYYY/MM/UUID.ext
        now = datetime.now(timezone.utc)
        year_str = now.strftime("%Y")
        month_str = now.strftime("%m")

        unique_filename = f"{uuid.uuid4().hex}{extension}"
        relative_dir = Path(subfolder) / year_str / month_str
        target_dir = self.base_dir / relative_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        destination_path = target_dir / unique_filename

        # Write file content to disk
        with open(destination_path, "wb") as f:
            f.write(content)

        relative_path_str = (relative_dir / unique_filename).as_posix()

        return SavedFileInfo(
            original_name=original_filename,
            relative_path=relative_path_str,
            mime_type=mime_type,
            file_size_bytes=len(content),
        )

    def delete_file(self, relative_path: str) -> bool:
        """Safely removes a file from disk if it exists."""
        # Prevent directory traversal
        target_path = (self.base_dir / relative_path).resolve()
        if not str(target_path).startswith(str(self.base_dir.resolve())):
            return False

        if target_path.exists() and target_path.is_file():
            try:
                target_path.unlink()
                return True
            except OSError:
                return False
        return False

    def get_absolute_path(self, relative_path: str) -> Path:
        """Returns the absolute path on disk for a relative path."""
        target_path = (self.base_dir / relative_path).resolve()
        if not str(target_path).startswith(str(self.base_dir.resolve())):
            raise InvalidFileException("Ruta de archivo no autorizada.")
        return target_path


storage_service = StorageService()

