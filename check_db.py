import sqlite3

conn = sqlite3.connect('kudosbot.db')
cursor = conn.cursor()

print("Users table columns:")
cursor.execute('PRAGMA table_info(users)')
for row in cursor.fetchall():
    print(row)

print("\nUsers table data:")
cursor.execute('SELECT * FROM users LIMIT 5')
for row in cursor.fetchall():
    print(row)

conn.close()
