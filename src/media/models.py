from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from src.database.base import Base


class ImageMedia(Base):
    """Модуль для хранения информации об изображении."""

    filename = Column(String(255), nullable=False, unique=True)
    original_filename = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(10), nullable=False)
    storage_path = Column(String(500), nullable=False)
    uploaded_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey('users.id'),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f'<Image(id={self.id}, filename={self.filename})'
