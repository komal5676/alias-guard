import sqlite3

DATABASE = "aliasguard.db"


def get_db():
	conn = sqlite3.connect(DATABASE)
	conn.row_factory = sqlite3.Row
	return conn


def init_db():
	conn = get_db()

	conn.execute("""
		CREATE TABLE IF NOT EXISTS aliases (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			alias TEXT UNIQUE NOT NULL,
			service TEXT NOT NULL,
			purpose TEXT,
			trust_level TEXT,
			status TEXT DEFAULT 'ACTIVE',
			risk_score INTEGER DEFAULT 0,
			messages INTEGER DEFAULT 0,
			leaked INTEGER DEFAULT 0,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)
	""")

	conn.execute("""
		CREATE TABLE IF NOT EXISTS events (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			alias TEXT,
			event_type TEXT,
			description TEXT,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)
	""")

	conn.commit()
	conn.close()
