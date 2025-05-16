import os
import sqlite3
from flask import Flask, render_template, request, abort
from flask_socketio import SocketIO, emit
import eventlet

eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'

socketio = SocketIO(app, async_mode='eventlet')

DB_FILE = 'chat.db'
LOCK_FILE = 'lockstatus.txt'

PASSWORD = "100005"
is_locked = False

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
def check_lock():
    global is_locked

    if request.path in ['/coverup', '/static/favicon.ico']:
        return  # Allow /coverup without password

    if is_locked:
        pw = request.args.get('password', '')
        if pw != PASSWORD:
            abort(401, description='Unauthorized: Site is locked, password required')

@app.route('/coverup', methods=['GET', 'POST'])
def coverup():
    global is_locked

    if request.method == 'GET':
        return render_template('coverup.html')

    password = request.form.get('password', '')
    if password != PASSWORD:
        return render_template('coverup.html', error='Wrong password')

    is_locked = not is_locked
    save_lock_status()
    status = "LOCKED" if is_locked else "UNLOCKED"
    return render_template('coverup_result.html', status=status)

@app.route('/')
def index():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT id, username, message FROM messages ORDER BY id DESC LIMIT 50")
        messages = c.fetchall()[::-1]
    return render_template('index.html', messages=messages)

@socketio.on('send_message')
def handle_send(data):
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

if __name__ == '__main__':
    load_lock_status()
    init_db()
    socketio.run(app, host='0.0.0.0', port=5000)
