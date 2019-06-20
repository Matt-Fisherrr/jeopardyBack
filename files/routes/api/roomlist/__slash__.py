from flask import request, jsonify, current_app as app
from __main__ import global_vars as gv
from flask_cors import cross_origin

@app.route('/api/roomlist', methods=['GET'])
@cross_origin(allow_headers=['authorization', 'content-type'], allow_methods=['GET, OPTIONS'])
@gv.auth.auth_required(request)
def get_room_list():
    access_token = gv.auth.get_token_auth_header(request)
    rooms = []
    for room in gv.room_list:
        rooms.append({'name':gv.room_list[room].name, 'id':gv.room_list[room].room_id, 'players':'started' if gv.room_list[room].started else gv.room_list[room].player_counts['total_count'], 'old':False })
    gv.cur.execute("SELECT room_name, room_id, player1, player2, player3, started FROM rooms WHERE room_owner = %s AND complete = 0",(gv.connected_users[access_token]['auth0_code'],))
    for room in gv.cur.fetchall():
        if room[1] not in list(gv.room_list.keys()):
            rooms.append({'name':room[0], 'id':room[1], 'players':'started' if room[5] == 1 else len([p for p in room[2:4] if p != None]), 'old':True })
    return jsonify(rooms)