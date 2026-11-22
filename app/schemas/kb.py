from pydantic import BaseModel, ConfigDict, Field


class KBArticleWrite(BaseModel):
    title: str = Field(min_length=1, max_length=200)  # String(200) in the model
    content: str = Field(min_length=1)


class KBArticleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str


class KBSearch(BaseModel):
    query: str = Field(min_length=1)


class KBSearchResult(KBArticleRead):
    score: float  # similarity, 1 = same meaning
