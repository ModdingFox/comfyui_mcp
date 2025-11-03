import asyncio
from pathlib import Path
from unittest.mock import MagicMock

from comfyui_mcp.workflow_utils import call_workflow, get_params_from_workflow, prepare_workflow


def test_call_workflow(monkeypatch):
    """Run call_workflow synchronously with a patched ComfyAPI and Callbacks."""

    called = {}

    async def fake_submit(self, workflow, callbacks):
        called["workflow"] = workflow
        # Simulate callback completing successfully
        await callbacks.completed({"images": [{"filename": "test.png"}]}, cached=False)

    class DummyCallbacks:
        async def completed(self, output, cached):
            pass

    # Patch methods/classes where used
    monkeypatch.setattr("comfyui_mcp.workflow_utils.ComfyAPI.submit", fake_submit)
    monkeypatch.setattr("comfyui_mcp.workflow_utils.Callbacks", DummyCallbacks)

    args = MagicMock()
    args.host = "localhost"

    result = asyncio.run(
        call_workflow(args, {"nodes": {"0": {"class_type": "ImageSaver"}}})
    )

    assert isinstance(result, list)
    assert result == ["http://localhost/api/view?filename=test.png"]
    assert "workflow" in called


def test_get_params_from_workflow():
    """Ensure parameter extraction matches real keying by _meta.title."""
    workflow_payload = {
        "0": {
            "_meta": {"title": "Node0"},
            "class_type": "PrimitiveInt",
            "inputs": {"value": 42},
        },
        "1": {
            "_meta": {"title": "Node1"},
            "class_type": "ImageResize",
            "inputs": {"width": 1280, "height": 720},
        },
    }

    result = get_params_from_workflow(workflow_payload)
    expected = {"Node0": 42}
    assert result == expected


def test_get_params_from_workflow_loadimageoutput():
    """Covers the LoadImageOutput branch (empty string result)."""
    workflow_payload = {
        "0": {
            "_meta": {"title": "Loader"},
            "class_type": "LoadImageOutput",
            "inputs": {"image": "path/to/image.png"},
        }
    }
    result = get_params_from_workflow(workflow_payload)
    assert result == {"Loader": ""}


def test_prepare_workflow():
    """Ensure prepare_workflow updates prompt and preserves structure."""
    workflow_payload = {
        "0": {
            "_meta": {"title": "Example"},
            "class_type": "ImageGenerator",
            "inputs": {"prompt": "old prompt"},
        }
    }

    # Modify directly to simulate input update
    workflow_payload["0"]["inputs"]["prompt"] = "new prompt"
    result = prepare_workflow(workflow_payload)

    assert "0" in result
    assert "inputs" in result["0"]
    assert result["0"]["inputs"]["prompt"] == "new prompt"
    assert result["0"]["class_type"] == "ImageGenerator"


def test_prepare_workflow_primitive_update():
    """Ensure prepare_workflow replaces Primitive inputs correctly."""
    workflow_payload = {
        "0": {
            "_meta": {"title": "Height"},
            "class_type": "PrimitiveInt",
            "inputs": {"value": 720},
        }
    }
    updated = prepare_workflow(workflow_payload, Height=1080)
    assert updated["0"]["inputs"]["value"] == 1080


def test_prepare_workflow_loadimageoutput(tmp_path: Path):
    """Covers LoadImageOutput handling with static [output] tag."""
    image_path = tmp_path / "photo.png"
    image_path.write_text("fake")

    workflow_payload = {
        "0": {
            "_meta": {"title": "Loader"},
            "class_type": "LoadImageOutput",
            "inputs": {"image": ""},
        }
    }

    updated = prepare_workflow(workflow_payload, Loader=str(image_path))
    expected_value = f"{image_path} [output]"
    assert updated["0"]["inputs"]["image"] == expected_value
