import os
import sqlite3
import sys

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB = os.path.join(BASE, 'data.db')

print('Using DB:', DB)
if not os.path.exists(DB):
    print('Database not found:', DB)
    sys.exit(1)

# Backup first
bak = DB + '.bak'
if not os.path.exists(bak):
    print('Creating backup:', bak)
    import shutil
    shutil.copy2(DB, bak)
else:
    print('Backup exists:', bak)

conn = sqlite3.connect(DB)
cur = conn.cursor()

# check columns
cur.execute("PRAGMA table_info('entry')")
cols = [r[1] for r in cur.fetchall()]
print('Entry columns:', cols)
if 'user_id' in cols:
    print('user_id column already exists; nothing to do')
    conn.close()
    sys.exit(0)

print('Adding user_id column to entry table...')
try:
    cur.execute('ALTER TABLE entry ADD COLUMN user_id INTEGER')
    conn.commit()
    print('Added column user_id')
except Exception as e:
    print('Failed to add column:', e)
    conn.rollback()
    conn.close()
    sys.exit(2)

# Optionally set existing rows to a default user id (skip by default)
# If you want to set a default, uncomment and set default_user_id variable
# default_user_id = 1
# cur.execute('UPDATE entry SET user_id = ?', (default_user_id,))
# conn.commit()

conn.close()
print('Done. You may restart the app now.')
