# MediX Web 部署方案

## 目标架构

推荐生产部署使用一体化后端服务：

```text
Browser
  -> Nginx / HTTPS
  -> aiohttp web_app.py
      -> /static/* 静态前端
      -> /api/chat SwarmCoordinator
      -> LLM API / Mem0 / Milvus Lite
```

本地开发也可以拆成两层：

```text
python static_preview.py     # 127.0.0.1:8080，只看静态页面，同时代理 /api/*
python web_app.py            # 127.0.0.1:7864，真实后端
```

## 本地启动

1. 启动真实后端：

```powershell
cd D:\workfile\medix-agent-swarm
C:\Conda\miniconda3\envs\medix-swarm\python.exe web_app.py --host 127.0.0.1 --port 7864
```

2. 可选：启动静态预览代理：

```powershell
cd D:\workfile\medix-agent-swarm
$env:MEDIX_BACKEND_URL="http://127.0.0.1:7864"
C:\Conda\miniconda3\envs\medix-swarm\python.exe static_preview.py
```

访问：

```text
http://127.0.0.1:8080
```

如果不需要静态预览，直接访问后端一体服务：

```text
http://127.0.0.1:7864
```

## Linux 服务器部署

1. 准备 Python 环境：

```bash
cd /opt/medix-agent-swarm
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. 配置密钥。

不要把 API key 写死在 `config.py`。建议改为环境变量或 `.env`：

```bash
export LLM_API_KEY="..."
export MEM0_API_KEY="..."
```

3. 初始化知识库：

```bash
python knowledge/scripts/import_hardcoded_data.py
```

4. 启动服务：

```bash
python web_app.py --host 127.0.0.1 --port 7864
```

5. 用 Nginx 暴露公网 HTTPS。

参考 [nginx-medix.conf](nginx-medix.conf)。

6. 用 systemd 保活。

参考 [medix-web.service](medix-web.service)。

## 生产注意事项

- Web 后端进程必须能访问 LLM API、Mem0 和本地 Milvus Lite。
- `web_app.py` 内部复用一个 `SwarmCoordinator`，不要每个请求重启进程。
- Milvus Lite 数据目录 `knowledge/data/milvus_lite.db` 需要随服务部署并保持可写。
- 建议只让 Nginx 暴露公网端口，`web_app.py` 绑定 `127.0.0.1`。
- Windows 控制台可能因 emoji 产生 GBK 编码错误，生产环境建议设置 `PYTHONIOENCODING=utf-8`。
- 当前医疗回答仅供参考，生产使用前需要补齐皮肤科、过敏、药物相互作用等知识库，并增加审计日志。
