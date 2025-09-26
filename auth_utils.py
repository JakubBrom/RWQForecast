from functools import wraps
from flask import request, jsonify, current_app
import jwt

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({'error': 'Token chybí'}), 401

        try:
            token = auth_header.split(" ")[1]  # "Bearer <token>"
            decoded = jwt.decode(token, current_app.secret_key, algorithms=['HS256'])
            # Můžeš předat user_id do funkce jako argument
            return f(decoded)
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Token is not valid!'}), 401

    return decorated
