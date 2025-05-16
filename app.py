import os
import sqlite3
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import eventlet

eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'

socketio = SocketIO(app, async_mode='eventlet')

DB_FILE = 'chat.db'

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            username TEXT, 
            message TEXT
        )''')
        conn.commit()

@app.route('/')
def index():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        # Select id too to track messages for deletion
        c.execute("SELECT id, username, message FROM messages ORDER BY id DESC LIMIT 50")
        messages = c.fetchall()[::-1]  # Reverse to show oldest first
    return render_template('index.html', messages=messages)

@socketio.on('send_message')
def handle_send(data):
    try:
        username = "anom"  # You can replace this with real user logic
        message = data.get('message', '').strip()
        if not message:
            return  # ignore empty messages

        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("INSERT INTO messages (username, message) VALUES (?, ?)", (username, message))
            message_id = c.lastrowid
            conn.commit()

        # Broadcast inserted message with its DB id
        emit('receive_message', {'id': message_id, 'username': username, 'message': message}, broadcast=True)
    except Exception as e:
        print("Error in send_message:", e)

@socketio.on('delete_messages')
def handle_delete_messages(data):
    try:
        amount = data.get('amount', 0)
        if not isinstance(amount, int) or amount <= 0:
            return  # Ignore invalid inputs

        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("SELECT id FROM messages ORDER BY id DESC LIMIT ?", (amount,))
            rows = c.fetchall()
            ids_to_delete = [row[0] for row in rows]

            if ids_to_delete:
                placeholders = ','.join(['?'] * len(ids_to_delete))
                c.execute(f"DELETE FROM messages WHERE id IN ({placeholders})", ids_to_delete)
                conn.commit()

        # Notify clients to remove deleted messages
        emit('messages_deleted', {'deleted_ids': ids_to_delete}, broadcast=True)
    except Exception as e:
        print("Error in delete_messages:", e)

if __name__ == '__main__':
    init_db()
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
