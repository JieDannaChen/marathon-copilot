"""COROS MCP transport and decoding. No private COROS HTTP endpoints or login."""
from __future__ import annotations

import asyncio
import json
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

RUNNING_CODES = [100, 101, 102, 103]
READ_TOOLS = {
    'querySportRecords', 'getActivityDetail', 'queryActivityLapData',
    'queryFitnessAssessmentOverview', 'queryRecoveryStatus',
    'queryTrainingLoadAssessment', 'querySleepHrv', 'queryRestingHeartRate',
    'queryTrainingSchedule', 'queryScheduledWorkoutDetails',
}


class McpError(RuntimeError):
    pass


def canonical(name):
    # Host prefixes are not part of the server's native tool name.
    return name.rsplit('__', 1)[-1].removeprefix('coros_').lower()


def decode_result(result):
    if hasattr(result, 'model_dump'):
        result = result.model_dump(by_alias=True, mode='json')
    if not isinstance(result, dict):
        raise McpError('MCP tool result must be an object')
    if result.get('isError') or result.get('is_error'):
        raise McpError('COROS MCP tool returned an error; query is not complete')
    structured = result.get('structuredContent', result.get('structured_content'))
    if structured is not None:
        if isinstance(structured, dict) and set(structured) == {'result'}:
            structured = structured['result']
        if not isinstance(structured, str):
            return structured
        value = structured
    else:
        blocks = [c.get('text', '') for c in result.get('content', []) if c.get('type') == 'text']
        if not blocks:
            raise McpError('MCP result has no supported text or structured content')
        value = '\n'.join(blocks)
    # The connected COROS host currently wraps text in a JSON string.
    for _ in range(2):
        try:
            parsed = json.loads(value)
        except (ValueError, TypeError):
            return value
        if not isinstance(parsed, str):
            return parsed
        value = parsed
    return value


def seconds(value):
    parts = value.strip().split(':')
    if len(parts) not in (2, 3) or not all(p.isdigit() for p in parts):
        raise McpError('Unsupported COROS duration or pace format')
    nums = list(map(int, parts))
    if any(v >= 60 for v in nums[1:]):
        raise McpError('Invalid COROS duration')
    return sum(v * 60 ** i for i, v in enumerate(reversed(nums)))


def field(text, label, pattern=r'([^\n|]+)'):
    found = re.search(r'(?m)^\s*' + re.escape(label) + r':\s*' + pattern, text)
    return found.group(1).strip() if found else None


def number(text, label):
    value = field(text, label, r'(-?\d+(?:\.\d+)?)')
    return float(value) if value is not None else None


def parse_records(value):
    """Strict decoder for the actual COROS MCP text format; never guess units."""
    if not isinstance(value, str):
        raise McpError('Unrecognized activity schema: expected COROS Sport Records text')
    if re.fullmatch(r'No sport records found from \d{4}-\d{2}-\d{2} to \d{4}-\d{2}-\d{2}\.', value.strip()):
        return []
    header = re.search(r'Sport Records.*?\((\d+) records?\)', value)
    if not header:
        raise McpError('Unrecognized activity response; cannot claim date coverage')
    expected = int(header.group(1))
    chunks = re.split(r'(?m)^\d+\. ', value)[1:]
    if len(chunks) != expected:
        raise McpError('Activity count does not match decoded records')
    records = []
    for chunk in chunks:
        title = re.match(r'(.+?) — (\d{4}-\d{2}-\d{2})', chunk)
        info = re.search(r'LabelId: (\d+)\s*\|\s*SportType: (\d+)', chunk)
        metrics = re.search(r'Duration: ([\d:]+)\s*\|\s*Distance: ([\d.]+) km', chunk)
        if not (title and info and metrics):
            raise McpError('An activity is missing identity, date, duration or distance')
        pace = re.search(r'Average Pace: ([\d:]+) /km', chunk)
        hr = re.search(r'Avg HR: (\d+) bpm', chunk)
        start = re.search(r'startTimestamp=(\d+)', chunk)
        records.append({
            'labelId': info.group(1), 'sportType': int(info.group(2)),
            'date': title.group(2), 'name': title.group(1),
            'distance': float(metrics.group(2)) * 1000,
            'totalTime': seconds(metrics.group(1)),
            'startTime': int(start.group(1)) if start else None,
            'avgSpeed': seconds(pace.group(1)) if pace else None,
            'avgHr': int(hr.group(1)) if hr else None,
            'trainingLoad': None, 'maxHr': None, 'avgCadence': None,
        })
    if len({r['labelId'] for r in records}) != len(records):
        raise McpError('Duplicate activity IDs in MCP result')
    return records


def record_args(start, end, limit=60):
    for day in (start, end):
        datetime.strptime(day, '%Y%m%d')
    if start > end or limit < 1:
        raise ValueError('Invalid query range or limit')
    return dict(startDate=start, endDate=end, limit=limit, sportTypeCodes=RUNNING_CODES,
                locationKeyword='', maxAveragePace='', maxDistanceKm=0,
                maxDurationMinutes=0, minDistanceKm=0, minDurationMinutes=0)


def read_config(path=None):
    name = path or os.environ.get('COROS_MCP_CONFIG')
    if not name:
        return {'transport': 'host'}
    location = Path(name).resolve()
    config = json.loads(location.read_text(encoding='utf-8'))
    if config.get('response_file'):
        config['response_file'] = str((location.parent / config['response_file']).resolve())
    return config


