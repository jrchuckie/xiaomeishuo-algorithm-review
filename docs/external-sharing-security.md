# 外部分享安全说明

## 已排除

- OpenAI、Google、GitHub 和云平台 API Key
- App Access Token、Cookie、OAuth Token、JWT 与服务账号文件
- 线上服务地址和部署项目标识
- Apple Developer Team ID、证书、私钥和 Provisioning Profile
- `.env`、本地 Xcode 配置、虚拟环境、构建缓存与设备日志
- 真实用户照片、画像、生成结果和联系方式
- 内部文档、内部迁移记录和内部产品对照材料

## 小红书边界

仓库保留一项用户可见产品能力：读取用户主动粘贴的公开收藏夹网页。

- 唯一允许的站点：`https://www.xiaohongshu.com/board/...`
- 使用普通公开 HTTPS 请求，不携带用户 Cookie 或登录态
- 不使用 SSO、内部 Header、内部域名、内部 CDN、内部 API 或内部 SDK
- 读取失败时降级为用户本地上传参考图

## 外包协作要求

- 外包方必须使用自己的测试 Key 与隔离的测试云项目。
- 禁止把 Key 放进 Swift、Python、Issue、PR、日志或截图。
- 禁止使用真实用户照片测试；只使用获得授权的测试素材或合成素材。
- 禁止将仓库、代码、Prompt、测试结果或模型输出再次分享给第三方。
- 交付 Pull Request 不得包含 `.env`、`Cloud.xcconfig` 或构建产物。
- 若扫描发现凭证，立即停止推送并通知仓库所有者轮换凭证。
