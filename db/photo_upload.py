from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import Response

from db import db

router = APIRouter()

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


@router.post("/pets/{pet_id}/photo")
async def upload_pet_photo(
    pet_id: int,
    file: UploadFile = File(...),
):
    if pet_id <= 0:
        raise HTTPException(
            status_code=400,
            detail="Некорректный ID питомца",
        )

    content_type = file.content_type or ""

    if content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Разрешены только JPG, PNG и WEBP",
        )

    content = await file.read(MAX_SIZE + 1)
    await file.close()

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

    if db.pool is None:
        raise HTTPException(
            status_code=503,
            detail="Нет подключения к базе данных",
        )

    try:
        with db.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM pets WHERE id = %s",
                    (pet_id,),
                )

                if cur.fetchone() is None:
                    raise HTTPException(
                        status_code=404,
                        detail="Питомец не найден",
                    )

                cur.execute(
                    """
                    INSERT INTO pet_photos
                        (pet_id, photo_data, content_type, photo_url)
                    VALUES (%s, %s, %s, NULL)
                    RETURNING id, pet_id, is_main, created_at
                    """,
                    (pet_id, content, content_type),
                )

                photo = cur.fetchone()

            conn.commit()

        return {
            "id": photo["id"],
            "pet_id": photo["pet_id"],
            "is_main": photo["is_main"],
            "created_at": photo["created_at"],
            "photo_url": f"/pets/photos/{photo['id']}",
            "message": "Фотография сохранена в PostgreSQL",
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Не удалось сохранить фотографию",
        ) from exc


@router.get("/pets/photos/{photo_id}")
def get_pet_photo(photo_id: int):
    """Возвращает изображение непосредственно из PostgreSQL."""
    if photo_id <= 0:
        raise HTTPException(
            status_code=400,
            detail="Некорректный ID фотографии",
        )

    if db.pool is None:
        raise HTTPException(
            status_code=503,
            detail="Нет подключения к базе данных",
        )

    try:
        with db.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT photo_data, content_type
                    FROM pet_photos
                    WHERE id = %s
                    """,
                    (photo_id,),
                )
                photo = cur.fetchone()

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Не удалось получить фотографию",
        ) from exc

    if photo is None or photo["photo_data"] is None:
        raise HTTPException(
            status_code=404,
            detail="Фотография не найдена или ещё не хранится в BYTEA",
        )

    content_type = photo["content_type"]

    if content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=500,
            detail="Неизвестный формат фотографии",
        )

    return Response(
        content=bytes(photo["photo_data"]),
        media_type=content_type,
        headers={"X-Content-Type-Options": "nosniff"},
    )
