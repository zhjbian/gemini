# Data Stream Status Monitoring (数据流监控)

This plan details the implementation of a real-time monitor for SPX Gamma (`ws_client.py` and JSON files) and Order Flow (`StudyOrderFlowDataExporter` tick exporter HTML file) data streams, displaying their health status at the beginning of the "综合信号" section.

## User Review Required

> [!NOTE]
> We propose checking the data stream status **on-demand** through a Flask route rather than maintaining a separate background daemon. When the web page loads, it queries `/data/data_stream_status` immediately, and then refreshes the check every **10 minutes** (using JavaScript `setInterval`). This is lightweight, real-time, and does not run background processes when the web UI is closed.

### Health Criteria
1. **SPX Gamma (`ws_client.py`)**:
   - Check if the process `quantdata/ws_client.py` is currently running (via `pgrep -f`).
   - Check if the latest file matching `spx_net_gamma_*.json` in `/Users/zhijiebian/Documents/MyDoc/Finance/Current/QuantData/Gamma` was modified within the last **5 minutes**.
2. **Order Flow Exporter**:
   - Check if today's HTML file `/Users/zhijiebian/Documents/MyDoc/Finance/Current/MotiveWave_OrderFlow_Data/Realtime/es_order_flow_realtime_YYYY-MM-DD.html` exists and was modified within the last **5 minutes**.
   
*Note: During non-RTH hours (outside 06:30 - 13:00 Seattle PST) or on non-market days, file modification age is ignored (marked as OK) to avoid false alerts.*

---

## Proposed Changes

### Backend Components

#### [MODIFY] [bbt_signals.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/data_app/bbt_signals.py)
- Create a new route `/data/data_stream_status` to evaluate and return the running status of both streams.
- Use `BBDateTime.is_market_open_today()` and `BBDateTime.is_RTH_Now()` to adjust health validation context.

---

### Frontend Components

#### [MODIFY] [bbt_signals.html](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/templates/bbt_signals.html)
- Insert a data-stream status bar with visual badges right under the "综合信号" heading (above the analysis option rows).

#### [MODIFY] [bbt_signals.js](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/static/js/bbt_signals.js)
- Implement `checkDataStreamStatus()` to query `/data/data_stream_status` and update the status bar styles.
- Bind the check to run immediately on `$(document).ready()` and set a timer to repeat the check every **10 minutes** (`600,000 ms`).

---

## Verification Plan

### Manual Verification
- Deploy and verify that:
  1. On page load, the status bar shows "正在检测..." and then renders the badges.
  2. If `ws_client.py` is running and receiving data, the SPX Gamma badge shows green `运行正常`.
  3. If you manually stop `ws_client.py`, the badge updates to red `ws_client.py 未运行`.
  4. If the Java exporter is writing ticks, the Order Flow badge shows green `正常`.
