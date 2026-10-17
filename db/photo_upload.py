from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response

from db import queries
from src.auth import current_user_id

router = APIRouter(tags=["photo"])

MAX_SIZE = 5 * 1024 * 1024  # 5 МБ

ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def is_valid_image(content: bytes, content_type: str) -> bool:
    """Проверяет сигнатуру изображения, а не только имя файла."""
    if content_type == "image/jpeg":
        return content.startswith(b"\xff\xd8\xff")

    if content_type == "image/png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")

    if content_type == "image/webp":
        return (
            len(content) >= 12
            and content.startswith(b"RIFF")
            and content[8:12] == b"WEBP"
        )

    return False


# Фото хранится в самой строке питомца (pets.picture, BYTEA), по одному на питомца.
# Работать с фото может только владелец питомца; на чужого питомца ответ — 404.

@router.post("/pets/{pet_id}/photo")
def upload_pet_photo(
    pet_id: int,
    file: UploadFile = File(...),
    user_id: int = Depends(current_user_id),
):
    content_type = file.content_type or ""

    if content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Разрешены только JPG, PNG и WEBP",
        )

    content = file.file.read(MAX_SIZE + 1)

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Файл пустой",
        )

    if len(content) > MAX_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Максимальный размер фотографии — 5 МБ",
        )

    if not is_valid_image(content, content_type):
        raise HTTPException(
            status_code=400,
            detail="Содержимое файла не соответствует формату изображения",
        )

    # Новое фото заменяет предыдущее
    if not queries.set_pet_picture(pet_id, user_id, content, content_type):
        raise HTTPException(
            status_code=404,
            detail="Питомец не найден",
        )

    return {
        "pet_id": pet_id,
        "photo_url": f"/pets/{pet_id}/photo",
    }


@router.get(
    "/pets/{pet_id}/photo",
    response_class=Response,
    responses={200: {"content": {"image/*": {}}}},
)
def get_pet_photo(pet_id: int, user_id: int = Depends(current_user_id)):
    """Возвращает изображение непосредственно из PostgreSQL."""
    photo = queries.get_pet_picture(pet_id, user_id)

    if photo is None:
        raise HTTPException(
            status_code=404,
            detail="Фотография не найдена",
        )

    return Response(
        content=bytes(photo["picture"]),
        media_type=photo["picture_type"],
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-cache",
        },
    )


@router.delete("/pets/{pet_id}/photo", status_code=status.HTTP_204_NO_CONTENT)
def delete_pet_photo(pet_id: int, user_id: int = Depends(current_user_id)):
    if not queries.set_pet_picture(pet_id, user_id, None, None):
        raise HTTPException(
            status_code=404,
            detail="Питомец не найден",
        )
