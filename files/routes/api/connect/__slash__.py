from flask import request, jsonify, current_app as app
from __main__ import global_vars as gv
from flask_cors import cross_origin
from jose import jwt
import hashlib

@app.route('/api/connect', methods=['POST'])
@cross_origin(allow_headers=['authorization', 'content-type'], allow_methods=['POST, OPTIONS'])
@gv.auth.auth_required(request)
def connect():
    id_token = request.get_json()['IDToken']
    access_token = gv.auth.get_token_auth_header(request)

    id_decode = jwt.decode(id_token, gv.jwks, algorithms=gv.auth.ALGORITHMS, audience="3eCEPx9I6Wr0N3FIJAwXXi5caFdRfZzV", access_token=access_token)
    hashed_id = str(hashlib.sha512(id_decode['sub'].encode('utf-8') + '8616b99be2344c82ad77f24977eac12e'.encode('utf-8')).hexdigest())
    gv.cur.execute("SELECT username FROM players WHERE auth0_code = %s", (hashed_id,))
    username = gv.cur.fetchone()

    gv.connected_users[access_token] = {'access_token':access_token, 'id_token':id_token, 'auth0_code':hashed_id}
    if username == None:
        return jsonify({'response': 'username'})

    gv.connected_users[access_token]['username'] = username[0]
    return jsonify({'response': True, 'username': username[0]})