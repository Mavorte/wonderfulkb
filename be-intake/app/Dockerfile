FROM python:3.12-slim AS package-builder
WORKDIR /build
COPY be-document-processing/pyproject.toml be-document-processing/requirements.txt ./
COPY be-document-processing/src ./src
RUN pip wheel --no-deps --wheel-dir /wheels .

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY --chmod=644 be-intake/app/requirements.txt .
RUN pip install -r requirements.txt
COPY --from=package-builder /wheels /wheels
# Intake supplies the audit subset's boto3/botocore; do not install worker dependencies.
RUN pip install --no-deps /wheels/*.whl && rm -rf /wheels
COPY --chmod=644 be-intake/app/main.py be-intake/app/content_hashes.py be-intake/app/processing_monitor_lifecycle_routes.py be-intake/app/processing_monitor_authorization.py .
COPY --chmod=644 be-intake/app/processing_monitor_routes.py .
COPY --chmod=644 be-intake/app/processing_monitor_page_routes.py .
COPY --chmod=644 be-intake/app/processing_monitor_step_routes.py .
RUN useradd -r -u 10001 app
USER app
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--no-server-header"]
