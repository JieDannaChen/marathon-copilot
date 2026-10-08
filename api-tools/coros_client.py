#!/usr/bin/env python3
"""COROS client backed exclusively by MCP tools. See README_MCP.md."""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from coros_mcp import ToolCaller, McpError, add_mcp_arguments, field, number, seconds, RUNNING_CODES

SPORT_NAMES = {100: '跑步', 101: '室内跑', 102: '越野跑', 103: '运动场跑步'}
RUNNING_SPORT_TYPES = set(RUNNING_CODES)


def format_pace(value):
    return f'{int(value) // 60}\'{int(value) % 60:02d}"' if value and value > 0 else '--:--'


def format_duration(value):
    if value is None or value < 0:
        return '--:--'
    h, rem = divmod(int(value), 3600)
    m, s = divmod(rem, 60)
    return f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'


def get_sport_name(sport_type, mode=0):
    return SPORT_NAMES.get(sport_type, '其他')


class CorosClient:
    """MCP-only read adapter; caller may be injected for tests or other hosts."""
    def __init__(self, *, mcp_config=None, snapshot=None, as_of=None,
                 timezone='Asia/Shanghai', caller=None):
        from coros_mcp import read_config
        self.timezone = ZoneInfo(timezone)
        self.today = date.fromisoformat(as_of) if as_of else datetime.now(self.timezone).date()
        self.caller = caller or ToolCaller(read_config(mcp_config), snapshot)

    @classmethod
    def from_args(cls, args):
        return cls(mcp_config=args.mcp_config, snapshot=args.mcp_snapshot,
                   as_of=args.as_of, timezone=args.timezone)

    def get_activity_detail(self, label_id, sport_type):
        return self.caller.call('getActivityDetail', {'labelId': str(label_id), 'sportType': sport_type})

    def get_activity_laps(self, label_id, sport_type):
        return self.caller.call('queryActivityLapData', {'labelId': str(label_id), 'sportType': sport_type})

    def get_activities(self, size=20, page=1, mode_list='', start_date=None, end_date=None):
        if page != 1 or mode_list:
            raise McpError('MCP uses explicit date ranges and running scope, not legacy API pages/modeList')
        end = end_date or self.today.strftime('%Y%m%d')
        start = start_date or (self.today - timedelta(days=6)).strftime('%Y%m%d')
        rows = self.caller.records(start, end)
        return {'result': '0000', 'source': 'COROS MCP',
                'data': {'dataList': rows[:size], 'count': len(rows)}, 'scope': RUNNING_CODES}

    def _enrich(self, row):
        detail = self.get_activity_detail(row['labelId'], row['sportType'])
        if not isinstance(detail, str):
            raise McpError('Unrecognized activity detail schema; do not assume units')
        workout_time = field(detail, 'Workout Time', r'([\d:]+)')
        if workout_time:
            row['totalTime'] = seconds(workout_time)
        mapping = {'trainingLoad': 'Training Load', 'avgCadence': 'Average Cadence',
                   'avgPower': 'Average Power', 'avgStrideLength': 'Average Stride Length',
                   'maxHr': 'Maximum Heart Rate', 'ascent': 'Elevation Gain'}
        for key, label in mapping.items():
            row[key] = number(detail, label)
        return row

    def get_weekly_activities(self, weeks_ago=0, size=60):
        if weeks_ago < 0:
            raise ValueError('weeks_ago must be nonnegative')
        monday = self.today - timedelta(days=self.today.weekday() + weeks_ago * 7)
        end = min(monday + timedelta(days=6), self.today)
        rows = self.caller.records(monday.strftime('%Y%m%d'), end.strftime('%Y%m%d'))
        return [self._enrich(dict(r)) for r in rows]

    def generate_weekly_summary(self, weeks_ago=0):
        activities = self.get_weekly_activities(weeks_ago)
        monday = self.today - timedelta(days=self.today.weekday() + weeks_ago * 7)
        sunday = monday + timedelta(days=6)
        summary = {
            'source': 'COROS MCP', 'scope': RUNNING_CODES, 'as_of': str(self.today),
            'week_start': str(monday), 'week_end': str(sunday),
            'queried_through': str(min(sunday, self.today)), 'complete': sunday <= self.today,
            'total_activities': len(activities), 'run_count': len(activities),
            'total_distance_km': round(sum(r['distance'] for r in activities) / 1000, 3),
            'total_duration_sec': sum(r['totalTime'] for r in activities),
            'total_training_load': sum(r['trainingLoad'] for r in activities)
                if all(r['trainingLoad'] is not None for r in activities) else None,
            'activities': [],
        }
        for a in activities:
            summary['activities'].append({
                'label_id': a['labelId'], 'sport_type': a['sportType'],
                'name': a['name'], 'date': a['date'], 'type': get_sport_name(a['sportType']),
                'distance_km': round(a['distance'] / 1000, 3),
                'duration': format_duration(a['totalTime']), 'duration_sec': a['totalTime'],
                'pace': format_pace(a['avgSpeed']), 'avg_speed': a['avgSpeed'],
                'avg_hr': a['avgHr'], 'max_hr': a['maxHr'], 'avg_cadence': a['avgCadence'],
                'training_load': a['trainingLoad'], 'avg_power': a.get('avgPower'),
                'avg_stride_length': a.get('avgStrideLength'), 'ascent': a.get('ascent'),
                'calories_kcal': None,
            })
        summary['run_distance_km'] = summary['total_distance_km']
        summary['run_duration_sec'] = summary['total_duration_sec']
        summary['total_duration_str'] = format_duration(summary['total_duration_sec'])
        summary['run_duration_str'] = summary['total_duration_str']
        return summary

    def get_schedule(self, start_date, end_date):
        return self.caller.call('queryTrainingSchedule', {'startDate': start_date, 'endDate': end_date})

    def get_health_summary(self):
        rec = self.caller.call('queryRecoveryStatus', {})
        fitness = self.caller.call('queryFitnessAssessmentOverview', {})
        return {'source': 'COROS MCP', 'captured_at': (getattr(self.caller, 'bundle', None) or {}).get('captured_at', datetime.now(self.timezone).isoformat()),
                'mcp_raw': {'recovery': rec, 'fitness': fitness},
                'sleep_hrv': {}, 'resting_hr': None,
                'recovery': {'recovery_pct': number(rec, 'Recovery') if isinstance(rec, str) else None}}

    def get_training_load_detail(self, days=14):
        raw = self.caller.call('queryTrainingLoadAssessment', {'days': days})
        # Do not relabel Short-Term Load as ATI, or Long-Term Load as CTI.
        return {'source': 'COROS MCP', 'mcp_raw': raw, 'summary': {}, 'daily_metrics': []}



def main():
    parser = argparse.ArgumentParser(description='COROS MCP-only data client')
    add_mcp_arguments(parser)
    parser.add_argument('--json', action='store_true')
    sub = parser.add_subparsers(dest='command', required=True)
    act = sub.add_parser('activities')
    act.add_argument('--start')
    act.add_argument('--end')
    act.add_argument('--size', type=int, default=60)
    wk = sub.add_parser('weekly')
    wk.add_argument('--weeks-ago', type=int, default=1)
    sch = sub.add_parser('schedule')
    sch.add_argument('--start', required=True)
    sch.add_argument('--end', required=True)
    sub.add_parser('health')
    args = parser.parse_args()
    client = CorosClient.from_args(args)
    try:
        if args.command == 'activities':
            result = client.get_activities(size=args.size, start_date=args.start, end_date=args.end)
        elif args.command == 'weekly':
            result = client.generate_weekly_summary(args.weeks_ago)
        elif args.command == 'schedule':
            result = client.get_schedule(args.start, args.end)
        else:
            result = {'health': client.get_health_summary(), 'training_load': client.get_training_load_detail()}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (McpError, ValueError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
