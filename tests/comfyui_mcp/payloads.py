from comfyui_mcp.base_types import (
    WorkflowParamType,
    WorkflowType,
)

valid_workflow_payload_base: WorkflowType = {
    "0": {"inputs": {"value": 720}, "class_type": "PrimitiveInt", "_meta": {"title": "height"}},
    "1": {"inputs": {"noise_seed": 0}, "class_type": "RandomNoise", "_meta": {"title": "RandomNoise"}},
    "2": {"inputs": {"value": 1280}, "class_type": "PrimitiveInt", "_meta": {"title": "width"}},
}

valid_workflow_payload_image: WorkflowType = valid_workflow_payload_base | {
    "3": {
        "inputs": {"image": "_output_images_will_be_put_here [outputs]"},
        "class_type": "LoadImageOutput",
        "_meta": {"title": "image_0"},
    },
}

valid_workflow_payload_modified_base: WorkflowType = {
    "0": {"inputs": {"value": 1080}, "class_type": "PrimitiveInt", "_meta": {"title": "height"}},
    "1": {"inputs": {"noise_seed": 0}, "class_type": "RandomNoise", "_meta": {"title": "RandomNoise"}},
    "2": {"inputs": {"value": 1920}, "class_type": "PrimitiveInt", "_meta": {"title": "width"}},
}

valid_workflow_payload_modified_image: WorkflowType = valid_workflow_payload_modified_base | {
    "3": {
        "inputs": {"image": "Comfy [outputs]"},
        "class_type": "LoadImageOutput",
        "_meta": {"title": "image_0"},
    },
}

valid_workflow_params_base: WorkflowParamType = {
    "height": 720,
    "width": 1280,
}

valid_workflow_params_image: WorkflowParamType = valid_workflow_params_base | {
    "image_0": "_output_images_will_be_put_here [outputs]",
}

workflow_params_modified_base: WorkflowParamType = {
    "height": 1080,
    "submit_batch": 1,
    "width": 1920,
}

workflow_params_modified_image: WorkflowParamType = workflow_params_modified_base | {
    "image_0": "Comfy",
}
