# COROS接入更新

当前COROS入口已迁移为MCP。连接方式、读取命令、数据范围及推送边界见[COROS MCP说明](api-tools/README_MCP.md)。下文涉及旧Token/邮箱/密码或Web API的内容是历史说明，不能作为当前COROS接入步骤。

# Marathon Copilot — 你的 AI 马拉松教练

> 从长期训练规划到比赛日配速，再到赛后深度复盘——覆盖全马备赛全周期的智能助手。
> COROS 手表数据自动采集 → AI 生成训练计划 → 一键推送到手表。
> 不用懂代码，在微信小程序上就能用。

---

## 它能帮你做什么？

### 长期训练规划

比赛还有好几个月？Marathon Copilot 帮你设计**从今天到比赛日的完整训练周期化方案**：

- 基于当前 VDOT 和目标成绩，规划 **VDOT 递进路径**（每 16 周提升 0.5-1.5 点）
- 设计 5-6 个训练阶段：恢复期 → 有氧基础期 → 有氧发展期 → 专项期 → 巅峰期 → 减量期
- 逐周跑量递进（严格遵守 10% 增量上限 + 每 4 周减载恢复；大体重跑者自动收紧至 8%）
- 安排里程碑测试（5km → 10km → 半马），用来验证进步和调整计划
- 配套力量训练、营养策略、伤病预防方案
- 多因子达成概率精算（VDOT 缺口 × 训练年限 × 伤病 × 跑量 × 耦合比 × 体重 × 年龄）
- **女性跑者：** 自动预测比赛日生理周期相位，计算周期修正因子，并提供对应的赛日策略

### 每周训练计划

长期方案落地到每一周，生成**天气自适应的 7 天训练日历**：

- 自动获取 7 天天气预报，把质量课安排在好天气日、恶劣天气日安排休息
- 每日训练处方精确到配速、心率上限、RPE、距离
- 每日饮食方案（碳水/蛋白质/脂肪按体重和训练阶段计算）
- 恢复监控清单（晨脉、DOMS、疼痛量表、睡眠）+ 自动决策树
- 力量训练课表（随训练阶段变化：关节稳定 → 跑步经济性 → 维持）
- **女性生理周期整合**：自动叠加 5 相位周期模型（经期/卵泡期/排卵期/早期黄体期/晚期黄体期），按周期日调节训练强度、营养比例、ACL 风险预警和 RPE 膨胀修正

### COROS 手表集成

Marathon Copilot 直连 COROS Training Hub，实现**数据采集 → 智能分析 → 课表推送**全闭环：

**数据读取：**
- 自动拉取 COROS 手表活动数据（距离、配速、心率、训练负荷）
- 读取 HRV、恢复度、安静心率等健康指标，评估恢复状态
- 生成周报：实际执行 vs 计划对比分析，自动发现超量/违规高强度等问题

**课表推送：**
- 解析 AI 生成的每周训练计划 Markdown → 自动转换为 COROS 结构化课程
- 支持轻松跑、长距离、节奏跑、间歇跑四种训练类型的自动识别和分段
- 每段配速/距离精准推送，手表上即看即跑——热身、主课、放松一目了然
- 休息日/交叉训练日自动跳过

**每周自动化流水线：**

```
COROS 手表数据 → generate_next_week_plan.py → AI 生成训练计划 → coros_push_plan.py → 手表
     ↑ 自动采集          ↑ 周报 + Prompt                ↑ Markdown          ↑ 自动推送
```

一条 cron 命令 (`run_weekly_plan.sh`) 每周日晚自动执行整个流水线。

### HYROX 专项训练

除了公路马拉松，还支持 **HYROX 综合体能赛**专项训练计划生成：

- 基于跑者跑力数据、力量训练背景和目标赛事定制
- 周期化课表（跑步专项 + 8 项功能性训练站点交替）
- 发力模式纠正、数据追踪、场馆策略

### 赛前：帮你定目标、出配速方案

比赛前最纠结的问题："我该跑多快？"

Marathon Copilot 会根据你的真实跑力，帮你算出**靠谱的比赛目标**和**逐公里配速表**：

