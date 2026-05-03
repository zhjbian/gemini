import sys
import os
from datetime import datetime, timedelta

# Add relevant paths to sys.path
sys.path.append('/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web')

from db_connection_legacy import create_engine, DATABASE_URL
from sqlalchemy import text

def get_unique_exec_types_last_365():
    engine = create_engine(DATABASE_URL)
    n_days_ago = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    try:
        with engine.connect() as connection:
            print(f"Querying unique base exec_type since {n_days_ago}...")
            query = text(f"SELECT DISTINCT exec_type FROM option_flow WHERE exec_type IS NOT NULL AND transac_date >= '{n_days_ago}';")
            result = connection.execute(query)
            
            # Strip prefixes D. and N.
            types = set()
            for row in result:
                t = row[0]
                if t.startswith('D.') or t.startswith('N.'):
                    t = t[2:]
                types.add(t)
            
            sorted_types = sorted(list(types))
            print("\n".join(sorted_types))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_unique_exec_types_last_365()
