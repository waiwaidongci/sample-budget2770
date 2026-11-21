# 榆灯重叠标签追加投放台

从重叠标签受众中找出值得追加投放的一群：开投前锁定每人的搜寻/复核归属、重叠标签和原分派，只用搜寻集选群，复核点击揭盲后按原分派计算差值与 95% 区间，页面以区间下限是否为正说明能否追加。原生 HTML/CSS/JavaScript 多模块工作席，所有统计由 Python 完成。

## 模拟业务
榆灯研究协作组在日常投放复盘里手工比对重叠标签：同一用户常同时带着「冬季关注」「高活跃」等多个标签，凭直觉挑人群容易把复核后才出现的效果当成依据。上游提供带重叠标签的合成受众名单；本应用接管归属登记、开投前锁定、搜寻选群、复核补报、揭盲核算与预算决策；下游负责人据区间下限定追加与保留原预算。

核心业务实体：CampaignPlan / AudienceMember / AudienceSelection / ValidationUnblind / BudgetDecision。源码 model/schema/service/controller/route 与前端 api/store/pages 完成链路，不依赖浏览器本地假数据。

## 功能与方法
- 投放计划、受众成员批量录入/编辑/删除；重名与非法点击明确拒绝。
- **开投前锁定**：每人的搜寻/复核归属、重叠标签、原分派一次冻结，生成归属 SHA256；锁定后成员表不可改。
- **搜寻选群**：只用搜寻集点击，按重叠标签比较「处理−对照」点击率差，取差值最大者作为候选人群。搜寻点击可更正，更正后可改选，历史结论仍保留。
- **复核揭盲**：只取一个完整复核批次，按开投前原分派汇总；补报在同批内覆盖旧值，已揭盲封存的批不再接收补报。缺报不记为零，列入缺报名单并排除。
- **区间与决策**：Newcombe 混合得分区间给出差值 95% 区间，区间下限 > 0 才建议追加；无论结论如何原预算照常。揭盲结论与复核决定均不可覆盖。
- 审计记录登录、成员录入、锁定、选群、更正、补报、揭盲、决定与导出；240 请求/分钟限流、全局可恢复错误。

## 快速启动
```bash
cp .env.example .env
docker compose up -d --build
docker compose exec -T backend python -m scripts.seed_demo
```
访问 http://localhost:18244 ，API http://localhost:19244/docs 。数据库映射 17744。无需 Node 构建。可以从中文和带空格目录启动。`docker compose down -v --remove-orphans` 会删除演示数据卷。

|角色|账号|密码|权限与典型动作|
|---|---|---|---|
|admin 负责人|admin@demo.local|Research2026!|全部读写、揭盲、归档复核、下载|
|analyst 分析师|analyst@demo.local|Research2026!|成员录入、锁定、选群、复核补报、导出；不能揭盲|
|viewer 观察员|viewer@demo.local|Research2026!|只读；仅可导出已复核结论|

## 一天的工作剧本
1. 09:00 admin 登录，查看「榆灯·冬季专题」当前阶段。
2. 09:10 analyst 在来源录入页批量粘贴受众：成员编号、重叠标签、搜寻/复核归属、原分派、搜寻点击。
3. 09:15 核对归属 SHA256 后点击锁定；成员表冻结。
4. 09:20 在搜寻选群页读取逐标签点击率差，锁定最大差值标签。
5. 09:35 复核点击陆续回收，按批次录入；缺报留空，不填零。
6. 09:45 admin 对一个完整批次揭盲，页面显示原分派差值、95% 区间与缺报名单。
7. 09:50 负责人按区间下限归档决策：下限为正则可追加，否则不加投；原预算照常。
8. 10:00 viewer 下载已复核结论 CSV，在操作留痕页核对下载事件。

seed 是 3 个前瞻设计计划，每个含 180 名合成受众（120 搜寻 / 60 复核，对照与处理各半），标签由固定种子 42 生成；本题用于开投前设计与流程演示，不伪造实验后因果结论。

## 技术与目录
|部分|实现|
|---|---|
|前端|原生 ES modules、HTML/CSS、Nginx1.27，无前端框架|
|API|Python3.11、FastAPI0.115、SQLAlchemy2、JWT、PBKDF2 密码|
|计算|SciPy1.15（Wilson / Newcombe 区间）|
|数据库|PostgreSQL16（测试可用 SQLite）|
|限流|Redis7 计数器，可选|

`frontend/src/` 分 api、stores、types、components/common、hooks、pages、router、utils、constants；`backend/src/` 分 config、models、schemas、services、controllers、routes、middlewares、utils、constants；`backend/scripts/seed_demo.py` 自然键插入、重复不覆盖修改；`backend/migrations/README.md` 说明 schema 版本。

环境变量 `.env.example`：COMPOSE_PROJECT_NAME、FRONTEND_PORT、BACKEND_PORT、DB_PORT、DB_PASSWORD、JWT_SECRET、SEED_DEMO。开发时在本地 venv 安装 backend/requirements.txt，设置 DATABASE_URL、REDIS_URL（可留空跳过限流）、JWT_SECRET 再运行 uvicorn；前端开发经 Nginx 代理 `/api/` 到不带前缀的 API。

共享枚举：角色 admin/analyst/viewer，阶段 unlocked/locked/selected/unblinded/reviewed，归属 search/validation，原分派 control/treatment，结论 can_expand/do_not_expand；后端 `src/constants/enums.py` 与前端 `src/types/enums.js` 使用同值。Google Fonts：Noto Serif SC + IBM Plex Mono；断网使用 serif/monospace 回退。

## 算法与复现
选群只读搜寻集，逐标签统计各臂点击与人数，取「处理−对照」点击率差最大且两臂都有人的标签。揭盲只用被选标签的复核集成员与你指定的那一个批次；有报告但点击留空、或整份未报，都算缺报并排除，绝不补零。差值区间采用 Newcombe 混合得分法（两比例独立、按原分派分组），默认 95%。判定规则固定为区间下限 > 0 才建议追加，原预算照常。归属 SHA256 与搜寻指纹分别用于锁定校验和改选检测。

已知边界：小型本地研究应用，使用合成数据，不含企业 SSO 与外发邮件；结果由人工复核，不自动执行业务决策。开投后新增成员或改归属是不允许的，需要另建计划；未做多重比较校正，选群使用的搜寻集与揭盲使用的复核集分离即为方法边界。

MIT License。
