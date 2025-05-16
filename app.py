import os
import sqlite3
from flask import Flask, render_template, request, abort, jsonify
from flask_socketio import SocketIO, emit
import eventlet

eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'

socketio = SocketIO(app, async_mode='eventlet')

DB_FILE = 'chat.db'
LOCK_FILE = 'lockstatus.txt'

PASSWORD = "100005"
is_locked = False  # global variable, loaded from LOCK_FILE

def load_lock_status():
    global is_locked
    if os.path.exists(LOCK_FILE):
        with open(LOCK_FILE, 'r') as f:
            val = f.read().strip()
            is_locked = (val == 'locked')
    else:
        is_locked = False

def save_lock_status():
    with open(LOCK_FILE, 'w') as f:
        f.write('locked' if is_locked else 'unlocked')

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            username TEXT, 
            message TEXT
        )''')
        conn.commit()

@app.before_request
def require_password_if_locked():
    global is_locked

    # Allow /coverup and static files without password
    if request.path == '/coverup' or request.path.startswith('/static/'):
        return

    if is_locked:
        pw = request.args.get('password', '')
        if pw != PASSWORD:
            abort(401, description='Unauthorized - Password required')

@app.route('/coverup', methods=['POST'])
def toggle_lock():
    global is_locked
    # Accept password from form or JSON
    password = request.form.get('password') or (request.json and request.json.get('password'))
    if password != PASSWORD:
        abort(403, description='Wrong password')

    is_locked = not is_locked
    save_lock_status()
    status = "LOCKED" if is_locked else "UNLOCKED"
    return jsonify({"message": f"Site is now {status}"}), 200

@app.route('/')
def index():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT id, username, message FROM messages ORDER BY id DESC LIMIT 50")
        messages = c.fetchall()[::-1]  # oldest first
    return render_template('index.html', messages=messages)

@socketio.on('send_message')
def handle_send(data):
    try:
        username = "anom"
        message = data.get('message', '').strip()
        if not message:
            return

        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("INSERT INTO messages (username, message) VALUES (?, ?)", (username, message))
            message_id = c.lastrowid
            conn.commit()

        emit('receive_message', {'id': message_id, 'username': username, 'message': message}, broadcast=True)
    except Exception as e:
        print("Error in send_message:", e)

@socketio.on('delete_messages')
def handle_delete_messages(data):
    try:
        amount = data.get('amount', 0)
        if not isinstance(amount, int) or amount <= 0:
            return

        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("SELECT id FROM messages ORDER BY id DESC LIMIT ?", (amount,))
            rows = c.fetchall()
            ids_to_delete = [row[0] for row in rows]

            if ids_to_delete:
                placeholders = ','.join(['?'] * len(ids_to_delete))
                c.execute(f"DELETE FROM messages WHERE id IN ({placeholders})", ids_to_delete)
                conn.commit()

        emit('messages_deleted', {'deleted_ids': ids_to_delete}, broadcast=True)
    except Exception as e:
        print("Error in delete_messages:", e)

if __name__ == '__main__':
    load_lock_status()
    init_db()
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
