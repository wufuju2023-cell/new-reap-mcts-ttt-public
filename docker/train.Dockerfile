# reap-train: 训练环境（torch/peft/trl on ROCm base）
# 注意: base 由 AMD 官方 rocm/pytorch 提供（大型镜像 ~8GB；构建建议走 CI，见 .github/workflows/docker.yml）
# 构建: podman build -f docker/train.Dockerfile -t reap-train:local .
#      （本机可加 --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple/ 加速）
FROM rocm/pytorch:rocm7.2.4_ubuntu24.04_py3.12_pytorch_release_2.10.0
ARG PIP_INDEX_URL=https://pypi.org/simple/
WORKDIR /workspace
COPY app/requirements.lock /tmp/requirements.lock
RUN python3 -m pip install --no-cache-dir -r /tmp/requirements.lock \
    --index-url ${PIP_INDEX_URL}
COPY app/ /workspace/app/
ENV PYTHONPATH=/workspace/app
CMD ["python3", "/workspace/app/policy_server.py", "--help"]
