from pathlib import Path  # Keep uploaded demo files inside the project media directory.
from uuid import uuid4  # Generate unpredictable names instead of trusting uploaded filenames.

from fastapi import APIRouter, Depends, HTTPException, Request, status  # Validate upload requests and return safe errors.

from app.auth import get_current_user  # Require a signed-in owner before accepting an upload.
from app.models import User  # Type the authenticated account dependency.


router = APIRouter()  # Group media upload routes.
MAX_COVER_BYTES = 5 * 1024 * 1024  # Limit cover images to five megabytes.
MEDIA_DIR = Path(__file__).resolve().parents[1] / "media" / "recipe-covers"  # Store development uploads under the project root.
MEDIA_DIR.mkdir(parents=True, exist_ok=True)  # Prepare the local directory before the static mount starts.
ALLOWED_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}  # Accept raster formats safe for browser display.


# Accept a bounded raster image and return its local API URL.
@router.post("/media/recipe-covers", status_code=status.HTTP_201_CREATED)  # Require authentication to upload a recipe cover.
async def upload_recipe_cover(request: Request, user: User = Depends(get_current_user)) -> dict[str, str]:  # Stream one image into local development storage.
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()  # Normalize the browser-provided image type.
    extension = ALLOWED_TYPES.get(content_type)  # Allow only supported raster formats.
    if extension is None:  # Reject HTML, SVG, and unknown upload types.
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Formats acceptés : JPEG, PNG ou WebP.")  # Explain the supported image formats.
    chunks: list[bytes] = []  # Keep only the bounded request body in memory.
    size = 0  # Track bytes while receiving the file.
    async for chunk in request.stream():  # Read the upload in bounded network chunks.
        size += len(chunk)  # Add the current chunk length.
        if size > MAX_COVER_BYTES:  # Stop before storing an oversized cover.
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="La photo ne peut pas dépasser 5 Mo.")  # Explain the upload limit.
        chunks.append(chunk)  # Keep accepted image bytes for the final write.
    if size == 0:  # Reject empty file selections.
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Le fichier image est vide.")  # Explain why the upload was rejected.
    filename = uuid4().hex + extension  # Ignore the client filename to prevent path manipulation and collisions.
    destination = MEDIA_DIR / filename  # Build a path contained in the server-owned media directory.
    destination.write_bytes(b"".join(chunks))  # Persist the bounded file bytes.
    return {"image_url": "/api/v1/media/files/" + filename}  # Return the same-origin URL accepted by recipe records.
