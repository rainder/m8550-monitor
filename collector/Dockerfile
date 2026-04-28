FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv==0.8.*

WORKDIR /build
COPY pyproject.toml uv.lock ./
COPY src ./src

RUN uv pip install --system --no-cache .


FROM python:3.12-slim

RUN useradd --system --uid 1000 collector
USER collector

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/m8550-collector /usr/local/bin/m8550-collector

CMD ["m8550-collector"]
