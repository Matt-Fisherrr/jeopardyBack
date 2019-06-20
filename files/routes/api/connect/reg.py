from flask import request, jsonify, current_app as app
from __main__ import global_vars as gv
from flask_cors import cross_origin

@app.route('/api/connect/reg', methods=['POST'])
@cross_origin(allow_headers=['authorization', 'content-type'], allow_methods=['POST, OPTIONS'])
@gv.auth.auth_required(request)
def set_username():
    access_token = gv.auth.get_token_auth_header(request)
    username = request.get_json()['user']
    gv.cur.execute("SELECT count(auth0_code) FROM players WHERE auth0_code = %s", (gv.connected_users[access_token]['auth0_code'],))
    if gv.cur.fetchone()[0] == 0:
        gv.cur.execute("INSERT INTO players(username, auth0_code) VALUES (%s, %s)", (username, gv.connected_users[access_token]['auth0_code']))
    else:
        gv.cur.execute("UPDATE players SET username = %s WHERE auth0_code = %s", (username, gv.connected_users[access_token]['auth0_code']))
    gv.connected_users[access_token]['username'] = username
    gv.conn.commit()
    return jsonify({'response': True, 'username': username})