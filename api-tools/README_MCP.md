# COROS MCP 数据接入

COROS 读取已切换为 MCP 工具调用，不再读取 `COROS_TOKEN`、邮箱、密码或旧 Token 缓存，不请求私有 Web API。既有 `.env` 和凭据缓存不自动删除；迁移后的入口不使用它们。

## 当前聊天中已连接的高驰 MCP

下列日期均为虚构历史示例，与任何跑者的真实训练记录无关。

连接由聊天宿主管理。Python 进程不能直接调用聊天里的 `tools.*`，也不能继承其 OAuth 会话。因此使用“请求清单 → 宿主执行真实 MCP 调用 → 原始响应文件 → 本地报告”。原始响应是明确标记日期的快照，不冒充后台实时连接。

```bash
python3 api-tools/coros_mcp_sync.py request --start 20250106 --end 20250109 -o /tmp/coros-mcp-request.json
```

将请求文件交给已连接高驰的助手执行。助手只能调用清单中的读取工具，并为活动追加 `getActivityDetail`，保留大整数ID为字符串。若返回数量达到limit，缩短日期范围后重新查询；单日仍达到limit则标记覆盖不完整。不要用助手总结代替原始响应。

响应文件格式：

```json
{
  "schema": "coros-mcp/v1",
  "source": "COROS MCP",
  "captured_at": "2025-01-09T12:00:00+08:00",
  "calls": [
    {"tool": "querySportRecords", "arguments": {}, "result": {"content": [], "isError": false}}
  ]
}
```

上面仅展示结构；arguments必须是实际查询参数，result必须是实际CallToolResult。客户端要求查询范围、运动类型和完整数量匹配，错误或缺失响应不会变成零跑量。

```bash
python3 api-tools/coros_client.py --mcp-snapshot /tmp/coros-response.json --as-of 2025-01-09 weekly --weeks-ago 0
python3 api-tools/coros_weekly_report.py --mcp-snapshot /tmp/coros-response.json --as-of 2025-01-09 --weeks-ago 0 --json
python3 api-tools/generate_next_week_plan.py --mcp-snapshot /tmp/coros-response.json --as-of 2025-01-09 --weeks-ago 0 --report-only --json -o /tmp/weekly-report.json
```

也可设置`COROS_MCP_SNAPSHOT`，但重复运行只重放该快照，不能更新高驰数据。正在进行的一周带`complete=false`和`queried_through`；仅统计跑步100/101/102/103，不能称为全运动负荷。

## 独立部署的 MCP Server

安装到自己的虚拟环境：

```bash
python -m pip install -r api-tools/requirements-mcp.txt
```

实现采用[官方 MCP Python SDK v1](https://github.com/modelcontextprotocol/python-sdk/tree/v1.26.0)，使用initialize、tools/list、tools/call与标准会话关闭。依赖限定`mcp>=1.26,<2`，避免v2不兼容接口。

Streamable HTTP配置`api-tools/coros_mcp.local.json`：

```json
{
  "transport": "streamable-http",
  "url": "http://127.0.0.1:8000/mcp",
  "timeout_seconds": 60
}
```

这里是本地服务示例，不是高驰官方地址。实际URL需要由部署方提供。服务若需要授权，可添加`header_env`，其值是环境变量名，例如`{"Authorization":"COROS_MCP_AUTHORIZATION"}`；变量完整值由部署方配置，不将凭据写入版本库。未实现自动OAuth交互流程；需要OAuth的独立服务须提供适合该客户端的授权方式。

stdio配置：

```json
{
  "transport": "stdio",
  "command": "python3",
  "args": ["/path/to/coros_mcp_server.py"]
}
```

stdio的`env_names`也是“服务环境变量名 → 当前进程环境变量名”映射，不存凭据值。不要填入未知来源的启动命令。

工具名默认按标准名称或`coros_`宿主前缀匹配。若服务名称不同，提供`tools`映射，如`{"querySportRecords":"my_query_records"}`。这只映射名称；不同参数或响应语义仍需另写适配器。本客户端目前严格解析已连接高驰服务的英文Sport Records及Activity Details文本；未知结构会明确报错，不猜单位。

```bash
python3 api-tools/coros_mcp_sync.py collect --mcp-config api-tools/coros_mcp.local.json --start 20250106 --end 20250109 -o /tmp/coros-response.json
python3 api-tools/coros_weekly_report.py --mcp-config api-tools/coros_mcp.local.json --weeks-ago 1 --json
```

`COROS_MCP_CONFIG`可作为默认配置路径。未配置服务、也未提供快照时，会提示宿主执行流程，不回退旧API。定时脚本使用独立服务可以自行读数据；只有聊天宿主连接时，cron不能自行刷新MCP快照。

## 数据与训练写入边界

- 活动ID按字符串保留，同日多条活动分别保留。
- 活动列表没有Training Load时，读取详情补全；详情仍没有则是null，不是0。
- Workout Time是运动时间；Total Time可能包含暂停，不替换运动时间。
- Short-Term/Long-Term Load不映射成旧ATI/CTI；恢复与跑力保留MCP原始数据。HRV、睡眠、安静心率未查询就保持缺失。
- 原Markdown推送脚本现在只生成`createScheduledWorkout`请求清单，包含日期，不再直接创建课程库或自动下发。旧解析器仍可能推断分段，所以每一段必须审阅。命令：`python3 api-tools/coros_push_plan.py plan.md --export-mcp /tmp/review.json`。
- 本地MCP客户端只允许读取工具，拒绝写工具；用户确认具体方案并明确要求推送后，由宿主使用高驰MCP写入并回读核验。
- `run_weekly_plan.sh`不再接受开关自动推送。生成材料不等于确认执行。

## 验证

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s api-tools/tests -p 'test_coros_mcp.py'
```

单元测试不需要高驰账号。安装SDK时额外运行真实stdio协议模拟服务器测试；这只能验证协议与适配器，不能代替对具体远程服务的连通测试。
