# 小美说 · Algorithm Review Package

这是“小美说”iOS v1.2.0 的外部算法评审仓库。仓库只包含评审、开发和测试所需的 SwiftUI 客户端、FastAPI 模型网关、生成裁判系统与非隐私测试定义。

## 评审重点

- OpenAI 多模态审美画像、修图方案与医美目标分析
- Gemini 图片编辑与候选生成
- 统一生成流水线：输入前检 → 方案编译 → 候选生成 → 几何检测 → 多模态质检 → 候选排序 → 定向纠偏 → 安全回退
- 身份保护、画幅保护、未选部位锁定、目标变化验收
- 医美多方向集合完整性与 V2/V3 原图基线
- 时延、成本与质量门槛优化

## 目录

```text
ios/       SwiftUI iOS App
backend/   FastAPI 模型网关与生成裁判
docs/      算法与安全边界
scripts/   分享前安全扫描
```

## 本地运行

后端默认使用 `mock` 模式，不需要任何 API Key：

```bash
cp .env.example backend/.env
cd backend
./setup.sh
./run.sh
```

需要真实模型时，请只在本机 `backend/.env` 中填写你自己的测试 Key。该文件已被 `.gitignore` 排除，禁止把任何 Key 提交到 Git。

iOS 项目默认连接本机 Mock 后端：

```bash
open ios/Xiaomeishuo.xcodeproj
```

如需连接自有测试服务，在本机创建 `ios/Config/Cloud.xcconfig`：

```text
XMS_API_HOST = your-test-api.example.com
XMS_APP_ACCESS_TOKEN = your-temporary-test-token
```

`Cloud.xcconfig` 也已被 Git 排除。

## 隐私与外部资源边界

- 仓库不含 OpenAI、Google、GitHub 或云平台凭证。
- 仓库不含线上 Cloud Run 地址、App Token、Apple Team ID、开发证书或 Provisioning Profile。
- 仓库不含真实用户照片、审美档案、联系方式或生成历史。
- 公开收藏夹功能只读取用户主动提供的 `https://www.xiaohongshu.com/board/...` 公开网页。
- 不包含小红书 Cookie、登录态、SSO、内部 Header、内部域名、内部 API、内部 CDN、内部 SDK 或公司文档。
- 服务端不建立长期用户数据库，也不持久化上传图片。

## 自动验证

```bash
./scripts/security_scan.sh
cd backend && python -m pytest -q
```

真实模型验收使用仓库内的非隐私合成人像，输出包含逐张前后对比、质量分、失败码和耗时的 HTML 报告：

```bash
cd backend
MODEL_MODE=live \
IMAGE_PROVIDER=openai \
OPENAI_ANALYSIS_MODEL=gpt-4.1-mini \
OPENAI_JUDGE_MODEL=gpt-4.1 \
OPENAI_IMAGE_MODEL=gpt-image-2 \
GEMINI_IMAGE_MODEL=gemini-3.1-flash-image \
python scripts/live_acceptance.py
```

V2/V3 三图验收：

```bash
cd backend
MODEL_MODE=live IMAGE_PROVIDER=openai \
OPENAI_ANALYSIS_MODEL=gpt-4.1 OPENAI_JUDGE_MODEL=gpt-4.1 \
OPENAI_IMAGE_MODEL=gpt-image-2 \
python scripts/revision_acceptance.py
```

API Key 只通过本机环境变量或被 Git 排除的 `backend/.env` 提供；验收报告写入同样被排除的 `backend/acceptance_runs/`。

本轮实测结果见 [真实模型验收结果](docs/live-acceptance-result.md)。

详见 [算法评审说明](docs/algorithm-review.md)、[iPhone App 端到端验收](docs/mobile-acceptance.md)、[国内网络与本地 PoC](docs/china-provider-poc.md)、[算法优化落地方案](docs/optimization-solution.md) 与 [外部分享安全说明](docs/external-sharing-security.md)。
