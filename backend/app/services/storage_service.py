import os
import re
import uuid
import pathlib
from typing import Tuple
from fastapi import UploadFile, HTTPException, status
from backend.app.config import settings

# Supported MIME types and their canonical magic byte headers
MAGIC_SIGNATURES = {
    "application/pdf": [b"%PDF-"],
    "image/jpeg": [b"\xFF\xD8\xFF"],
    "image/png": [b"\x89PNG\r\n\x1a\n", b"\x89\x50\x4E\x47\x0D\x0A\x1A\x0A"],
}

ALLOWED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}

class StorageService:
    def __init__(self, base_dir: str = None):
        self.base_dir = pathlib.Path(base_dir or settings.UPLOAD_STORAGE_DIR).resolve()
        # Ensure target storage directory exists
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_filename(self, filename: str) -> str:
        """Strips path characters and keeps only safe characters for preservation."""
        name = pathlib.Path(filename).name
        # Remove any path traversal or dangerous symbols, keeping only alphanumeric, hyphen, underscore, period
        cleaned = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", name)
        # Prevent hidden files
        cleaned = cleaned.lstrip(".")
        return cleaned or "document"

    def _detect_mime_type(self, header: bytes, extension: str) -> str:
        """
        Validates content magic bytes against allowed formats.
        Prevents file extension spoofing (e.g. text or executable renamed to .pdf).
        """
        ext = extension.lower()
        expected_mime = ALLOWED_EXTENSIONS.get(ext)
        if not expected_mime:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{extension}'. Allowed formats: PDF, JPG, JPEG, PNG."
            )

        signatures = MAGIC_SIGNATURES.get(expected_mime, [])
        matches = any(header.startswith(sig) for sig in signatures)
        if not matches:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File content does not match the expected {expected_mime} format. Invalid magic bytes header."
            )

        return expected_mime

    def _get_safe_path(self, stored_filename: str) -> pathlib.Path:
        """
        Ensures the requested stored_filename resolves strictly inside self.base_dir.
        Blocks directory traversal attacks.
        """
        # Disallow directory components in stored_filename
        if "/" in stored_filename or "\\" in stored_filename or ".." in stored_filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid stored filename parameter."
            )

        resolved_path = (self.base_dir / stored_filename).resolve()
        try:
            resolved_path.relative_to(self.base_dir)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Access outside authorized storage directory is prohibited."
            )
        return resolved_path

    async def save_upload(self, upload_file: UploadFile) -> Tuple[str, str, int, str]:
        """
        Reads, validates, and securely stores an uploaded file.
        Returns:
            (stored_filename, original_filename, file_size, mime_type)
        """
        original_name = upload_file.filename or "upload"
        sanitized_original = self._sanitize_filename(original_name)
        ext = pathlib.Path(sanitized_original).suffix.lower()

        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file extension '{ext}'. Only .pdf, .jpg, .jpeg, and .png files are accepted."
            )

        # Read file into memory chunk-by-chunk to enforce MAX_UPLOAD_SIZE_BYTES
        content = bytearray()
        chunk_size = 64 * 1024  # 64 KB
        total_size = 0
        max_size = settings.MAX_UPLOAD_SIZE_BYTES

        while True:
            chunk = await upload_file.read(chunk_size)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > max_size:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File exceeds maximum allowed size of {max_size // (1024 * 1024)} MB."
                )
            content.extend(chunk)

        if total_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty (0 bytes)."
            )

        # Validate magic header
        mime_type = self._detect_mime_type(bytes(content[:32]), ext)

        # Generate unique unguessable filename
        unique_token = uuid.uuid4().hex
        stem = pathlib.Path(sanitized_original).stem[:32]
        stored_filename = f"fdr_doc_{unique_token}_{stem}{ext}"

        safe_path = self._get_safe_path(stored_filename)
        with open(safe_path, "wb") as f:
            f.write(content)

        return stored_filename, original_name, total_size, mime_type

    def get_file_path(self, stored_filename: str) -> pathlib.Path:
        """Retrieves and verifies existence of stored file."""
        safe_path = self._get_safe_path(stored_filename)
        if not safe_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document file does not exist on disk."
            )
        return safe_path

    def delete_file(self, stored_filename: str) -> bool:
        """Safely removes stored file from disk if it exists."""
        try:
            safe_path = self._get_safe_path(stored_filename)
            if safe_path.is_file():
                safe_path.unlink()
                return True
        except Exception:
            pass
        return False

storage_service = StorageService()
