# Image tunggal untuk finrag-api dan finrag-worker (Architecture.md 3.1).
# Build: docker buildx build --platform linux/amd64 --provenance=false -t ECR_URL:TAG --push .
FROM public.ecr.aws/lambda/python:3.12

# Dependensi dikunci lewat uv.lock. Ekspor ke requirements tanpa memasang paket proyek.
COPY pyproject.toml uv.lock ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir uv \
 && uv export --frozen --no-dev --no-hashes --no-emit-project --no-header > /tmp/requirements.txt \
 && pip install --no-cache-dir -r /tmp/requirements.txt \
 && rm -f ${LAMBDA_TASK_ROOT}/pyproject.toml ${LAMBDA_TASK_ROOT}/uv.lock

# Ekstensi MotherDuck dipasang saat build agar tidak diunduh pada cold start (Architecture.md 3.1).
# Lokasi ekstensi di /opt, karena home di Lambda hanya tulis ke /tmp.
RUN python -c "import duckdb; c = duckdb.connect(); c.sql(\"SET extension_directory='/opt/duckdb_ext'\"); c.sql('INSTALL motherduck'); print('motherduck extension installed')"

COPY app/ ${LAMBDA_TASK_ROOT}/app/
COPY config/ ${LAMBDA_TASK_ROOT}/config/

# Handler default; Terraform menimpa dengan image_config.command per fungsi.
CMD ["app.lambda_api.handler"]
