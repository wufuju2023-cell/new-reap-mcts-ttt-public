# reap-lean(CI 自包含版): lean 4.28.0-rc1(官方 release) + reap clone + lake build
# CI 在 GitHub US runner 上从官方 release 下载（~100MB/s），不依赖私有 base/手工传输。
# 本机构建复用同文件亦可（需外网 release 可达）。
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
    zstd ca-certificates git curl && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /opt && \
    curl -fsSL -o /tmp/lean.tar.zst \
      https://github.com/leanprover/lean4/releases/download/v4.28.0-rc1/lean-4.28.0-rc1-linux.tar.zst && \
    cd /opt && tar -I zstd -xf /tmp/lean.tar.zst && \
    mv lean-4.28.0-rc1-linux lean && rm /tmp/lean.tar.zst
ENV PATH=/opt/lean/bin:$PATH
RUN git clone --depth 1 https://github.com/IQuestLab/reap.git /workspace/reap
WORKDIR /workspace/reap
RUN lake build
ENV LAKE_HOME=/workspace/reap
CMD ["lean", "--version"]
