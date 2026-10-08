#!/usr/bin/env python3
"""Generate requests for a connected host, or collect via a standalone MCP server."""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from coros_mcp import (READ_TOOLS, canonical, decode_result, parse_records, record_args,
                       open_session, session_call, read_config, McpError)


def request(start, end):
    return {'schema': 'coros-mcp-request/v1', 'scope': 'running', 'calls': [
        {'tool': 'querySportRecords', 'arguments': record_args(start, end)},
        {'tool': 'queryRecoveryStatus', 'arguments': {}},
        {'tool': 'queryFitnessAssessmentOverview', 'arguments': {}},
        {'tool': 'queryTrainingLoadAssessment', 'arguments': {'days': 14}},
    ], 'follow_up': 'For every returned labelId/sportType, call getActivityDetail and append its result. A query at its limit is incomplete: split the date range and retry; never mark it covered. Save actual CallToolResult objects in coros-mcp/v1, not assistant summaries.'}


def sanitize(result):
    # Coordinates are unnecessary for weekly analysis. Preserve the protocol shape.
    if hasattr(result, 'model_dump'):
        result = result.model_dump(by_alias=True, mode='json')
    result = json.loads(json.dumps(result))
    for c in result.get('content', []):
        if c.get('type') == 'text':
            import re
            text = decode_result({'content': [c]})
            if isinstance(text, str):
                c['text'] = re.sub(r'(?m)^\s*Start Coordinates:.*\n?', '', text)
    return result


async def collect(config, manifest):
    calls = []
    async with open_session(config) as session:
        for c in manifest['calls']:
            raw = await session_call(session, config, c['tool'], c['arguments'])
            decode_result(raw)
            calls.append({**c, 'result': sanitize(raw)})
        rows = parse_records(decode_result(calls[0]['result']))
        if len(rows) >= manifest['calls'][0]['arguments']['limit']:
            raise McpError('Record limit reached; request a shorter date range before collecting')
        for row in rows:
            args = {'labelId': row['labelId'], 'sportType': row['sportType']}
            raw = await session_call(session, config, 'getActivityDetail', args)
            decode_result(raw)
            calls.append({'tool': 'getActivityDetail', 'arguments': args, 'result': sanitize(raw)})
    return {'schema': 'coros-mcp/v1', 'captured_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
            'source': 'COROS MCP', 'transport': config['transport'], 'calls': calls}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['request', 'collect'])
    parser.add_argument('--start', required=True, help='YYYYMMDD')
    parser.add_argument('--end', required=True, help='YYYYMMDD')
    parser.add_argument('--mcp-config')
    parser.add_argument('-o', '--output', required=True)
    args = parser.parse_args()
    manifest = request(args.start, args.end)
    value = manifest if args.mode == 'request' else asyncio.run(collect(read_config(args.mcp_config), manifest))
    Path(args.output).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
