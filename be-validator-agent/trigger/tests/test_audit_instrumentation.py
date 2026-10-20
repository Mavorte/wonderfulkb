import inspect

from trigger import worker_handler


def test_process_document_accepts_explicit_execution_context():
    parameters = inspect.signature(worker_handler.process_document).parameters
    assert "execution_context" in parameters
