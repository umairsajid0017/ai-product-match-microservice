# syntax=docker/dockerfile:1.6
# Lambda container image for Everystore product-match (CPU OpenCLIP + FastAPI)

FROM public.ecr.aws/lambda/python:3.11 AS base

RUN yum install -y mesa-libGL libgomp \
    && yum clean all \
    && rm -rf /var/cache/yum

COPY requirements.txt ${LAMBDA_TASK_ROOT}/

RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir --only-binary=:all: "numpy==1.26.4" "Pillow==10.4.0" \
    && pip install --no-cache-dir \
         torch==2.4.1 torchvision==0.19.1 \
         --extra-index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt \
    && pip install --no-cache-dir --no-deps "open-clip-torch==2.24.0"

ENV TORCH_HOME=/opt/ml/torch
ENV OPEN_CLIP_CACHE_DIR=/opt/ml/open_clip
ENV HF_HOME=/opt/ml/hf
RUN mkdir -p /opt/ml/torch /opt/ml/open_clip /opt/ml/hf \
    && python - <<'PY'
import open_clip
print("Downloading ViT-B-32 openai weights...")
model, _, preprocess = open_clip.create_model_and_transforms(
    "ViT-B-32", pretrained="openai", device="cpu"
)
model.eval()
print("CLIP weights cached.")
PY

COPY app ${LAMBDA_TASK_ROOT}/app
COPY sql ${LAMBDA_TASK_ROOT}/sql

CMD ["app.lambda_handler.handler"]
