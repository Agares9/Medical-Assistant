# Docker 部署

## 1. 服务器准备

服务器需要安装 Docker 和 Docker Compose v2。

```bash
docker --version
docker compose version
```

建议目录：

```bash
/www/wwwroot/medix
```

## 2. 上传代码

```bash
cd /www/wwwroot
git clone <your-repo-url> medix
cd /www/wwwroot/medix
```

如果不是 Git 仓库，可以把当前项目目录整体上传到服务器。

## 3. 配置环境变量

```bash
cp .env.example .env
nano .env
```

至少填写：

```env
LLM_API_KEY=你的模型接口密钥
LLM_MODEL_NAME=deepseek-v4-flash
LLM_BASE_URL=https://api.deepseek.com
MEM0_API_KEY=你的Mem0密钥
ICD_API_CLIENT_ID=你的WHO ICD API ClientId
ICD_API_CLIENT_SECRET=你的WHO ICD API ClientSecret
```

不要把 `.env` 提交到仓库。

## 4. 准备知识库数据

项目已有 `knowledge/data/documents` 和 Milvus Lite 数据目录时，可以直接随代码上传。

如果服务器上需要重新导入：

```bash
docker compose run --rm medix-web python knowledge/scripts/import_hardcoded_data.py
```

推荐使用新的统一构建脚本，先预览再重建：

```bash
docker compose run --rm medix-web python knowledge/scripts/build_knowledge_base.py --preview
docker compose run --rm medix-web python knowledge/scripts/build_knowledge_base.py --rebuild
```

统一构建脚本会同时读取：

```text
knowledge/data/documents
knowledge/data/icd11_preview
knowledge/data/clinical_paths_cleaned_by_department
```

如果需要先下载 ICD-11 常见病种子集：

```bash
docker compose run --rm medix-web python knowledge/scripts/download_icd11_common.py
docker compose run --rm medix-web python knowledge/scripts/build_knowledge_base.py --rebuild
```

注意：首次运行会下载 embedding 模型，耗时较长。

## 5. 构建并启动

```bash
docker compose up -d --build
```

Compose 会启动两个服务：

```text
medix-web    # Web + Agent 后端
medix-redis  # 最近对话列表缓存
```

查看日志：

```bash
docker compose logs -f medix-web
```

访问：

```text
http://服务器IP:7864
```

如果你只想在服务器本机访问，可以把端口改成：

```yaml
ports:
  - "127.0.0.1:7864:7864"
```

健康检查：

```bash
curl http://127.0.0.1:7864/api/health
```

## 6. 常用运维命令

重启：

```bash
docker compose restart medix-web
```

停止：

```bash
docker compose down
```

更新代码后重新构建：

```bash
git pull
docker compose up -d --build
```

进入容器：

```bash
docker compose exec medix-web bash
```

## 7. 数据持久化

`docker-compose.yml` 已挂载：

```text
./knowledge/data -> /app/knowledge/data
./memory         -> /app/memory
medix-hf-cache   -> /app/.cache/huggingface
medix-redis-data -> Redis AOF 数据
```

这些分别用于：

- Milvus Lite 本地知识库
- 验证记录、会话记录、长期记忆辅助文件
- HuggingFace embedding 模型缓存
- 最近对话列表

## 8. 推荐公网部署

生产环境建议不要直接暴露容器端口到公网，而是：

```text
Nginx / HTTPS -> 127.0.0.1:7864 -> medix-web
```

Nginx 示例见：

```text
deploy/nginx-medix.conf
```

如果只想监听本机，把 compose 端口改成：

```yaml
ports:
  - "127.0.0.1:7864:7864"
```

然后由 Nginx 反向代理。

## 9. 注意事项

- 当前镜像会安装 `torch`、`sentence-transformers`、`pymilvus`，体积较大，首次构建较慢。
- 容器必须能访问 LLM API 和 Mem0。
- `config.py` 已改为优先读取环境变量。
- 如果使用云服务器安全组，需要放行 7864 或 Nginx 的 80/443。
- 医疗咨询内容仅供参考，正式使用前需要补齐知识库和审计策略。
