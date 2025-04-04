from flask import session, request
from flask_socketio import emit

connected_users = {}

def register_socketio_events(socketio):

    @socketio.on("connect")
    def handle_connect():
        user_id = session.get("user_id")  # Pokud je uživatel přihlášen
        if not user_id:
            user_id = request.sid  # Pokud ne, použijeme request.sid

        connected_users[user_id] = request.sid
        print(f"Uživatel {user_id} připojen s ID {request.sid}")
        print(f"Seznam připojených uživatelů: {connected_users}")

    @socketio.on("disconnect")
    def handle_disconnect():
        user_id = next((uid for uid, sid in connected_users.items() if sid == request.sid), None)
        if user_id:
            del connected_users[user_id]
            print(f"Uživatel {user_id} odpojen")

# @socketio.on('connect')
# def handle_connect():
#     print(f"User {request.sid} is connected now.")

# @socketio.on('disconnect')
# def handle_disconnect():
#     print(f"User {request.sid} disconnected.")

# @socketio.on('join')
# def handle_join(data):
#     room = data['room']
#     join_room(room)
#     emit('message', f"User joined the room {room}", room=room)

# @socketio.on('leave')
# def handle_leave(data):
#     room = data['room']
#     leave_room(room)
#     emit('message', f"User leaved the room {room}", room=room)

# @socketio.on('private_message')
# def handle_private_message(data):
#     recipient_sid = data.get('recipient_sid')
#     message = data.get('message')
#     emit('new_message', message, room=recipient_sid)
    
# @socketio.on('force_disconnect')
# def force_disconnect():
#     disconnect()