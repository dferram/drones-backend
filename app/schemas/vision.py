from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ModelSpec(BaseModel):
    path: str
    labels: dict[int, Literal["PERSONA", "HUMO"]] = Field(min_length=1)
    class_count: int = Field(ge=1, le=1000)
    input_size: int = Field(640, ge=128, le=2048)

    @model_validator(mode="after")
    def valid_labels(self):
        if any(key < 0 or key >= self.class_count for key in self.labels):
            raise ValueError("Índice de clase fuera de rango")
        return self
