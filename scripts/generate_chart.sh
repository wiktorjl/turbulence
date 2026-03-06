#!/usr/bin/env bash
# Generate daily turbulence chart PNG and send ntfy notification
# Intended to run via cron on weekdays at 1:15 PM PST (21:15 UTC)

set -euo pipefail

VENV="/home/seed/code/turbulence/.venv/bin/activate"
OUTPUT_DIR="/home/seed/code/turbulence/charts"
DATE=$(date +%Y-%m-%d)
LOG_FILE="${OUTPUT_DIR}/generate_chart.log"
NTFY_TOPIC="ntfy.sh/WiktorAI"

mkdir -p "$OUTPUT_DIR"

source "$VENV"

echo "[${DATE} $(date +%H:%M:%S)] Starting chart generation" >> "$LOG_FILE"

# Fetch latest data then generate YTD chart
turbulence fetch-data >> "$LOG_FILE" 2>&1
turbulence compute >> "$LOG_FILE" 2>&1
turbulence chart --ytd --output "${OUTPUT_DIR}/turbulence_${DATE}.png" >> "$LOG_FILE" 2>&1

# Also maintain a "latest" symlink
ln -sf "turbulence_${DATE}.png" "${OUTPUT_DIR}/turbulence_latest.png"

echo "[${DATE} $(date +%H:%M:%S)] Chart saved to ${OUTPUT_DIR}/turbulence_${DATE}.png" >> "$LOG_FILE"

# Extract score context and send ntfy notification
NOTIFY_MSG=$(python3 -c "
from turbulence import storage
import pandas as pd

df = storage.load_composite_scores()
df = df.sort_values('date').tail(10)

latest = df.iloc[-1]
score = latest['composite_score']
regime = latest['regime_label']
date = str(latest['date'].date()) if hasattr(latest['date'], 'date') else str(latest['date'])[:10]

# Calculate trend
prev = df.iloc[-2]
prev_score = prev['composite_score']
delta = score - prev_score

# 5-day average for trend context
avg_5d = df.tail(5)['composite_score'].mean()
avg_5d_prev = df.tail(6).head(5)['composite_score'].mean()
trend_5d = avg_5d - avg_5d_prev

if delta > 0.05:
    direction = '++ RISING'
elif delta < -0.05:
    direction = '-- FALLING'
else:
    direction = '~~ STABLE'

if trend_5d > 0.03:
    trend_label = 'Upward trend'
elif trend_5d < -0.03:
    trend_label = 'Downward trend'
else:
    trend_label = 'Sideways'

# Component breakdown
components = []
for col, label in [('vix_component', 'VIX'), ('realized_vol_component', 'RVol'),
                    ('turbulence_component', 'Turb'), ('garch_component', 'GARCH'),
                    ('vix_term_component', 'Term')]:
    if col in latest.index:
        components.append(f'{label}: {latest[col]:.2f}')

print(f'{direction} | Score: {score:.3f} ({delta:+.3f}) | Regime: {regime.upper()}')
print(f'5d trend: {trend_label} ({trend_5d:+.3f})')
print(f'{\" | \".join(components)}')
print(f'Date: {date}')
")

TITLE="Turbulence: $(echo "$NOTIFY_MSG" | head -1)"

curl -s \
  -H "Title: ${TITLE}" \
  -d "$NOTIFY_MSG" \
  "https://${NTFY_TOPIC}" >> "$LOG_FILE" 2>&1

echo "[${DATE} $(date +%H:%M:%S)] Notification sent to ${NTFY_TOPIC}" >> "$LOG_FILE"
