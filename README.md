# SenseVoice ASR API

基于 Sherpa-ONNX 的本地语音识别 API 服务，支持多语言、VAD 分段、ITN 数字规整。

## 主要功能

- ✅ 完全本地化运行，无需联网
- ✅ 支持 Web 界面和 REST API
- ✅ 多语言支持（中/英/日/韩）
- ✅ 语音活动检测（VAD）自动分段
- ✅ 音频降噪与预处理
- ✅ Docker 一键部署

## 快速开始

### 1. 准备模型文件

**注意**：`models/` 目录内容已被 Git 忽略，需要自行下载模型文件。

从 [Sherpa-ONNX Releases](https://github.com/k2-fsa/sherpa-onnx/releases) 下载以下文件到 `models/` 目录：

```
models/
  ├── model.int8.onnx
  ├── tokens.txt
  └── silero_vad.onnx
```

### 2. 安装依赖

```bash
pip install -r requirements_api.txt
```

### 3. 启动服务

```bash
python main_api.py \
  --sense-voice models/model.int8.onnx \
  --tokens models/tokens.txt \
  --silero-vad-model models/silero_vad.onnx
```

### 4. API 调用

```python
import requests

with open("audio.mp3", "rb") as f:
    response = requests.post(
        "http://localhost:8000/transcribe_file",
        files={"file": f}
    )
    result = response.json()
    print(result["text"])
```

## Docker 部署

```bash
# 启动服务
docker-compose up -d

# 访问 API
curl http://localhost:8022/docs
```

## 配置参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--language` | 语言 (zh/en/ja/ko/auto) | auto |
| `--use-itn` | ITN 数字规整 | 1 |
| `--port` | 服务端口 | 8000 |
| `--vad-max-speech` | 最大语音时长(秒) | 5.0 |

完整参数见 API 文档：`http://localhost:8000/docs`

## 技术栈

- [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) - 语音识别引擎
- [FastAPI](https://fastapi.tiangolo.com/) - API 服务框架
- [FFmpeg](https://ffmpeg.org/) - 音频处理
- [Docker](https://www.docker.com/) - 容器化部署

## 作者

**HeGenAI** - 老何的AIGC研究室
微信: hlsaig

## 许可证

MIT License