- 根据你的 PB 计算跑力值（VDOT），给出科学的目标成绩
- 考虑比赛当天的天气（温度、湿度、风速），自动修正配速
- 考虑你的身体状况（HRV 心率变异性、伤病、赛间恢复时间）
- 生成一份完整的配速表：每公里该跑多快、心率控制在多少、什么时候补水补胶
- 设定"熔断机制"：如果比赛中心率飙高或配速偏差过大，告诉你什么时候该果断降速

### 每日训练 & 饮食计划

赛前 7 天到比赛日，每天帮你安排**训练、饮食、恢复**三件事：

- **训练**：根据 VDOT 计算训练配速，从赛前减量跑到赛前激活跑，每天不一样
- **饮食**：基于体重计算碳水/蛋白质/脂肪摄入目标，越接近比赛日碳水占比越高（糖原超补）
- **恢复**：睡眠、拉伸、泡沫轴、冰浴……按天推荐最合适的恢复策略

### 天气追踪 & 每日简报

从报名到比赛日，每天自动追踪赛事城市的天气变化：

- 量化"环境税"对配速的影响（综合气温、湿度、风速、体感温度）
- 根据最新天气动态调整配速建议
- 生成**每日简报**（Markdown + PDF），集成天气、训练计划、饮食建议于一份报告
- 支持多人模式：一次生成多位跑者的个性化简报

### 赛后：深度复盘——用运动手表数据找到"下次怎么赢"

跑完比赛不只是看个成绩就完了，Marathon Copilot 会帮你做**教练级深度复盘**：

- **四维生物力学分析**：利用运动手表（COROS / Garmin）的 5km 分段数据，对步幅、步频、功率、配速做逐段关联分析，精确定位配速变化的生理驱动因子
- **步幅衰减三阶段模型**：识别稳定期 → 加速衰减期 → 崩塌期的里程拐点，量化步幅缩短贡献了多少配速损失（实战验证：步幅贡献率通常 > 70%）
- **心率-配速脱耦诊断**：区分"心率漂移型"衰减（湿度/脱水）和"糖原耗竭型"崩盘（配速暴降但心率不升反降），精准定位根因
- **多因子根因链分析**：将总偏差拆解为结构性根因（跑量不足）+ 触发因子（赛间恢复不充分）+ 放大器（步幅锁死导致额外代谢成本）+ 边际因子（补给时机），每项量化到秒
- **偏差分解量化**：总偏差精确分解到各因子，总和必须吻合（如 +9:01 = C 级跑量 +316" + 赛间 7 天 +105" + 步幅崩塌 +99" + ...）
- **跨赛事对比**：多场比赛横向对比（跑量评级、步幅数据、正 split 幅度），找出训练和执行的规律
- **能力重估**：去除可消除因素后的"净完赛能力"、VDOT 校准、下一场比赛建议
- **教练私房话**：用跑者能理解的语言，给出"三条行动指令"——最重要的改进方向

### PDF 报告：一键生成精美文档

所有分析结果可以导出为排版精美的 PDF，方便保存和分享给教练、跑友。

---

## 实战验证

Marathon Copilot 已在多场真实半马/全马比赛中验证，以下是复盘系统发现的典型案例模式：

| 场景 | 复盘发现 |
| :--- | :--- |
| 半马：赛前深层手法时机不当 | 赛前 72h 深层肌肉松解 → 步幅锁死（低于身高预期值）→ 制定"赛前 5 天禁深层手法"规则 |
| 全马：多因子叠加撞墙 | 三因子叠加"代谢完美风暴"：C 级周跑量 + 赛间恢复不足 + 步幅崩塌。前 20km 完美执行（A/A/A），后程撞墙 |
| 半马：赛道微气候陷阱 | 隧道段湿度 90%+ → 心率骤升 → 根因链分析定位微气候为核心触发因子 |
| 半马：基于复盘优化下一场方案 | 基于上场复盘数据，环境税从 92"→15"（-84%），PB 胜算从 72%→77% |

> 其中一份全马复盘报告（600+ 行）包含完整的 5km 分段四维分析、步幅三阶段崩塌模型、代谢成本量化、糖原经济学推算、多场赛事横向对比。这是目前最完整的复盘模板。

---

## 怎么用？

### 微信小程序（推荐）

**第 1 步：建立你的跑者档案**

