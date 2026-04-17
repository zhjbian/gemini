import sys
import os

# Add relevant directories to the path
sys.path.append("/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web")
sys.path.append("/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/db_query_module")
sys.path.append("/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools")

try:
    from db_query_order_flow import OrderFlowQueryMixin
    print("Calling backfillRthFh...")
    count = OrderFlowQueryMixin.backfillRthFh()
    print(f"Done. {count} records updated.")
except Exception as e:
    print(f"Error executing backfill: {e}")
    import traceback
    traceback.print_exc()
