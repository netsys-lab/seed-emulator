#!/usr/bin/env python3
import sqlite3, time, json
from pathlib import Path

con = sqlite3.connect('server/stkservers.db')

# Get list of all tables
cursor = con.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

# Print each table name
print("Tables in database:")
for table in tables:
    print(f"- {table[0]}")

# Print all tables and their contents
cursor = con.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

print("\nTables in database:")
for table in tables:
    table_name = table[0]
    print(f"\n=== {table_name} ===")
    
    # Get column names
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [col[1] for col in cursor.fetchall()]
    
    # Get table contents
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()
    
    # Print column headers
    print(" | ".join(columns))
    print("-" * 80)
    
    # Print rows
    for row in rows:
        print(" | ".join(str(val) for val in row))



q = '''
SELECT username,
       COUNT(*)                AS races,
       SUM(place = 1)          AS wins,
       ROUND(AVG(total_time),2) AS avg_time
FROM   v6_player_stats
GROUP  BY username
ORDER  BY wins DESC, avg_time ASC;
'''
rows = [dict(zip(('name','races','wins','avg_time'), r)) for r in con.execute(q)]
print(rows)