打开小程序，填写你的基本信息：
- 身高、体重（用于计算环境影响和营养目标）
- 历史 PB 成绩（比如半马最好成绩 1:35:00）
- HRV 数据（可选，有的话分析更准）

**第 2 步：赛前目标设定**

选择你要参加的比赛，填写赛事信息（赛道类型、海拔、预估天气等），AI 会自动生成：
- 推荐目标成绩（A/B/C 三档计划）
- 逐公里配速表
- 补给计划
- 锁屏备忘（比赛当天打开手机就能看）

**第 3 步：每日训练 & 饮食**

进入"每日训练 & 饮食"页面，查看赛前倒计时和当天的：
- 训练安排（项目、配速、时长）
- 饮食建议（碳水/蛋白质/脂肪克数、推荐食物）
- 恢复策略（睡眠、拉伸、补水要点）

**第 4 步：赛后复盘**

比赛结束后，录入实际比赛数据（分段配速、心率、步幅、功率等），AI 会生成一份教练级的深度复盘报告：
- 四维生物力学分析（步幅-步频-功率-配速）
- 根因链分析 + 偏差分解量化
- 能力重估 + 下一场比赛建议

### CLI 版（终端工具）

除了小程序，本项目也支持在终端中使用 Python 脚本，适合开发者和需要批量处理的场景。

```bash
# 安装依赖
pip install markdown weasyprint pymupdf requests pyyaml

# 1. 配置跑者信息（复制模板，填入你的数据）
cp api-tools/race_config.example.yaml api-tools/race_config.yaml
# 编辑 race_config.yaml，填入你的 PB、体重、目标成绩等

# 1b. 建立跑者档案（可选，用于长期训练规划）
cp api-tools/runner_profile.example.yaml api-tools/runner_profile_yourname.yaml
# 编辑填入完整的 PB 历史、VDOT、伤病记录等

# 1c. 配置训练周期（可选，用于周训练计划生成）
cp api-tools/training_cycle_config.example.yaml api-tools/training_cycle_config.yaml
# 编辑填入目标赛事、训练阶段、跑量递进等

# 1d. 配置 COROS 账号（可选，用于手表数据采集和课表推送）
cp api-tools/.env.example api-tools/.env
# 编辑 .env，填入 COROS_EMAIL + COROS_PASSWORD

# 2. 生成每日简报（天气 + 训练 + 饮食）
python api-tools/generate_daily_briefing.py --date 2026-03-26

# 3. 生成天气日报
python api-tools/daily_weather_report.py

# 4. COROS 手表数据 → 生成下周训练计划 prompt
python api-tools/generate_next_week_plan.py

# 5. 推送训练课表到 COROS 手表
python api-tools/coros_push_plan.py 训练计划.md           # 推送全部跑步日
python api-tools/coros_push_plan.py 训练计划.md --dry-run  # 预览模式（不推送）
python api-tools/coros_push_plan.py 训练计划.md --days 2,6 # 只推指定天

# 6. 每周自动化（cron 一键执行：采集数据 → 生成计划 → 推送手表）
bash api-tools/run_weekly_plan.sh

# 7. 运行算法自检（VDOT、配速、周期化模型）
python api-tools/training_calculator.py

# 8. 生成 PDF 报告
python generate_pdf.py 输入文件.md 输出文件.pdf
```

多人模式：创建多份配置文件（如 `race_config_b.yaml`），脚本会自动识别并为每位跑者生成独立报告。

---

## 背后的科学原理

Marathon Copilot 不是拍脑袋给建议，每个数字都有运动生理学依据：

