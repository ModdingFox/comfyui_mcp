import json
import time
from asyncio import sleep
from copy import deepcopy
from logging import getLogger
from typing import Any
from urllib.parse import quote

import backoff
import requests

from comfyui_mcp.argument_parser import ArgsComfyUI
from comfyui_mcp.base_types import (
    ComfyResult,
    HistoryEntry,
    HistoryResponse,
    InputTypes,
    PromptSuccessResponse,
    QueueResponse,
    WorkflowParamType,
    WorkflowType,
)
from comfyui_mcp.exceptions import (
    ExecutionFailedError,
    JobLostError,
    PromptValidationError,
    QueueValidationError,
    TimeoutError,
)

logger = getLogger(__name__)

class ComfyUIClient:
    def __init__(self, argscomfyui: ArgsComfyUI):
        self.host = argscomfyui.host
        self.max_retries = argscomfyui.max_retries
        self.request_timeout = argscomfyui.request_timeout
        self.queue_check_interval = argscomfyui.queue_check_interval
        self.lost_job_check_limit = argscomfyui.lost_job_check_limit
        self.max_wait_time = argscomfyui.max_wait_time

    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        @backoff.on_exception(
            backoff.expo,
            requests.RequestException,
            max_tries=self.max_retries,
            on_backoff=lambda details: logger.warning(
                f"Request retry {details['tries']} after {details['wait']:.2f}s"
            )
        )
        def _request():
            url = f"http://{self.host}{endpoint}"
            kwargs.setdefault('timeout', self.request_timeout)
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response

        return _request()

    def get_queue(self) -> QueueResponse:
        """Get and validate queue status"""
        response = self._make_request('GET', '/queue')
        raw_data = response.json()

        try:
            return QueueResponse.from_api_response(raw_data)
        except Exception as exception:
            logger.error(f"Failed to parse queue response: {exception}")
            logger.debug(f"Raw response: {json.dumps(raw_data, indent=2)}")
            raise QueueValidationError(f"Invalid queue response: {exception}")

    def get_history(self, prompt_id: str) -> HistoryResponse:
        """Get and validate history for a prompt"""
        response = self._make_request('GET', f'/history/{prompt_id}')
        raw_data = response.json()

        try:
            return HistoryResponse.from_api_response(raw_data)
        except Exception as exception:
            logger.error(f"Failed to parse history response: {exception}")
            logger.debug(f"Raw response: {json.dumps(raw_data, indent=2)}")
            raise QueueValidationError(f"Invalid history response: {exception}")

    def list_workflows(self, workflow_directory: str) -> list[dict[str, Any]]:
        """List workflows from a directory on ComfyUI server"""
        workflow_directory_urlencoded = quote(workflow_directory, safe="")
        response = self._make_request(
            'GET',
            f'/api/v2/userdata?path={workflow_directory_urlencoded}'
        )
        return response.json()

    def get_workflow(self, workflow_path: str) -> dict[str, Any]:
        """Get workflow data from ComfyUI server"""
        workflow_path_encoded = quote(workflow_path, safe="")
        response = self._make_request(
            'GET',
            f'/api/userdata/{workflow_path_encoded}'
        )
        return response.json()

    def convert_workflow(self, workflow_data: dict[str, Any]) -> WorkflowType:
        """Convert workflow UI format to API format"""
        response = self._make_request(
            'POST',
            '/workflow/convert',
            json=workflow_data
        )
        return response.json()

    def submit_prompt(self, workflow: WorkflowType) -> str:
        logger.info("Submitting prompt...")

        response = self._make_request(
            'POST',
            '/prompt',
            json={"prompt": workflow},
            headers={'Content-Type': 'application/json'}
        )
        result = response.json()

        try:
            success_response = PromptSuccessResponse.model_validate(result)
            logger.info(f"Prompt submitted: {success_response.prompt_id}")
            return success_response.prompt_id

        except Exception:
            error_msg = json.dumps(result, indent=2)
            logger.error(f"Prompt submission failed: {error_msg}")
            raise PromptValidationError(f"Prompt submission failed: {error_msg}")

    async def wait_for_completion(self, prompt_id: str) -> HistoryEntry:
        """Wait for job completion and return the history entry"""
        lost_job_counter = 0
        start_time = time.time()

        while True:
            if self.max_wait_time:
                elapsed = time.time() - start_time
                if elapsed > self.max_wait_time:
                    raise TimeoutError(
                        f"Job {prompt_id} exceeded max wait time: "
                        f"{elapsed:.1f}s > {self.max_wait_time}s"
                    )

            queue = self.get_queue()
            position_info = queue.find_prompt_position(prompt_id)

            if position_info:
                lost_job_counter = 0
                status, position, total = position_info

                if status == 'pending':
                    logger.info(f"Job {prompt_id} pending (position {position}/{total})...")
                elif status == 'running':
                    logger.info(f"Job {prompt_id} running...")

                await sleep(self.queue_check_interval)
                continue

            # Job is neither pending nor running - check history
            history = self.get_history(prompt_id)

            if history.is_empty() or not history.get_entry(prompt_id):
                lost_job_counter += 1
                logger.warning(
                    f"Job {prompt_id} not found in queue or history "
                    f"({lost_job_counter}/{self.lost_job_check_limit})"
                )

                if lost_job_counter >= self.lost_job_check_limit:
                    raise JobLostError(
                        f"Job {prompt_id} lost after {lost_job_counter} checks. "
                        f"Not in queue and no history available."
                    )

                await sleep(self.queue_check_interval)
                continue

            # Found in history
            lost_job_counter = 0
            entry = history.get_entry(prompt_id)

            logger.info(f"Job {prompt_id} status: {entry.status.status_str}")

            if entry.status.is_success():
                logger.info(f"Job {prompt_id} completed successfully")
                outputs = entry.get_output_filenames()

                for node_id, filenames in outputs.items():
                    logger.info(f"Job {prompt_id} - Node {node_id}: {len(filenames)} file(s)")

                return entry
            if entry.status.is_failed():
                raise ExecutionFailedError(
                    f"Job {prompt_id} failed with status '{entry.status.status_str}'"
                )
            logger.warning(f"Job {prompt_id} has unknown status: {entry.status.status_str}")
            await sleep(self.queue_check_interval)
            continue

    async def execute_workflow(self, workflow: WorkflowType) -> HistoryEntry:
        """Execute workflow and return complete history entry with outputs"""
        prompt_id = None
        try:
            prompt_id = self.submit_prompt(workflow)
            return await self.wait_for_completion(prompt_id)
        except KeyboardInterrupt:
            if prompt_id:
                logger.warning(f"Interrupted! Job {prompt_id} may still be running on server.")
            raise

