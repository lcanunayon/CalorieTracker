import os
import sqlite3
import sys

DB = os.path.join(os.path.dirname(__file__), '..', 'data.db')
DB = os.path.abspath(DB)

print('Checking DB at:', DB)
try:
    st = os.stat(DB)
    print('File exists. Size:', st.st_size, 'bytes')
except FileNotFoundError:
    print('Database file not found at', DB)
    sys.exit(1)

try:
    conn = sqlite3.connect(DB, timeout=10)
    cur = conn.cursor()
    print('\nListing sqlite_master entries:')
    for row in cur.execute("SELECT type, name, tbl_name FROM sqlite_master ORDER BY type, name"):
        print(' ', row)

    print('\nTrying a small query on users table (if exists):')
    try:
        for r in cur.execute('SELECT id, username FROM user LIMIT 5'):
            print(' ', r)
    except Exception as e:
        print('  Could not query `user` table:', e)

    conn.close()
    print('\nOK: DB check completed successfully')
except Exception as e:
    print('\nERROR when accessing DB:')
    import traceback
    traceback.print_exc()
    sys.exit(2)
