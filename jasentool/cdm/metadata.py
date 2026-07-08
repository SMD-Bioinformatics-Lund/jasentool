"""Metadata models."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_serializer
from typing_extensions import Annotated

from .base import RelOrAbsPath


class MetadataTypes(StrEnum):
    """Supported metadata types."""

    STR = "string"
    INT = "integer"
    FLOAT = "float"


class StrMetadataEntry(BaseModel):
    """Container of basic metadata information"""

    fieldname: str
    value: str
    category: str = "general"
    type: Literal[MetadataTypes.STR]


class IntMetadataEntry(BaseModel):
    """Container of basic metadata information"""

    fieldname: str
    value: int
    category: str = "general"
    type: Literal[MetadataTypes.INT]


class FloatMetadataEntry(BaseModel):
    """Container of basic metadata information"""

    fieldname: str
    value: int
    category: str = "general"
    type: Literal[MetadataTypes.FLOAT]


class DatetimeMetadataEntry(BaseModel):
    """Container of basic metadata information"""

    fieldname: str
    value: datetime
    category: str = "general"
    type: Literal["datetime"]

    @field_serializer("value")
    def serialize_datetime(self, date: datetime) -> str:
        """Serialize datetime object as string."""
        return date.isoformat()


class TableMetadataEntry(BaseModel):
    """Container of basic metadata information"""

    fieldname: str
    value: RelOrAbsPath | str
    category: str = "general"
    type: Literal["table"]


MetaEntry = Annotated[
    TableMetadataEntry
    | DatetimeMetadataEntry
    | StrMetadataEntry
    | IntMetadataEntry
    | FloatMetadataEntry,
    Field(discriminator="type"),
]
