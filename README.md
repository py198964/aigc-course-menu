# AI微课工坊

AI视频创作，从工具应用到专业交付。面向院校教学、企业培训与个人进修的模块化课程平台。

**[访问公开课程站](https://py198964.github.io/aigc-course-menu/) · [下载完整系统](https://github.com/py198964/aigc-course-menu/releases/latest) · [服务器部署说明](platform/README.md)**

## 在线课程站

GitHub Pages 发布新版品牌、课程目录与组课页面，包含 **47门课程、75小时内容、13个转绘专题模块**。

- F/T/P/B 四类课程分色，支持搜索、方向筛选、学习路径和 1—7 天培训模板。
- 课程详情分为概览、大纲、资料三个页签，提供完整教学目标、分时课纲、实践任务与评价标准。
- 购物车选课、调整顺序、先修检查、按日排课与参考价汇总。
- 浏览器规则组课、课程简介和宣传摘要、JSON方案导入导出、Markdown教案和打印PDF。
- PPT、录课视频与配套资料保留展示区域，公开站暂无上传的教学文件。

**公开站不提供机构账号、发布审核、询价报价或资料上传服务。** GitHub Pages [只托管静态网页](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)。在线组合保存在当前浏览器，规则组课无需登录、不调用外部AI；有需要时请导出文件保存。

## 完整机构系统

`platform/` 包含 FastAPI 后端、SQLite 数据库及完整管理界面，支持：

- 人员与组织权限、指定邮箱邀请、讲师草稿、管理员审核、课程版本留存。
- 每模块按班次参考定价（默认0元）、客户方案与询价快照、项目报价及客户确认。
- PPT/PPTX下载、PDF在线预览、MP4/WebM播放及下载，资源按公开/机构/项目授权。
- 规则组课和可配置的真实AI文案接口，服务器备份及Docker Compose部署。

本机默认地址 `http://127.0.0.1:8765`。要让其他人使用机构业务，需要按[部署说明](platform/README.md)启动后端并配置公网域名；GitHub上的公开站与本机数据库不会自动同步。

## 更新公开站

在仓库目录执行：

```powershell
python platform/build_pages.py
```

构建脚本从已审核的 `platform/seed_courses.json` 生成公开目录，移除策划提示词，只复制明确列出的前端文件至 `public/` 并更新根目录 `index.html`。GitHub Pages 从 `main` 分支根目录自动发布。

账户、密码、API密钥、运行数据库、客户资料与测试资源均不纳入版本控制或部署包。仓库中的初始课程和课程策划元数据属于公开示例内容，不是机密信息。
