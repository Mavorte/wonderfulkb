# Worker image: the same directory layout as infra/validator-agent (pipeline imports its siblings by path).
# Build context is build/pkg, staged by build.sh (never build from here directly).
FROM public.ecr.aws/lambda/python:3.14
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir --only-binary :all: -r ${LAMBDA_TASK_ROOT}/requirements.txt --target ${LAMBDA_TASK_ROOT}
COPY trigger ${LAMBDA_TASK_ROOT}/trigger
COPY document_processing ${LAMBDA_TASK_ROOT}/document_processing
COPY pipeline ${LAMBDA_TASK_ROOT}/pipeline
COPY classify ${LAMBDA_TASK_ROOT}/classify
COPY embed ${LAMBDA_TASK_ROOT}/embed
COPY dedup ${LAMBDA_TASK_ROOT}/dedup
COPY signatures ${LAMBDA_TASK_ROOT}/signatures
COPY privacy ${LAMBDA_TASK_ROOT}/privacy
COPY regions ${LAMBDA_TASK_ROOT}/regions
CMD ["trigger.worker_handler.handler"]
