# Railway 部署

本服务同时提供网页和 API，保持单实例运行。课程数据和附件必须放在持久卷中。

## 服务配置

从 GitHub 仓库部署时，Root Directory 设为 `/platform`，配置文件指定 `/platform/railway.json`。本目录的 Dockerfile 构建 Python 服务，`/api/health` 用作健康检查。

1. 添加持久卷，挂载 `/data`，再启动部署。
2. 设置变量：

   ```dotenv
   COURSE_DATA_DIR=/data
   APP_HOST=0.0.0.0
   RAILWAY_RUN_UID=0
   MAX_UPLOAD_MB=20
   ```

   Railway 的卷默认归 root 所有；`RAILWAY_RUN_UID=0` 是平台文档给出的写入兼容方式。应用优先读取平台 `PORT`，本机仍使用 `APP_PORT`。20MB 是免费试用期的单文件限制，不是总存储配额。
3. 生成 Railway 公网域名，将 `APP_ORIGIN` 设置为完整 HTTPS 地址（无末尾斜杠），重新部署后再登录。
4. 初次启动会生成 47 门课程和负责人账号。首次密码保存在卷内 `/data/首次登录.txt`，使用 Railway CLI 下载到受控的本地目录，勿提交到 GitHub、构建日志或聊天中。
5. 验证首页、`/api/health`、登录与保存功能；重启后检查课程、账号及保存的方案仍存在。

## 免费试运行

部署前以 Railway 账号显示的套餐和额度为准。不要自动升级付费套餐。免费计划持久卷容量有限，暂不上传大型录播。免费额度不保证全天连续运行；保持异地备份，勿依赖试用期作为唯一数据存储。

当前配置未包含在线支付、真实 AI API 或邮件服务。数据库独立于本机实例；默认部署不会上传本机账号、询价、附件和密码。

参考：[CLI](https://docs.railway.com/cli)、[持久卷](https://docs.railway.com/volumes)、[配置文件](https://docs.railway.com/config-as-code/reference)。