@asynccontextmanager
async def open_session(config):
    """SDK v1 session lifecycle kept in one task; no SDK needed for host replay."""
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from mcp.client.streamable_http import streamable_http_client
        import httpx
    except ImportError as exc:
        raise McpError('Standalone MCP requires: pip install -r requirements-mcp.txt') from exc
    transport = config.get('transport')
    if transport == 'stdio':
        # env entries are *environment variable names*, never embedded secrets.
        env = {k: os.environ[v] for k, v in config.get('env_names', {}).items()}
        params = StdioServerParameters(command=config['command'], args=config.get('args', []), env=env or None)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session
    elif transport == 'streamable-http':
        url = config.get('url', '')
        if not url.startswith(('https://', 'http://localhost:', 'http://127.0.0.1:')):
            raise McpError('Use HTTPS or an explicit local MCP URL')
        headers = {k: os.environ[v] for k, v in config.get('header_env', {}).items()}
        async with httpx.AsyncClient(headers=headers, timeout=config.get('timeout_seconds', 60)) as http:
            async with streamable_http_client(url, http_client=http) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session
    else:
        raise McpError('Standalone MCP transport must be stdio or streamable-http')


async def session_call(session, config, name, args):
    names = []
    cursor = None
    while True:
        page = await session.list_tools(cursor=cursor)
        names.extend(t.name for t in page.tools)
        cursor = page.nextCursor
        if not cursor:
            break
    configured = config.get('tools', {}).get(name)
    matches = [n for n in names if n == configured] if configured else [n for n in names if canonical(n) == canonical(name)]
    if len(matches) != 1:
        raise McpError(f'MCP server has no unique matching tool for {name}; configure tools mapping')
    result = await session.call_tool(matches[0], args)
    return result.model_dump(by_alias=True, mode='json')


class ToolCaller:
    def __init__(self, config=None, snapshot=None):
        self.config = config or read_config()
        path = snapshot or os.environ.get('COROS_MCP_SNAPSHOT') or self.config.get('response_file')
        self.bundle = json.loads(Path(path).read_text(encoding='utf-8')) if path else None
        if self.bundle and self.bundle.get('schema') != 'coros-mcp/v1':
            raise McpError('Unsupported MCP snapshot; collect a coros-mcp/v1 response bundle')

    def call_raw(self, name, args):
        if name not in READ_TOOLS:
            raise McpError(f'Unsupported MCP operation: {name}')
        if self.bundle is not None:
            candidates = [c for c in self.bundle['calls'] if canonical(c['tool']) == canonical(name) and c['arguments'] == args]
            if len(candidates) != 1:
                raise McpError(f'Snapshot has no unique response for {name}; refresh via MCP')
            result = candidates[0]['result']
        elif self.config.get('transport', 'host') == 'host':
            raise McpError('Host MCP is owned by the chat. Run coros_mcp_sync.py request, have the assistant execute it, then pass --mcp-snapshot. For standalone use --mcp-config with a real server URL/command.')
        else:
            async def invoke():
                async with open_session(self.config) as session:
                    return await session_call(session, self.config, name, args)
            result = asyncio.run(asyncio.wait_for(invoke(), timeout=self.config.get('timeout_seconds', 60)))
        decode_result(result)  # Fail on isError even when returning raw content.
        return result

    def call(self, name, args):
        return decode_result(self.call_raw(name, args))

    def records(self, start, end):
        # Reuse a successful wider query only when demonstrably untruncated and scope matches.
        if self.bundle is not None:
            for c in self.bundle['calls']:
                a = c['arguments']
                if canonical(c['tool']) != canonical('querySportRecords') or a.get('sportTypeCodes') != RUNNING_CODES:
                    continue
                if a['startDate'] <= start <= end <= a['endDate']:
                    rows = parse_records(decode_result(c['result']))
                    if len(rows) >= a['limit']:
                        continue
                    if any(not a['startDate'] <= r['date'].replace('-', '') <= a['endDate'] or r['sportType'] not in RUNNING_CODES for r in rows):
                        raise McpError('MCP response contains activities outside the declared query scope')
                    return [r for r in rows if start <= r['date'].replace('-', '') <= end]
            raise McpError('Snapshot does not prove full running-data coverage for this range')
        rows = parse_records(self.call('querySportRecords', record_args(start, end)))
        if any(not start <= r['date'].replace('-', '') <= end or r['sportType'] not in RUNNING_CODES for r in rows):
            raise McpError('MCP response contains activities outside the declared query scope')
        if len(rows) < 60:
            return rows
        if start == end:
            raise McpError('Daily record limit reached; coverage is incomplete')
        left, right = datetime.strptime(start, '%Y%m%d'), datetime.strptime(end, '%Y%m%d')
        middle = left + (right - left) // 2
        return self.records(start, middle.strftime('%Y%m%d')) + self.records((middle + timedelta(days=1)).strftime('%Y%m%d'), end)


def add_mcp_arguments(parser):
    parser.add_argument('--mcp-config', help='MCP transport config JSON; defaults to COROS_MCP_CONFIG or host mode')
    parser.add_argument('--mcp-snapshot', help='Response bundle collected through the connected MCP host')
    parser.add_argument('--as-of', help='Local date YYYY-MM-DD for reproducible reports')
    parser.add_argument('--timezone', default='Asia/Shanghai', help='Report date timezone')
