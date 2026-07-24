from pydantic import BaseModel, Field, SecretStr
from .models import Visibility
class CharacterCreate(BaseModel):
    name: str; adult_age: int = Field(ge=18, le=120); biography: str=""; profile: dict={}; visual_assets: dict={}; visibility: Visibility=Visibility.PRIVATE
class CredentialCreate(BaseModel): provider: str; label: str; api_secret: SecretStr
class CredentialView(BaseModel): id: str; provider: str; label: str; masked_identifier: str
