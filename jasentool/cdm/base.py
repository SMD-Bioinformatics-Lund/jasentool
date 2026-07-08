"""Generic database objects of which several other models are based on."""

from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, FilePath

from jasentool.cdm.io.utils import convert_rel_to_abs_path

RelOrAbsPath = Annotated[Path, BeforeValidator(convert_rel_to_abs_path)]
OptionalFile = FilePath | None


class AllowExtraModelMixin(BaseModel):
    """Mixin to allow extra fields in pydantic model."""

    model_config = ConfigDict(extra="allow")
