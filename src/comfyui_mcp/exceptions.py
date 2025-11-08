class ComfyUIException(Exception):
    """Base exception for all ComfyUI client errors"""

class PromptSubmissionError(ComfyUIException):
    """Raised when prompt submission fails"""

class PromptValidationError(ComfyUIException):
    """Raised when prompt validation fails"""

class JobLostError(ComfyUIException):
    """Raised when a job is lost from queue and history"""

class ExecutionFailedError(ComfyUIException):
    """Raised when workflow execution fails"""

class TimeoutError(ComfyUIException):
    """Raised when job execution exceeds max wait time"""

class QueueValidationError(ComfyUIException):
    """Raised when queue or history response validation fails"""
