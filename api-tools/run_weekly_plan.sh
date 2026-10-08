#!/bin/bash
# Weekly Training Plan Generator — Cron Wrapper
#
# Runs every Sunday evening (or Monday morning) to:
#   1. Pull last week's COROS watch data
#   2. Generate next week's training plan prompt
#   3. Keep the plan pending runner confirmation and explicit MCP push
#   4. Save weekly report + prompt to reports/
#
# Crontab entry examples:
#   # Sunday 20:00 Beijing time (prepare for next week)
#   0 20 * * 0 /path/to/api-tools/run_weekly_plan.sh >> /path/to/reports/weekly_cron.log 2>&1
#
#   # Monday 06:00 Beijing time (start of new training week)
#   0 6 * * 1 /path/to/api-tools/run_weekly_plan.sh >> /path/to/reports/weekly_cron.log 2>&1
#
# Prerequisites:
#   - COROS_MCP_CONFIG for a standalone server, or a refreshed COROS_MCP_SNAPSHOT
#   - Host-only MCP cannot be refreshed by cron; execute the request manifest in the chat first
#   - training_cycle_config.yaml (training plan)
#   - runner_profile_*.yaml (runner data)
#   - Python 3.10+ with requirements-mcp.txt and pyyaml for standalone MCP

set -euo pipefail
export TZ='Asia/Shanghai'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-python3}"
REPORTS_DIR="${REPORTS_DIR:-$SCRIPT_DIR/reports}"
LOG_FILE="$REPORTS_DIR/weekly_cron.log"

# Ensure reports directory exists
mkdir -p "$REPORTS_DIR" || { echo "[ERROR] Cannot create $REPORTS_DIR" >&2; exit 1; }

echo "===== $(date '+%Y-%m-%d %H:%M:%S %Z') Weekly Plan Start =====" >> "$LOG_FILE"

# Check Python availability
if ! command -v "$PYTHON" &> /dev/null; then
    echo "[ERROR] Python not found: $PYTHON" >> "$LOG_FILE"
    exit 1
fi

# Check if training cycle is over
TODAY=$(date '+%Y%m%d')
CYCLE_END=$("$PYTHON" -c "
import sys; sys.path.insert(0, '$SCRIPT_DIR')
try:
    import yaml
    from pathlib import Path
    # Find training cycle config
    p = None
    for f in Path('$SCRIPT_DIR').glob('training_cycle_config*.yaml'):
        if '.example' not in f.name:
            p = f; break
    if not p:
        print('99991231')
        sys.exit(0)
    cfg = yaml.safe_load(open(p))
    end = cfg.get('cycle', {}).get('end_date', '9999-12-31')
    print(str(end).replace('-', ''))
except Exception:
    print('99991231')
" 2>/dev/null)

if [ "$TODAY" -gt "$CYCLE_END" ]; then
    echo "[INFO] Training cycle ended ($CYCLE_END). Stopping." >> "$LOG_FILE"
    exit 0
fi

# Generate date-stamped filename
WEEK_START=$(date -d "last monday" '+%Y%m%d' 2>/dev/null || date '+%Y%m%d')
PROMPT_FILE="$REPORTS_DIR/weekly_plan_prompt_${WEEK_START}.md"
REPORT_FILE="$REPORTS_DIR/weekly_report_${WEEK_START}.json"

cd "$SCRIPT_DIR" || { echo "[ERROR] Cannot cd to $SCRIPT_DIR" >&2; exit 1; }

# Step 1: Generate weekly report (JSON) + save to reports/
echo "[INFO] Pulling COROS data and generating report..." >> "$LOG_FILE"
if ! "$PYTHON" generate_next_week_plan.py \
    --report-only --json --save-report \
    -o "$REPORT_FILE" 2>> "$LOG_FILE"; then
    echo "[ERROR] Weekly report generation failed" >> "$LOG_FILE"
    # Don't exit — try prompt generation anyway
fi

# Step 2: Generate training plan prompt (Markdown)
echo "[INFO] Generating training plan prompt..." >> "$LOG_FILE"
if ! "$PYTHON" generate_next_week_plan.py \
    -o "$PROMPT_FILE" 2>> "$LOG_FILE"; then
    echo "[ERROR] Prompt generation failed at $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
    exit 1
fi

echo "[OK] Weekly report saved: $REPORT_FILE" >> "$LOG_FILE"
echo "[OK] Plan prompt saved: $PROMPT_FILE" >> "$LOG_FILE"

# Step 3: No automatic writes. A generated plan still needs runner confirmation
# and explicit push authorization in the MCP host.
echo "[INFO] COROS MCP read workflow complete; no workouts were pushed." >> "$LOG_FILE"

echo "===== $(date '+%Y-%m-%d %H:%M:%S %Z') Weekly Plan End =====" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# Log rotation: keep last 500 lines
if [ -f "$LOG_FILE" ] && [ "$(wc -l < "$LOG_FILE")" -gt 1000 ]; then
    tail -500 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
fi