async def call_workflow(argscomfyui: ArgsComfyUI, workflow: WorkflowType) -> list[ComfyResult]:
    """Execute a workflow and return results"""
    results = []

    client = ComfyUIClient(argscomfyui)
    history_entry = await client.execute_workflow(workflow)

    # Process outputs using the actual media_type from the node outputs
    for node_id, node_output in history_entry.outputs.items():
        all_outputs = node_output.get_all_outputs()

        for media_type, output_list in all_outputs.items():
            for output_file in output_list:
                file_link = f"http://{argscomfyui.host}/api/view?filename={output_file.filename}"
                results.append(ComfyResult(media_type=media_type, filename=file_link))

    return results

def get_params_from_workflow(workflow: WorkflowType) -> WorkflowParamType:
    result: WorkflowParamType = {}
    for value in workflow.values():
        class_type: str = value["class_type"]
        _meta: dict[str, str] = value["_meta"]
        inputs: dict[str, InputTypes] = value["inputs"]
        _meta_title: str = _meta["title"]
        inputs_value: InputTypes | None = inputs.get("value")
        if class_type == "PrimitiveFloat" and inputs_value is not None:
            result[_meta_title] = float(inputs_value)
        elif class_type.startswith("Primitive") and inputs_value is not None:
            result[_meta_title] = inputs_value
        elif class_type == "LoadImageOutput":
            result[_meta_title] = ""
    return result

def prepare_workflow(workflow: WorkflowType, **kwargs) -> WorkflowType:
    result_workflow = deepcopy(workflow)
    for key, value in result_workflow.items():
        class_type: str = value["class_type"]
        _meta: dict[str, str] = value["_meta"]
        _meta_title: str = _meta["title"]
        if kwargs.get(_meta_title):
            input_value = kwargs[_meta_title]
            if class_type.startswith("Primitive"):
                result_workflow[key]["inputs"]["value"] = input_value
            elif class_type == "LoadImageOutput":
                result_workflow[key]["inputs"]["image"] = f"{input_value} [output]"
    return result_workflow
