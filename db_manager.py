import sqlite3

class DBManager:
    def __init__(self, db_name='twitch_db.sqlite'):
        self.conn = sqlite3.connect(db_name)
        self.create_tables()

    # -----------------------
    # Database setup methods
    # -----------------------

    def create_tables(self):
        cur = self.conn.cursor()
        # Create the streamers table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS streamers (
                server_id INTEGER,
                twitch_name TEXT,
                last_notified_at TIMESTAMP,
                PRIMARY KEY (server_id, twitch_name)
            )
        ''')
        # Create the commands table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS commands (
                server_id INTEGER,
                command TEXT,
                response TEXT,
                PRIMARY KEY (server_id, command)
            )
        ''')
        # Create the servers_channels table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS servers_channels (
                server_id INTEGER,
                channel_id INTEGER,
                PRIMARY KEY (server_id, channel_id)
            )
        ''')
        self.conn.commit()

    # -----------------------
    # Streamer methods
    # -----------------------

    def add_streamer(self, server_id, twitch_name):
        # Add a streamer to the database
        cur = self.conn.cursor()
        cur.execute('''
            INSERT OR IGNORE INTO streamers (server_id, twitch_name, last_notified_at) 
            VALUES (?, ?, ?)
        ''', (server_id, twitch_name, "1970-01-01 00:00:00"))
        self.conn.commit()

    def remove_streamer(self, server_id, twitch_name):
        # Remove a streamer from the database
        cur = self.conn.cursor()
        cur.execute('DELETE FROM streamers WHERE server_id = ? AND twitch_name = ?', (server_id, twitch_name,))
        self.conn.commit()

    def list_streamers(self, server_id):
        # List all streamers for a server
        cur = self.conn.cursor()
        cur.execute('SELECT twitch_name FROM streamers WHERE server_id = ?', (server_id,))
        rows = cur.fetchall()
        return [row[0] for row in rows]

    def get_last_notified_at(self, server_id, twitch_name):
        # Get the last notified time for a streamer
        cur = self.conn.cursor()
        cur.execute('SELECT last_notified_at FROM streamers WHERE server_id = ? AND twitch_name = ?', (server_id, twitch_name,))
        row = cur.fetchone()
        return row[0] if row else None

    def set_last_notified_at(self, server_id, twitch_name, last_notified_at):
        # Set the last notified time for a streamer
        cur = self.conn.cursor()
        cur.execute('''
            INSERT OR REPLACE INTO streamers (server_id, twitch_name, last_notified_at) 
            VALUES (?, ?, ?)
        ''', (server_id, twitch_name, last_notified_at))
        self.conn.commit()

    # -----------------------
    # Command methods
    # -----------------------

    def add_command(self, server_id, command, response):
        # Add a command to the database
        cur = self.conn.cursor()
        cur.execute('INSERT OR IGNORE INTO commands (server_id, command, response) VALUES (?, ?, ?)', (server_id, command, response))
        self.conn.commit()

    def remove_command(self, server_id, command):
        # Remove a command from the database
        cur = self.conn.cursor()
        cur.execute('DELETE FROM commands WHERE server_id = ? AND command = ?', (server_id, command,))
        self.conn.commit()

    def list_commands(self, server_id):
        # List all commands for a server
        cur = self.conn.cursor()
        cur.execute('SELECT command, response FROM commands WHERE server_id = ?', (server_id,))
        return dict(cur.fetchall())

    # -----------------------
    # Server-channel methods
    # -----------------------

    def get_channel_id(self, server_id):
        # Get the channel ID for a server
        cur = self.conn.cursor()
        cur.execute('SELECT channel_id FROM servers_channels WHERE server_id = ?', (server_id,))
        row = cur.fetchone()
        return row[0] if row else None

    def add_server_channel(self, server_id, channel_id):
        # Set the channel ID for a server
        cur = self.conn.cursor()
        cur.execute('''
            INSERT OR REPLACE INTO servers_channels (server_id, channel_id) 
            VALUES (?, ?)
        ''', (server_id, channel_id))
        self.conn.commit()

    def remove_server_channel(self, server_id, channel_id):
        cur = self.conn.cursor()
        cur.execute("""
            DELETE FROM servers_channels WHERE server_id = ? AND channel_id = ?
        """, (server_id, channel_id))
        self.conn.commit()
