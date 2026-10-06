"""Pydantic schemas of requests and responses."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from src.database.models import Role

USERNAME_PATTERN = r"^[A-Za-z0-9_.-]+$"


# ---------- users / auth ----------

class UserCreate(BaseModel):
    """Data for sign up."""

    username: str = Field(min_length=3, max_length=50, pattern=USERNAME_PATTERN)
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)


class UserUpdate(BaseModel):
    """Fields the user can change about themself; omitted fields stay the same."""

    username: str | None = Field(None, min_length=3, max_length=50, pattern=USERNAME_PATTERN)
    email: EmailStr | None = None
    full_name: str | None = Field(None, max_length=100)
    bio: str | None = Field(None, max_length=500)
    password: str | None = Field(None, min_length=6, max_length=72)


class UserMe(BaseModel):
    """Full information about the current user."""

    id: int
    username: str
    email: EmailStr
    full_name: str | None
    bio: str | None
    role: Role
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserProfile(BaseModel):
    """Public profile of a user."""

    id: int
    username: str
    full_name: str | None
    bio: str | None
    role: Role
    created_at: datetime
    photos_count: int
    comments_count: int


class UserAdminView(BaseModel):
    """A user as seen by an administrator."""

    id: int
    username: str
    email: EmailStr
    role: Role
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoleUpdate(BaseModel):
    """New role of a user."""

    role: Role


class TokenPair(BaseModel):
    """Access and refresh tokens."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class Message(BaseModel):
    """A plain text answer."""

    message: str


# ---------- photos ----------

class OwnerShort(BaseModel):
    """Owner of a photo or author of a comment."""

    id: int
    username: str

    model_config = ConfigDict(from_attributes=True)


class PhotoResponse(BaseModel):
    """A photo with its tags and rating."""

    id: int
    url: str
    description: str | None
    owner: OwnerShort
    tags: list[str]
    rating: float | None = Field(description="Average rating, null if nobody rated the photo")
    ratings_count: int
    comments_count: int
    created_at: datetime
    updated_at: datetime


class PhotoUpdate(BaseModel):
    """New description and (optionally) new tags of a photo."""

    description: str | None = Field(None, max_length=1000)
    tags: list[str] | None = Field(None, description="If given, replaces all tags of the photo")


class PhotoPage(BaseModel):
    """One page of photos."""

    items: list[PhotoResponse]
    total: int
    skip: int
    limit: int


CropMode = Literal["fill", "fit", "scale", "thumb", "crop", "pad", "limit"]
Gravity = Literal["auto", "center", "face", "faces", "north", "south", "east", "west"]
Effect = Literal["grayscale", "sepia", "blackwhite", "cartoonify", "pixelate", "blur", "vignette", "negate", "oil_paint"]
ImageFormat = Literal["jpg", "png", "webp", "gif"]


class TransformationRequest(BaseModel):
    """A limited set of Cloudinary transformations; at least one must be given."""

    width: int | None = Field(None, ge=1, le=4000)
    height: int | None = Field(None, ge=1, le=4000)
    crop: CropMode | None = None
    gravity: Gravity | None = None
    effect: Effect | None = None
    angle: int | None = Field(None, ge=-360, le=360)
    radius: int | Literal["max"] | None = Field(None, description="Rounded corners in px or 'max' for a circle")
    format: ImageFormat | None = None

    @field_validator("radius")
    @classmethod
    def radius_not_negative(cls, value):
        """Reject negative radius values."""
        if isinstance(value, int) and value < 0:
            raise ValueError("radius must be >= 0")
        return value

    @model_validator(mode="after")
    def not_empty(self):
        """At least one transformation is required."""
        if not self.model_dump(exclude_none=True):
            raise ValueError("at least one transformation must be given")
        return self


class TransformedLinkResponse(BaseModel):
    """A saved link to a transformed image and its QR code."""

    id: int
    photo_id: int
    url: str
    transformation: str
    qr_code_url: str
    created_at: datetime


# ---------- comments ----------

class CommentCreate(BaseModel):
    """Text of a new or edited comment."""

    text: str = Field(min_length=1, max_length=2000)


class CommentResponse(BaseModel):
    """A comment."""

    id: int
    text: str
    photo_id: int
    user: OwnerShort
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------- ratings ----------

class RatingCreate(BaseModel):
    """1 to 5 stars."""

    value: int = Field(ge=1, le=5)


class RatingResponse(BaseModel):
    """A rating given by a user."""

    id: int
    value: int
    photo_id: int
    user: OwnerShort
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