| 能力 | 原理 |
|------|------|
| **跑力计算** | 基于 Jack Daniels 的 VDOT 公式，用你的 PB 反推跑力值 |
| **训练周期化** | 基于 Daniels / Pfitzinger / Hansons 方法论的分期训练模型 |
| **跑量递进** | 10% 周增量上限 + 每 4 周减载恢复 + 分阶段峰值控制（大体重跑者自动降至 8%） |
| **耦合比分析** | 短距离 VDOT 与全马 VDOT 的比值，量化速度-耐力均衡度，指导训练侧重 |
| **环境修正** | 综合温度、湿度、风速对配速的影响，还会根据你的身高体重（BSA/体重比）做个性化修正 |
| **HRV 评估** | 三维度分析（基线偏差 + 变异系数 + 赛日回升），评估恢复状态和比赛日竞技状态 |
| **PB 概率** | 综合跑力、训练量、环境、身体状态、耦合比、伤病、HRV 等多因子精算 |
| **配速策略** | 支持均匀配速、后程加速、保守策略三种方案，自动生成逐公里计划 |
| **营养计算** | 根据体重和赛前天数计算碳水/蛋白质/脂肪目标，支持糖原超补周期 |
| **训练配速** | 基于 VDOT 推算 Easy/Marathon/Threshold/Interval/Repetition 五档训练配速 |
| **天气自适应** | 7 天天气预报驱动训练排课，自动避开恶劣天气日，高温日自动降速/替换交叉训练 |
| **四维生物力学** | 步幅-步频-功率-配速逐段关联分析，量化步幅贡献率（步幅 vs 步频对配速损失的贡献占比） |
| **糖原经济学** | 基于体重、配速、跑量评级精算糖原储备 vs 消耗 vs 赛中补充的能量平衡，预测撞墙里程 |
| **心率-配速脱耦** | 前后半程配速/HR比值变化，区分心率漂移（湿度）和糖原耗竭（配速降 + HR 不升） |
| **女性生理周期** | 5 相位周期模型（经期→卵泡期→排卵期→早期黄体期→晚期黄体期），按周期日调节训练强度系数、营养比例、ACL 风险预警和 RPE 膨胀修正。科学依据：Bruinvels et al. (2017) *BJSM*、McNulty et al. (2020) *Sports Med*、Wikström-Frisén et al. (2017) *JSCR* |

---

## 部署指南（开发者）

如果你想自己部署这个小程序，或者参与开发，请往下看。

### 环境准备

