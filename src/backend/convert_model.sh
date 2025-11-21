#!/usr/bin/env bash
set -e

# Resolve the directory this script lives in
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cd ~

python export_yolo11.py \
    -w "${SCRIPT_DIR}/models/model.pt" \
    -s 540 960 \
    --simplify \
    --batch 1

rm -f "${SCRIPT_DIR}/cv_process/model_b1_gpu0_fp16.engine"

echo "Created ${SCRIPT_DIR}/models/model.pt.onnx"
echo "Next run of deepstream will create the TensorRT engine file at ${SCRIPT_DIR}/models/model_b1_gpu0_fp16.engine"