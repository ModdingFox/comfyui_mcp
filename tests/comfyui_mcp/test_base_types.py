import pytest
from pydantic import HttpUrl, ValidationError

from comfyui_mcp.base_types import ComfyResult, MediaType

VALID_URL = "https://example.com/file.png"


@pytest.mark.parametrize(
    (
        "input_value",
        "expected",
    ),
    [
        (MediaType.AUDIO, MediaType.AUDIO),
        (MediaType.IMAGES, MediaType.IMAGES),
        (MediaType.UNKNOWN, MediaType.UNKNOWN),
        ("audio", MediaType.AUDIO),
        ("AUDIO", MediaType.AUDIO),
        ("images", MediaType.IMAGES),
        ("unknown", MediaType.UNKNOWN),
        ("nonsense", MediaType.UNKNOWN),
        (123, MediaType.UNKNOWN),
        (None, MediaType.UNKNOWN),
    ],
)
def test_media_type_field_validator(input_value, expected):
    """Ensure validate_media_type handles all supported input types."""
    result = ComfyResult(media_type=input_value, filename=VALID_URL)
    assert result.media_type == expected


def test_media_type_defaults_to_unknown():
    """If media_type not provided, it should default to UNKNOWN."""
    result = ComfyResult(filename=VALID_URL)
    assert result.media_type == MediaType.UNKNOWN


def test_invalid_url_raises_validation_error():
    """Invalid URL must raise a Pydantic ValidationError."""
    with pytest.raises(ValidationError):
        ComfyResult(media_type="audio", filename="not-a-valid-url")


def test_valid_url_accepts():
    """Valid URLs should pass validation."""
    result = ComfyResult(media_type="images", filename="https://valid-url.com/output.jpg")
    assert result.filename == HttpUrl("https://valid-url.com/output.jpg")


def test_media_type_enum_values():
    """Ensure the MediaType enum members have correct string values."""
    assert MediaType.AUDIO.value == "audio"
    assert MediaType.IMAGES.value == "images"
    assert MediaType.UNKNOWN.value == "unknown"
