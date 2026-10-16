# syntax=docker/dockerfile:1.7
# Estágio 1: compila gsplat e fused-ssim (CUDA) com o toolkit completo.
FROM nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04 AS build
ENV DEBIAN_FRONTEND=noninteractive \
    TORCH_CUDA_ARCH_LIST="8.0;8.6;8.9" \
    MAX_JOBS=2 \
    UV_PYTHON_INSTALL_DIR=/opt/python \
    UV_LINK_MODE=copy
RUN apt-get update && apt-get install -y --no-install-recommends git build-essential ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /usr/local/bin/uv

# venv do treino (o requirements do gsplat traz outro pacote chamado pycolmap: fica isolado aqui)
# A trava impede que o requirements dos exemplos troque o torch (sem ela o uv puxa o mais novo,
# que não casa com o gsplat compilado e estoura o disco do runner).
RUN printf 'torch==2.5.1+cu124\nnumpy<2\n' > /opt/train-constraints.txt \
    && uv venv -p 3.11 /opt/train \
    && uv pip install -p /opt/train torch==2.5.1 --index-url https://download.pytorch.org/whl/cu124 \
    && uv pip install -p /opt/train -c /opt/train-constraints.txt ninja setuptools wheel numpy
# --recurse-submodules: o glm (cabeçalhos do CUDA) vem como submódulo
RUN git clone --depth 1 --recurse-submodules --shallow-submodules -b v1.5.3 https://github.com/nerfstudio-project/gsplat /opt/gsplat \
    && uv pip install -p /opt/train --no-build-isolation -c /opt/train-constraints.txt /opt/gsplat
RUN uv pip install -p /opt/train --no-build-isolation -c /opt/train-constraints.txt \
        --extra-index-url https://download.pytorch.org/whl/cu124 --index-strategy unsafe-best-match \
        -r /opt/gsplat/examples/requirements.txt \
    && /opt/train/bin/python -c "import torch; assert torch.__version__ == '2.5.1+cu124', torch.__version__"

# venv do motor
COPY pyproject.toml README.md /src/engine/
COPY src /src/engine/src
RUN uv venv -p 3.11 /opt/engine \
    && uv pip install -p /opt/engine /src/engine pycolmap-cuda12==4.2.1

# Estágio 2: só o runtime.
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl ca-certificates libgl1 libglib2.0-0 \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @playcanvas/splat-transform@3.10.1 \
    && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/* /root/.npm
COPY --from=build /opt/python /opt/python
COPY --from=build /opt/train /opt/train
COPY --from=build /opt/engine /opt/engine
COPY --from=build /opt/gsplat /opt/gsplat
WORKDIR /work
ENTRYPOINT ["/opt/engine/bin/python", "-m", "visitta_engine"]
CMD ["run"]
