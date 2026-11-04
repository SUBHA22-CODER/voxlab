import sqlite3
from app.core.security import hash_password

con = sqlite3.connect("voxlab.db")
con.execute("UPDATE users SET password_hash = ? WHERE email = ?", (hash_password("demo123"), "demo@voxlab.dev"))
con.commit()
print("Successfully synced demo@voxlab.dev password hash to demo123")

