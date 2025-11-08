from dataclasses import dataclass

from jsonargparse import ArgumentParser, Namespace
from pydantic import BaseModel, Field


class ArgsComfyUI(BaseModel):
    host: str = Field(default="127.0.0.1:8188", description="ComfyUI host:port")
    request_timeout: int = Field(default=30, description="Timeout for requests to ComfyUI")
    max_retries: int = Field(default=5, ge=1, description="Maximum number of retries")
    queue_check_interval: float = Field(default=2.0, ge=0.1, description="Queue polling interval in seconds")
    lost_job_check_limit: int = Field(default=10, ge=1, description="Max checks before considering job lost")
    max_wait_time: float | None = Field(
        default=None, ge=1.0, description="Maximum time to wait for job completion (None = infinite)"
    )
    use_remote_workflow: bool = Field(
        default=True,
        description="True pulls workflow from comfyui directly. False uses a local directory path containing the json files",
    )
    workflow_directory: str = Field(default="workflows", description="Path to load workflows from")


class ArgsGenerate(BaseModel):
    # \n before and after audio tags required to make open-webui render correctly added to others to be consistent
    audio_url_template: str = Field(
        default="\nResult {index}\n<details><audio controls>\n{url}\n</audio></details>\n",
        description="Template to use for generated audio items. Template vars: index and url",
    )
    image_url_template: str = Field(
        default="\n![Result {index}]({url})\n",
        description="Template to use for generated image items. Template vars: index and url",
    )
    unknown_url_template: str = Field(
        default="\n[Result {index}]({url})\n",
        description="Template to use for unknown generated items. Template vars: index and url",
    )
    nothing_generated_message: str = Field(
        default="Tool call succeeded but nothing was generated",
        description="Message to return when called and nothing generated",
    )
    reply_include_workflow: bool = Field(
        default=True, description="If the reply will contain the executed workflow info"
    )
    reply_workflow_format_indent: int = Field(default=2, description="Json indentation level")
    reply_workflow_format_sort_keys: bool = Field(default=True, description="Json sort keys or leave them as they are")
    reply_workflow_template: str = Field(
        default="\n<details>\n<summary>payload.json</summary>\n{workflow_params}\n</details>\n",
        description="Template to use for returning the called params in the reply. Template vars: workflow_params",
    )
    result_generated_message_template: str = Field(
        default="Return the following to the user exactly as is in markdown format Do not provide any information before or after this in the output:\n{image_list}",
        description="Message to return when something was generated. Template vars: image_list",
    )


@dataclass
class Args:
    comfyui: ArgsComfyUI
    generate: ArgsGenerate


def get_application_args(args: list[str] | None = None) -> Args:
    _argument_parser: ArgumentParser = ArgumentParser()
    _argument_parser.add_class_arguments(ArgsComfyUI, "comfyui")
    _argument_parser.add_class_arguments(ArgsGenerate, "generate")
    _namespace_args: Namespace = _argument_parser.parse_args(args)
    _args = _argument_parser.instantiate_classes(_namespace_args)
    return Args(_args["comfyui"], _args["generate"])
