# 国内网络与本地 PoC

## 已落地的两级方案

### 1. iPhone 本地 Vision 前检（已运行）

App 在上传前本地完成单人脸、清晰度、亮度、边缘、遮挡、正面/45°角度和重复图片检查。它不产生 API 调用，热路径在固定测试图上约 9 ms，可直接减少无效上传和无效生成成本。

macOS 可复现命令：

```bash
bash scripts/run_local_vision_poc.sh backend/tests/live_assets/*.jpg
```

### 2. 阿里云百炼 Qwen 图片编辑（代码级 PoC）

后端增加 `IMAGE_PROVIDER=qwen`。请求支持原图、上一版和结构化反馈，返回后仍进入与 OpenAI/Gemini 相同的确定性前检、多模态质量门、最多两轮纠偏和原图安全回退。

```dotenv
IMAGE_PROVIDER=qwen
QWEN_API_KEY=your-server-side-key
QWEN_IMAGE_ENDPOINT=https://YOUR_WORKSPACE.cn-beijing.maas.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
QWEN_IMAGE_MODEL=qwen-image-edit-plus
```

当前仓库已经验证 Qwen 请求结构、尺寸约束、HTTPS 下载域名限制与服务端配置分流；由于没有百炼 Key，没有声称 Qwen 的真实人像质量已经通过。正式切换前必须用同一固定集跑 `live_acceptance.py` 与 `revision_acceptance.py`。

## 部署取舍

| 方案 | 国内网络 | 端侧成本 | 质量/运维结论 |
|---|---|---:|---|
| iPhone Vision | 最稳定，无外网依赖 | 0 API 费用 | 适合输入前检，不负责生成 |
| Qwen 百炼托管 | 国内链路友好 | 按图计费 | 已接好 Provider；需补同集真实验收 |
| Qwen3-VL 自托管 | 可完全内网 | GPU 与运维成本 | 适合分析/裁判，不建议第一阶段承担高保真人像编辑 |
| OpenAI/Gemini | 质量基准与降级路径 | 按调用计费 | 当前真实验收由 OpenAI 生成与裁判通过；Key 只在服务端 |

阿里云官方文档给出的 `qwen-image-edit-plus` 当前北京区价格为 0.2 元/张，且说明输出 URL 只保留 24 小时；因此代码在服务端立即下载结果，不把临时 URL交给手机。价格和接口规则以正式上线当天的官方页面为准。

官方资料：[阿里云模型价格](https://help.aliyun.com/zh/model-studio/model-pricing)、[Qwen Image Edit API](https://help.aliyun.com/en/model-studio/qwen-image-edit-api)、[Qwen3-VL 自托管说明](https://github.com/QwenLM/Qwen3-VL/blob/main/README.md)、[OpenAI GPT Image 2](https://developers.openai.com/api/docs/models/gpt-image-2)。