1. 注册 [微信小程序账号](https://mp.weixin.qq.com/)，获取 AppID
2. 下载 [微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)
3. 开通微信云开发

### 项目导入

1. 打开微信开发者工具，导入本项目
2. 在 `project.config.json` 中填入你的 AppID
3. 开通云开发环境

### 数据库配置

在云开发控制台中创建以下数据库集合：

| 集合名 | 用途 |
|--------|------|
| `runners` | 跑者档案 |
| `pb_records` | PB 记录 |
| `hrv_data` | HRV 时序数据 |
| `reports` | 分析报告 |
| `weather_tracking` | 天气追踪记录 |
| `daily_plans` | 每日训练 & 饮食计划 |

### 环境变量配置

在云函数设置中添加以下环境变量：

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `LLM_API_URL` | 大模型 API 地址 | `https://api.deepseek.com/v1/chat/completions` |
| `LLM_API_KEY` | 大模型 API Key | `sk-xxx` |
| `LLM_MODEL` | 模型名称 | `deepseek-chat` |
| `WEATHER_PROVIDER` | 天气服务 | `wttr` 或 `qweather` |
| `WEATHER_API_KEY` | 天气 API Key（和风天气） | — |

CLI 版额外需要在 `.env` 中配置（参见 `.env.example`）：

| 变量名 | 说明 |
|--------|------|
| `SMTP_HOST` | 邮件服务器地址 |
| `EMAIL_FROM` | 发件人邮箱 |
| `EMAIL_AUTH_CODE` | 邮箱授权码 |
| `REPORTS_DIR` | 报告输出目录 |
| `REPORTS_ONEDRIVE_DIR` | OneDrive 同步目录（可选） |
| `COROS_EMAIL` | COROS 账号邮箱（推荐，支持自动登录和课表推送） |
| `COROS_PASSWORD` | COROS 账号密码 |
| `COROS_TOKEN` | COROS accessToken（替代邮箱密码，从浏览器获取） |
| `COROS_REGION` | API 区域：`cn`（中国）或 `intl`（国际），默认 `cn` |
| `COROS_PUSH_ENABLED` | 是否在每周自动化中推送课表到手表：`0`（默认关闭）或 `1` |

支持的大模型：
- [DeepSeek](https://platform.deepseek.com/)（推荐，性价比高）
- [Kimi / Moonshot](https://platform.moonshot.cn/)
- [OpenAI](https://platform.openai.com/) 及兼容接口

### 跑者配置文件

CLI 版通过三类 YAML 文件管理跑者和训练数据：

```bash
# 赛事配置（单场比赛的跑者+天气+训练+饮食）
cp api-tools/race_config.example.yaml api-tools/race_config.yaml

# 跑者档案（持久化个人数据：所有 PB、VDOT 历史、伤病、HRV）
cp api-tools/runner_profile.example.yaml api-tools/runner_profile_yourname.yaml

# 训练周期配置（多周期分期训练计划：阶段划分、跑量递进、力量/营养）
cp api-tools/training_cycle_config.example.yaml api-tools/training_cycle_config.yaml
```

配置文件包含：
- **race_config.yaml**：单场比赛的赛事信息、目标成绩、配速策略、D-7 到 D-0 训练/饮食计划
- **runner_profile.yaml**：跑者全量档案（跨赛事复用），含 PB 表、VDOT 趋势、赛事历史、伤病追踪、HRV 数据、教练洞察、女性生理周期参数（周期长度、敏感度、避孕药状态）
- **training_cycle_config.yaml**：8-52 周训练周期架构，含阶段定义、周模板、力量训练、营养策略、天气排课规则

> 注意：所有包含个人数据的配置文件（`race_config.yaml`、`runner_profile_*.yaml`、`training_cycle_config.yaml`）均已加入 `.gitignore`，不会被提交到仓库。请基于 `*.example.yaml` 创建你自己的配置。

### 部署云函数

在微信开发者工具中，右键每个云函数目录 → "上传并部署：云端安装依赖"：
- `cloudfunctions/user` — 用户管理
- `cloudfunctions/raceGoal` — 赛前目标生成
- `cloudfunctions/raceReview` — 赛后复盘分析
- `cloudfunctions/weather` — 天气数据
- `cloudfunctions/dailyPlan` — 每日训练 & 饮食计划

### AI Skill 体系

Marathon Copilot 的核心分析能力由 7 个 AI Skill 驱动，覆盖从长期规划到赛后复盘的完整周期：

| Skill | 用途 | 时间跨度 |
|-------|------|----------|
| **race-plan** | 多周期分期训练目标方案（VDOT 递进、阶段划分、里程碑测试、女性周期整合） | 8-52 周 |
| **training-weekly** | 天气自适应每周训练计划（天气排课 + 每日处方 + 饮食 + 恢复 + 力量训练） | 1 周 |
| **race-goal** | 赛前目标设定与实战配速方案（HRV 三维评估 + 环境税精算 + PB 概率 + 熔断规则） | 赛前 1-2 周 |
| **race-training** | 赛前 D-7 到 D-0 每日训练 + 饮食 + 恢复（Taper 减量 + 碳水负荷 + 赛前激活） | D-7 至 D-0 |
| **race-weather** | 赛前天气日报（环境税重算 + 绿灯/黄灯/橙灯/红灯信号 + 策略调整建议） | D-7 至 D-0 |
| **race-review** | 赛后深度复盘（四维生物力学分析 + 根因链 + 偏差分解 + 跨赛事对比 + 能力重估） | 赛后 |
| **hyrox-training** | HYROX 专项冲刺训练计划（周期化课表 + 功能性站点训练 + 发力模式纠正） | 4-12 周 |

Skill 之间的数据流：

```
runner_profile.yaml (跑者静态档案)         COROS 手表 (实时数据)
    ↓                                         ↓
race-plan ──→ training-weekly ←── coros_client.py (活动/HRV/恢复)
 (8-52周)        (每周)                        ↓
                   ↓                    coros_push_plan.py → 手表
              race-training → race-goal → race-weather
              (D-7~D-0)     (赛前方案)   (天气日报)
                                  ↓
                              比赛日
                                  ↓
                            race-review (赛后复盘)
                                  ↓
                            下一个训练周期
```

### 项目结构

```
.
├── miniprogram/                    # 微信小程序前端
│   ├── pages/
│   │   ├── index/                  #   首页（功能入口）
│   │   ├── race-goal/              #   赛前目标设定
│   │   ├── daily-plan/             #   每日训练 & 饮食计划
│   │   ├── race-review/            #   赛后复盘
│   │   ├── history/                #   历史记录
│   │   ├── profile/                #   跑者档案
│   │   └── report-detail/          #   报告详情
│   ├── services/api.js             #   云函数调用封装
│   └── utils/util.js               #   工具函数
├── cloudfunctions/                  # 云函数（后端逻辑）
│   ├── user/                       #   用户管理
│   ├── raceGoal/                   #   赛前目标生成（AI + 算法）
│   ├── raceReview/                 #   赛后复盘分析（AI + 算法）
│   ├── weather/                    #   天气数据
│   ├── dailyPlan/                  #   每日训练 & 饮食计划（VDOT + 营养算法）
│   └── common/utils.js             #   核心算法库（JavaScript）
├── api-tools/                      # CLI 工具集
│   ├── training_calculator.py      #   核心算法库（Python，1800+ 行：VDOT、配速、周期化、生理周期模型）
│   ├── coros_client.py             #   COROS Training Hub API 客户端（活动/健康数据读取 + 课程写入）
│   ├── coros_push_plan.py          #   训练计划 → COROS 课程推送（解析 Markdown → 结构化课程 → 推送到手表）
│   ├── coros_token_manager.py      #   COROS Token 生命周期管理（缓存/刷新/验证）
│   ├── coros_weekly_report.py      #   COROS 周训练执行分析（实际 vs 计划对比）
│   ├── generate_next_week_plan.py  #   COROS 数据 → 下周训练计划 prompt 自动化桥接
│   ├── generate_daily_briefing.py  #   每日简报生成器（天气 + 训练 + 饮食）
│   ├── daily_weather_report.py     #   天气日报生成器
│   ├── daily_weather_email.py      #   天气日报邮件发送
│   ├── weather_client.py           #   天气 API 客户端（赛前 + 训练排课适宜度评分）
│   ├── env_tax.py                  #   环境税计算（共享模块）
│   ├── api_client.py               #   LLM API 客户端
│   ├── pdf_styles.py               #   PDF 样式定义
│   ├── run_weekly_plan.sh          #   每周自动化脚本（数据采集 → 计划生成 → 手表推送）
│   ├── run_daily_briefing.sh       #   每日简报一键运行脚本
│   ├── run_daily_weather.sh        #   天气日报一键运行脚本
│   ├── runner_profile.example.yaml #   跑者档案模板（含生理周期配置）
│   ├── training_cycle_config.example.yaml  #   训练周期配置模板
│   ├── .env.example                #   环境变量模板（COROS/邮件/API）
│   └── race_config.example.yaml    #   赛事配置模板
├── .cognition/skills/              # Devin AI Skills
│   ├── race-plan/                  #   长期训练周期规划（含生理周期整合）
│   ├── training-weekly/            #   每周训练计划生成（含每日周期叠加）
│   ├── race-goal/                  #   赛前目标设定 Skill
│   ├── race-review/                #   赛后复盘 Skill
│   ├── race-weather/               #   赛前天气日报 Skill
│   ├── race-training/              #   赛前训练 & 饮食计划 Skill
│   └── hyrox-training/             #   HYROX 专项训练计划 Skill
├── generate_pdf.py                 # PDF 生成器（通用）
├── md_to_pdf.py                    # Markdown → PDF 转换器
└── prompt.md                       # Prompt 模板
```

---

## 个人数据保护

- 所有跑者的个人数据（PB、体重、HRV、生理周期、比赛报告等）均已通过 `.gitignore` 排除，不会上传到代码仓库
- `race_config.yaml`（含跑者真实姓名和身体数据）不会被提交；仓库中只保留脱敏后的 `race_config.example.yaml` 模板
- `runner_profile_*.yaml`（跑者档案，含生理周期等敏感健康数据）和 `training_cycle_config.yaml`（训练周期配置）同样已排除
- 生成的报告文件（`*报告/`、`*数据/`、`*天气日报*.md`、`*训练目标*.md`、`*训练计划*.md`、`*_W*_*.md`）均已排除
- API 密钥、邮箱授权码、COROS 账号凭据通过 `.env` 管理，同样不会提交
- COROS Token 缓存存储在本地 `~/.config/marathon-copilot/coros_token.json`，不在项目目录中

## License

MIT
