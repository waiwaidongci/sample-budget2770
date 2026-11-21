# 实际验证记录

环境：Python 3.11、SQLAlchemy 2.0、FastAPI 0.115、SciPy 1.15，SQLite 临时库（本机无 Docker/Postgres 时用于测试；生产用 PostgreSQL 16）。前端以 esbuild 打包后在 jsdom 中运行，直接请求真实后端进程。

## 自动化测试
`cd backend && python3 -m pytest tests -q` → 22 passed。

- `tests/test_analysis.py`：
  - Wilson 区间对已知值（5/10 → [0.2366, 0.7634]）。
  - Newcombe 区间对 Newcombe(1998) 发表示例（48/80 vs 56/70 → 0.2，区间约 [0.0524, 0.3339]）。
  - 选群只用搜寻集；无搜寻点击的成员不进入分母。
  - 缺报（`click=None` 或整份未报）不计为零，列入 missing 并从分母剔除。
  - 区间下限 ≤ 0 判 `do_not_expand`，> 0 判 `can_expand`。
  - 另用独立手写的 Wilson/Newcombe 实现交叉核对，结果一致到 1e-12。
- `tests/test_workflow.py`：锁定前不能选群；锁定后成员表冻结且不可重复锁定；两臂/两个 split 缺一不可锁定；更正搜寻点击后可改选并保留历史；搜寻未变时重复选群被拒；缺报不补零；已封存批次拒绝补报；二次揭盲与二次复核均被拒；揭盲后拒绝更正搜寻；分析师不能揭盲、观察员不能写；复核报告拒绝非复核集成员；观察员导出需先有复核决定。

## 手工端到端（真实进程）
- 启动 `uvicorn src.main:app`（SQLite、`SEED_DEMO=true`），`/health` 200；seed 写入 3 个计划、1200 名成员。
- 用 API 走完：录入成员 → 锁定 → 搜寻选群（选中「高活跃」，差值 0.2372）→ 录入含 6 条缺报的复核批 → 揭盲 → 复核归档。
- 演示脚本 `python -m scripts.demo_validation` 生成 194 条报告；揭盲结果：对照 4/42、处理 18/47，差值 0.2877，95% 区间 [0.1106, 0.4417]，缺报 3（缺报成员计入 missing，未补零），结论 `can_expand`。
- 前端 jsdom：登录页、总览、来源录入（新建计划 + 批量录入 6 人）、锁定、搜寻选群、复核录入、揭盲页与复核归档均正确渲染；分析师揭盲返回 403、负责人成功；状态徽标与 CSV 导出正常。

## 未覆盖 / 已知边界
- 未在真实 Postgres + Redis + Nginx 容器中运行（本机无 Docker）；行锁 `SELECT … FOR UPDATE` 在 SQLite 下自动退化为单写者，仅 Postgres 生效。
- 限流为 Redis 计数器，`REDIS_URL` 留空时跳过。
- 方法上未做多重比较校正；选群与揭盲使用互相独立的搜寻集/复核集即为预设边界。
