# GitHub Actions Docker 自动构建配置

## 配置步骤

### 1. 在 GitHub 仓库中配置 Secrets

进入 GitHub 仓库设置页面：
1. 点击 **Settings** → **Secrets and variables** → **Actions**
2. 添加以下两个 Secrets：

| Secret 名称 | 值 | 说明 |
|------------|-----|------|
| `DOCKER_USERNAME` | `lunare` | Docker Hub 用户名 |
| `DOCKER_PASSWORD` | `<你的 Docker Hub 访问令牌>` | Docker Hub 访问令牌（不是密码） |

### 2. 创建 Docker Hub 访问令牌

1. 登录 [Docker Hub](https://hub.docker.com/)
2. 点击右上角头像 → **Account Settings** → **Security**
3. 点击 **New Access Token**
4. 输入描述（如 `github-actions`）
5. 权限选择 **Read & Write**
6. 点击 **Generate** 并复制生成的令牌
7. 将令牌粘贴到 GitHub Secrets 的 `DOCKER_PASSWORD` 中

## 工作流说明

### 触发条件
- 推送到 `main` 分支时自动构建
- 创建 Pull Request 时测试构建（不推送）
- 手动触发（workflow_dispatch）

### 构建架构（独立镜像）
- **AMD64** (`linux/amd64`) - Intel/AMD x86_64 处理器
  - 标签: `amd64`, `latest-amd64`
- **ARM64** (`linux/arm64`) - ARM64 架构（Apple Silicon、树莓派）
  - 标签: `arm64`, `latest-arm64`

两个架构并行构建，互不影响。

## 镜像使用

构建完成后，根据您的系统架构选择对应的镜像：

```bash
# AMD64 系统
docker pull lunare/sense-sherpa-api:amd64

# ARM64 系统（如 Mac M1/M2/M3、树莓派）
docker pull lunare/sense-sherpa-api:arm64

# 运行容器
docker run -d \
  --name sensevoice-asr \
  -p 8000:8000 \
  -v $(pwd)/models:/app/models \
  lunare/sense-sherpa-api:amd64
```

## 查看构建状态

访问 GitHub 仓库的 **Actions** 标签页查看构建状态和日志。
