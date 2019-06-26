from flask import request, jsonify, current_app as app
from __main__ import global_vars as gv
from flask_cors import cross_origin
from files.room import Room

@app.route('/api/roomlist/getboard', methods=['GET'])
@cross_origin(allow_headers=['authorization', 'content-type', 'room_id'], allow_methods=['GET, OPTIONS'])
@gv.auth.auth_required(request)
def get_board():
    access_token = gv.auth.get_token_auth_header(request)
    room_id = int(request.headers['room_id'])
    try:
        board = gv.room_list[room_id].board
    except:
        # print('except')
        gv.cur.execute("SELECT board_id, room_name, player1, player1score, player2, player2score, player3, player3score, started, activate_player FROM rooms WHERE room_id = %s",(room_id,))
        board_id, room_name, player1, player1score, player2, player2score, player3, player3score, started, active_player = gv.cur.fetchone()
        
        gv.room_list[room_id] = Room()
        gv.room_list[room_id].players[1]['auth0_code'] = player1
        gv.room_list[room_id].players[1]['score'] = player1score if player1score != None else 0
        gv.room_list[room_id].players[2]['auth0_code'] = player2
        gv.room_list[room_id].players[2]['score'] = player2score if player2score != None else 0
        gv.room_list[room_id].players[3]['auth0_code'] = player3
        gv.room_list[room_id].players[3]['score'] = player3score if player3score != None else 0

        gv.room_list[room_id].name = room_name
        gv.room_list[room_id].room_id = room_id
        gv.room_list[room_id].started = started
        gv.room_list[room_id].active_player = active_player
        gv.room_list[room_id].answer_count = 0

        gv.room_list[room_id].player_counts['total_count'] = len([p for p in gv.room_list[room_id].players if gv.room_list[room_id].players[p]['auth0_code'] != None])
        # print(gv.room_list[room_id].player_counts['total_count'])

        try:
            gv.room_list[room_id].room_owner = gv.connected_users[access_token]['auth0_code']
        except:
            del gv.room_list[room_id]
            return jsonify({'board':'board'})
    

        board = []
        gv.cur.execute("SELECT * FROM boards WHERE board_id = %s", (board_id,))
        cats = gv.cur.fetchone()[1:]
        for i, cat in enumerate(cats):
            gv.cur.execute("SELECT * FROM categories WHERE cat_id = %s", (cat,))
            curr_cat = gv.cur.fetchone()[1:]
            board.append({curr_cat[0]:[]})
            for clue in curr_cat[1:]:
                gv.cur.execute("SELECT * FROM clues WHERE clue_id = %s", (clue,))
                curr_clue = gv.cur.fetchone()[1:]
                board[i][curr_cat[0]].append({ 'id':curr_clue[0], 'question':curr_clue[1], 'answer':curr_clue[2], 'value':curr_clue[3], 'answered':curr_clue[4]})
                if curr_clue[4] == True:
                    gv.room_list[room_id].answer_count += 1
        gv.room_list[room_id].board = board
        
    return jsonify({'board': board})