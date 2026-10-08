import asyncio
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from coros_mcp import ToolCaller, McpError, decode_result, parse_records, record_args
from coros_client import CorosClient
from coros_weekly_report import analyze_weekly_data
from coros_push_plan import DailyWorkout, RunSegment, mcp_request

# Dates, IDs, durations and physiological values below are synthetic test fixtures.
TEXT = '''Sport Records — 2025-01-07 to 2025-01-08 (2 records)
========================

1. Outdoor Run — 2025-01-07
   Duration: 30:00 | Distance: 5.00 km
   Average Pace: 6:00 /km | Avg HR: 135 bpm
   LabelId: 9007199254740993001 | SportType: 100

2. Track Run — 2025-01-08
   Duration: 15:00 | Distance: 3.00 km
   Average Pace: 5:00 /km | Avg HR: 150 bpm
   LabelId: 9007199254740993002 | SportType: 103
'''
DETAIL = 'Workout Time: 30:00\nTotal Time: 45:00\nTraining Load: 40\nAverage Cadence: 178 spm'


def result(text):
    return {'content': [{'type': 'text', 'text': json.dumps(text)}], 'isError': False}


def bundle():
    calls = [{'tool': 'querySportRecords', 'arguments': record_args('20250106', '20250109'), 'result': result(TEXT)}]
    calls += [{'tool': 'getActivityDetail', 'arguments': {'labelId': id, 'sportType': sport}, 'result': result(DETAIL)}
              for id, sport in [('9007199254740993001', 100), ('9007199254740993002', 103)]]
    return {'schema': 'coros-mcp/v1', 'captured_at': '2025-01-09T12:00:00+08:00', 'calls': calls}


class McpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'response.json'
        self.data = bundle()
        self.save()

    def tearDown(self):
        self.tmp.cleanup()

    def save(self):
        self.path.write_text(json.dumps(self.data))

    def client(self):
        return CorosClient(snapshot=self.path, as_of='2025-01-09')

    def test_wrapped_text_and_large_id(self):
        rows = parse_records(decode_result(result(TEXT)))
        self.assertEqual(rows[0]['labelId'], '9007199254740993001')
        self.assertEqual(rows[0]['distance'], 5000)

    def test_weekly_summary_and_existing_analysis(self):
        summary = self.client().generate_weekly_summary(0)
        self.assertEqual(summary['run_distance_km'], 8)
        self.assertEqual(summary['total_training_load'], 80)
        self.assertEqual(summary['total_duration_sec'], 3600)  # Workout Time, not Total Time.
        self.assertFalse(summary['complete'])
        self.assertEqual(summary['queried_through'], '2025-01-09')
        analysis = analyze_weekly_data(summary)
        self.assertEqual(analysis['actual']['run_count'], 2)
        self.assertEqual(analysis['activities_detail'][0]['label_id'], '9007199254740993001')

    def test_missing_load_is_not_zero(self):
        for c in self.data['calls'][1:]:
            c['result'] = result('Workout Time: 30:00')
        self.save()
        self.assertIsNone(self.client().generate_weekly_summary(0)['total_training_load'])

    def test_limit_is_not_complete(self):
        self.data['calls'][0]['arguments']['limit'] = 2
        self.save()
        with self.assertRaises(McpError):
            self.client().generate_weekly_summary(0)

    def test_missing_range_does_not_become_empty(self):
        with self.assertRaises(McpError):
            self.client().generate_weekly_summary(1)

    def test_failed_query_is_not_empty(self):
        self.data['calls'][0]['result']['isError'] = True
        self.save()
        with self.assertRaises(McpError):
            self.client().generate_weekly_summary(0)

    def test_duplicate_and_malformed_records_rejected(self):
        with self.assertRaises(McpError):
            parse_records(TEXT.replace('9007199254740993002', '9007199254740993001'))
        with self.assertRaises(McpError):
            parse_records(TEXT.replace('(2 records)', '(3 records)'))

    def test_successful_empty_result_is_zero(self):
        self.data['calls'][0]['result'] = result('No sport records found from 2025-01-06 to 2025-01-09.')
        self.data['calls'] = self.data['calls'][:1]
        self.save()
        summary = self.client().generate_weekly_summary(0)
        self.assertEqual(summary['total_activities'], 0)
        self.assertEqual(summary['total_training_load'], 0)
        self.assertEqual(summary['run_distance_km'], 0)

    def test_unknown_format_rejected(self):
        with self.assertRaises(McpError):
            parse_records({'distance': 5000})

    def test_host_without_snapshot_has_actionable_error(self):
        with self.assertRaisesRegex(McpError, 'Host MCP'):
            ToolCaller({'transport': 'host'}).call('queryRecoveryStatus', {})

    def test_reads_cannot_invoke_write(self):
        with self.assertRaises(McpError):
            ToolCaller({'transport': 'host'}, self.path).call('createScheduledWorkout', {})

    def test_export_uses_date_and_exact_segment_units(self):
        workout = DailyWorkout(1, '周一', '2025-01-13', '轻松跑', segments=[RunSegment('main', 5, 360, 370)])
        call = mcp_request(workout)
        self.assertEqual(call['tool'], 'createScheduledWorkout')
        self.assertEqual(call['arguments']['date'], '20250113')
        section = call['arguments']['course']['sections'][0]
        self.assertEqual(section['targetValue'], 5000)
        self.assertEqual(section['intensityValueStart'], 360)

    def test_weekly_cli_no_legacy_credentials(self):
        script = Path(__file__).resolve().parents[1] / 'coros_weekly_report.py'
        run = subprocess.run([sys.executable, str(script), '--mcp-snapshot', str(self.path), '--as-of', '2025-01-09', '--weeks-ago', '0', '--json'], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)['actual']['run_km'], 8)

    @unittest.skipUnless(importlib.util.find_spec('mcp'), 'Standalone MCP SDK not installed')
    def test_real_stdio_mcp_protocol(self):
        server = Path(self.tmp.name) / 'server.py'
        server.write_text('''from mcp.server.fastmcp import FastMCP
mcp = FastMCP("test")

@mcp.tool()
def queryRecoveryStatus() -> str:
    return "Recovery: 88%"

if __name__ == "__main__":
    mcp.run()
''')
        caller = ToolCaller({'transport': 'stdio', 'command': sys.executable, 'args': [str(server)]})
        self.assertEqual(caller.call('queryRecoveryStatus', {}), 'Recovery: 88%')


if __name__ == '__main__':
    unittest.main()
