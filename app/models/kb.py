from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base

# Must match the size the embedding model is asked to return.
EMBEDDING_DIM = 768


# shortcut: one embedding per whole article, no chunking; fine while articles are a few
# paragraphs, split into chunks if long articles start retrieving poorly.
class KBArticle(Base):
    __tablename__ = "kb_articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    embedding = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
