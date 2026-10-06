"""Photo storage in Cloudinary and building URLs of transformed images."""
import uuid

import cloudinary
import cloudinary.uploader
import cloudinary.utils

from src.conf.config import settings


def is_configured() -> bool:
    """Check that all Cloudinary credentials are set.

    :return: ``True`` if photos can be uploaded.
    """
    return bool(settings.cloudinary_name and settings.cloudinary_api_key and settings.cloudinary_api_secret)


def _configure() -> None:
    cloudinary.config(
        cloud_name=settings.cloudinary_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )


def upload_photo(file, user_id: int) -> tuple[str, str]:
    """Upload an image to Cloudinary under a new unique public id.

    :param file: A file-like object with the image.
    :param user_id: The id of the owner; photos are grouped in a folder per user.
    :return: ``(url, public_id)``.
    :raises cloudinary.exceptions.Error: If Cloudinary rejects the upload.
    """
    _configure()
    public_id = f"{settings.cloudinary_folder}/user_{user_id}/{uuid.uuid4().hex}"
    result = cloudinary.uploader.upload(file, public_id=public_id, resource_type="image")
    return result["secure_url"], result["public_id"]


def delete_photo(public_id: str) -> None:
    """Delete an image from Cloudinary; errors are ignored, the database is the source of truth.

    :param public_id: The Cloudinary public id.
    """
    _configure()
    try:
        cloudinary.uploader.destroy(public_id, invalidate=True)
    except Exception:  # noqa: BLE001 - a leftover file must not break the API
        pass


def transformation_params(options: dict) -> dict:
    """Turn validated request options into Cloudinary transformation parameters.

    :param options: Fields of :class:`src.schemas.TransformationRequest` without ``None`` values.
    :return: Parameters for ``build_url``.
    """
    params = {}
    for key in ("width", "height", "crop", "gravity", "angle", "radius", "effect"):
        if key in options:
            params[key] = options[key]
    if ("width" in params or "height" in params) and "crop" not in params:
        params["crop"] = "fill"
    return params


def describe(options: dict) -> str:
    """Human readable, stable description of the transformation, e.g. ``width=300, effect=sepia``.

    :param options: Transformation options.
    :return: The description.
    """
    return ", ".join(f"{key}={options[key]}" for key in sorted(options))


def build_transformed_url(public_id: str, options: dict) -> str:
    """URL of the image with the transformation applied by Cloudinary on the fly.

    No request to Cloudinary is made: the transformation is encoded in the URL.

    :param public_id: The Cloudinary public id.
    :param options: Transformation options.
    :return: The URL.
    """
    _configure()
    params = transformation_params(options)
    kwargs = {"transformation": [params]} if params else {}
    if "format" in options:
        kwargs["format"] = options["format"]
    url, _ = cloudinary.utils.cloudinary_url(public_id, **kwargs)
    return url
