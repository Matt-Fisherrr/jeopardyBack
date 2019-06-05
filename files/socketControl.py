from threading import Lock
from flask_socketio import SocketIO, Namespace, emit, join_room, leave_room, close_room, rooms, disconnect


ping_list = {}

thread = None
thread_lock = Lock()
class jeopardy_socket(Namespace):

    def ping_check():
        global room_list, ping_list, socketio
        ping_count = 0
        while True:
            socketio.sleep(10)
            ping_list[ping_count] = datetime.datetime.now()
            emit('ping_check', {'ping_num':ping_count}, room='players')
            ping_count = ping_count + 1

    def buzzIn(room_id):
        socketio.sleep(3)
        emit('buzzable', {'buzz':True, 'buzzable_players':room_list[room_id]['buzzable_players']}, room=str(room_id))

    def buzzBackground(args):
        global room_list
        room_id = args['room_id']
        catclue = args['screen_clicked']
        socketio.sleep(7)
        if room_list[room_id]['buzzedIn'] == 0:
            category, clue = catclue.split('|')
            clue = int(clue)
            room_list[room_id]['answer_count'] = room_list[room_id].get('answer_count', 0) + 1
            if room_list[room_id].get('answer_count', 0) >= 5:
                calculate_winner(room_id)
            emit('no_buzz', { 'screen_clicked':catclue}, room=str(room_id))
            emit('no_correct_answer', { 'position':room_list[room_id]['active_player'], 'answer': room_list[room_id]['board'][category][clue]['answer']}, room=str(room_id))

    def buzz_in_background(room_id):
        global room_list
        if len(room_list[room_id]['buzzable_players']) > 1:
            socketio.sleep(2)
        lowest_time = 99999999999999999
        lowest_player = ''
        for player in room_list[room_id]['buzzedPlayerTimes']:
            if room_list[room_id]['buzzedPlayerTimes'][player] != '':
                if room_list[room_id]['buzzedPlayerTimes'][player] < lowest_time:
                    lowest_time = room_list[room_id]['buzzedPlayerTimes'][player]
                    lowest_player = player
        room_list[room_id]['buzzedIn'] = lowest_player
        del room_list[room_id]['buzzable_players'][room_list[room_id]['buzzable_players'].index(lowest_player)]
        emit('fastest_buzz', {'buzzedIn':room_list[room_id]['buzzedIn']}, room=str(room_id))
        thread_answer_timer = Lock()
        room_list[room_id]['answer_timer'] = None
        with thread_answer_timer:
            if room_list[room_id]['answer_timer'] == None:
                room_list[room_id]['answer_timer'] = socketio.start_background_task(answer_timer,room_id)

    def answer_timer(room_id):
        global room_list
        pos = room_list[room_id]['buzzedIn']
        question = room_list[room_id]['screen_clicked']
        socketio.sleep(7)
        if room_list[room_id]['buzzedIn'] == pos and question == room_list[room_id]['screen_clicked']:
            emit('take_too_long', {}, room=str(room_id))

    def calculate_winner(room_id):
        global room_list
        highest_score = -99999999999
        highest_player = ''
        for player in room_list[room_id]['players']:
            if player == 'one' or player == 'two' or player == 'three':
                if room_list[room_id]['players'][player]['username'] != '':
                    if room_list[room_id]['players'][player]['score'] > highest_score:
                        highest_score = room_list[room_id]['players'][player]['score']
                        highest_player = room_list[room_id]['players'][player]['username']
                    elif room_list[room_id]['players'][player]['score'] == highest_score:
                        highest_player = [highest_player, room_list[room_id]['players'][player]['username']]
        emit('winner', {'username':highest_player}, room=str(room_id))


    def on_pong_res(self, message):
        global room_list, ping_list, req_ids
        pos = req_ids[request.sid]['player_num']
        diff = datetime.datetime.now() - ping_list[message['ping_num']]
        ping = round((diff.microseconds / 10**6 + diff.seconds) * 1000)
        room_list[req_ids[request.sid]['room_id']]['players'][pos].get('ping',[]).append(ping) 

    def on_connect(self):
        global thread
        with thread_lock:
            if thread is None:
                thread = socketio.start_background_task(ping_check)

    def on_disconnect(self):
        global room_list, req_ids, connected_users
        room_id = req_ids[request.sid]['room_id']
        username = req_ids[request.sid]['username'][0]
        print(req_ids[request.sid]['username'][0] + ' disconnected from room ' + str(room_id))
        if req_ids[request.sid].get('player_num', 0) != 0:
            room_list[room_id]['players']['count'] = room_list[room_id]['players']['count'] - 1
        if username in room_list[room_id]['viewers']:
            del room_list[room_id]['viewers'][room_list[room_id]['viewers'].index(username)]
        if room_list[room_id]['players']['count'] == 0 and len(room_list[room_id]['viewers']) == 0:
            print('closed room ' + str(room_id))
            del room_list[room_id]
        del connected_users[req_ids[request.sid]['access_token']]
        del req_ids[request.sid]

    def on_join_room(self,message):
        try:
            global room_list, connected_users, req_ids


            room_id = message['room_id']
            access_token = message['access_token']
            req_ids[request.sid] = connected_users[access_token]

            join_room(str(room_id))

            room_list[room_id]['viewers'].append(req_ids[request.sid]['username'][0])
            req_ids[request.sid]['sid'] = request.sid
            req_ids[request.sid]['room_id'] = room_id

            cur.execute("SELECT player_id FROM players WHERE auth0_code = %s",(req_ids[request.sid]['auth0_code'],))
            req_ids[request.sid]['player_id'] = cur.fetchone()[0]

            if room_list[room_id].get('started', False,) == False:
                room_list[room_id]['active_player'] = 0
            if room_list[room_id].get('players',None) == None:
                room_list[room_id]['players'] = room_list[room_id].get('players',{})
            room_list[room_id]['players']['one'] = room_list[room_id]['players'].get('one',{})
            room_list[room_id]['players']['two'] = room_list[room_id]['players'].get('two',{})
            room_list[room_id]['players']['three'] = room_list[room_id]['players'].get('three',{})
            if room_list[room_id].get('init', None) == None:
                for pos in room_list[room_id]['players']:
                    if pos == 'one' or pos == 'two' or pos == 'three':
                        room_list[req_ids[request.sid]['room_id']]['players'][pos]['ping'] = []
                        cur.execute("SELECT username FROM players WHERE auth0_code = %s",(room_list[room_id]['players'][pos].get('auth0_code','0'),))
                        try:
                            room_list[room_id]['players'][pos]['username'] = cur.fetchone()[0]
                            room_list[room_id]['players'][pos]['score'] = 0
                        except:
                            room_list[room_id]['players'][pos]['username'] = ""
                            room_list[room_id]['players'][pos]['score'] = 0
                room_list[room_id]['init'] = True
            room = json.loads(json.dumps(room_list[room_id]))
            for pos in room['players']:
                if pos == 'one' or pos == 'two' or pos == 'three':
                    if room['players'][pos].get('auth0_code', None) != None:
                        del room['players'][pos]['auth0_code']
                        if room_list[room_id]['players'][pos]['auth0_code'] == req_ids[request.sid]['auth0_code']:
                            req_ids[request.sid]['player_num'] = pos
                            room_list[room_id]['viewers'].remove(req_ids[request.sid]['username'][0])
                            room_list[room_id]['players']['count'] = room_list[room_id]['players']['count'] + 1
                            join_room('players')
            emit('has_joined_room', { 
                'players':{ 
                    'one':room['players']['one'],
                    'two':room['players']['two'],
                    'three':room['players']['three'] 
                }, 
                'position':req_ids[request.sid].get('player_num',0), 
                'player_id':req_ids[request.sid]['player_id'],
                'started': room['started'],
                'active_player':room['active_player']
                }
            )
        except Exception as e:
            print(e)
            emit('error')

    def on_viewer_joined(self):
        global req_ids, room_list
        room_id = req_ids[request.sid]['room_id']
        emit('viewer_added', { 'viewers':len(room_list[room_id]['viewers'])}, room=str(room_id))

    def on_player_select(self,message):
        global room_list, connected_users ,req_ids

        position = message['position']
        room_id = req_ids[request.sid]['room_id']
        auth0_code = req_ids[request.sid]['auth0_code']
        
        if req_ids[request.sid].get('player_num',None) == None:
            if room_list[room_id]['players'][position]['username'] == "" and room_list[room_id].get('started', False) == False:
                room_list[room_id]['viewers'].remove(req_ids[request.sid]['username'][0])
                join_room('players')
                room_list[room_id]['players'][position]['auth0_code'] = auth0_code
                cur.execute("SELECT username FROM players WHERE auth0_code = %s",(room_list[room_id]['players'][position].get('auth0_code','0'),))
                room_list[room_id]['players'][position]['username'] = cur.fetchone()[0]
                req_ids[request.sid]['player_num'] = position
                room_list[room_id]['players']['count'] = room_list[room_id]['players'].get('count',0) + 1
                room_list[room_id]['players']['total_count'] = room_list[room_id]['players'].get('total_count',0) + 1
                emit('player_selected',{'username':req_ids[request.sid]['username'],'position':position, 'player_id':req_ids[request.sid]['player_id']}, room=str(room_id))

    def on_player_ready(self, message):
        global room_list, req_ids
        room_id = req_ids[request.sid]['room_id']
        pos = req_ids[request.sid]['player_num']
        if room_list[room_id]['players'][pos].get('ready',False) == False:
            room_list[room_id]['players'][pos]['ready'] = True
            room_list[room_id]['players']['ready_count'] = room_list[room_id]['players'].get('ready_count', 0) + 1
        else:
            room_list[room_id]['players'][pos]['ready'] = False
            room_list[room_id]['players']['ready_count'] = room_list[room_id]['players']['ready_count'] - 1
        if room_list[room_id]['players'].get('ready_count', 0) == room_list[room_id]['players']['count']:
            room_list[room_id]['started'] = 1
            room_list[room_id]['active_player'] = 1
            emit('ready_player', { 'position':pos,'ready':room_list[room_id]['players'][pos]['ready'], 'started': room_list[room_id]['started'], 'active_player': room_list[room_id]['active_player']}, room=str(room_id))
        else:
            emit('ready_player', { 'position':pos,'ready':room_list[room_id]['players'][pos]['ready'], 'started': room_list[room_id]['started']}, room=str(room_id))

    def on_screen_select(self, message):
        global room_list, req_ids
        room_id = req_ids[request.sid]['room_id']
        screen_clicked = message['screen_clicked']
        if req_ids[request.sid]['player_num'] == room_list[room_id]['active_player']:
            room_list[room_id]['screen_clicked'] = screen_clicked
            category, clue = room_list[room_id]['screen_clicked'].split('|')
            clue = int(clue)
            if room_list[room_id]['board'][re.sub(r'[^A-Za-z]','',category)][clue]['answered'] == False:
                room_list[room_id]['board'][re.sub(r'[^A-Za-z]','',category)][clue]['answered'] = True
                room_list[room_id]['buzzable_players'] = []
                for pos in room_list[room_id]['players']:
                    if pos == 'one' or pos == 'two' or pos == 'three':
                        if room_list[room_id]['players'][pos]['username'] != '':
                            room_list[room_id]['buzzable_players'].append(pos)
                room_list[room_id]['selected_board'] = room_list[room_id]['screen_clicked']
                room_list[room_id]['buzzedPlayerTimes'] = {'one':'','two':'','three':''}
                emit('screen_selected', { 'category':category, 'clue':clue, 'screen_text': room_list[room_id]['board'][category][clue]['question'], 'active_player':0, 'x_and_y':message['x_and_y']}, room=str(room_id))
                thread_lock_back = Lock()
                with thread_lock_back:
                    socketio.start_background_task(buzzIn,room_id)
                    room_list[room_id]['buzzed_in_back'] = None
                    room_list[room_id]['buzz_background'] = None
                    room_list[room_id]['buzzedIn'] = 0
                    room_list[room_id]['selected_time'] = datetime.datetime.now()
                    room_list[room_id]['buzz_background'] = socketio.start_background_task(buzzBackground,{'room_id':room_id, 'screen_clicked':room_list[room_id]['screen_clicked']})

    def on_buzz_in(self):
        global room_list, req_ids
        room_id = req_ids[request.sid]['room_id']
        pos = req_ids[request.sid]['player_num']

        if pos in room_list[room_id]['buzzable_players']:
            room_list[room_id]['buzzedIn'] = pos
            now = room_list[room_id]['selected_time']
            diff = (datetime.datetime.now() - now)
            diff = round((diff.microseconds / 10**6 + diff.seconds) * 1000)
            try:
                room_list[room_id]['buzzedPlayerTimes'][pos] = diff - (sum(room_list[room_id]['players'][pos].get('ping',[])) / len(room_list[room_id]['players'][pos].get('ping',[])))
            except:
                room_list[room_id]['buzzedPlayerTimes'][pos] = diff

            with thread_lock_buzz:
                if room_list[room_id]['buzzed_in_back'] == None:
                    room_list[room_id]['buzzed_in_back'] = socketio.start_background_task(buzz_in_background,room_id)

    def on_answer_typed(self, message):
        global room_list, req_ids
        room_id = req_ids[request.sid]['room_id']
        if req_ids[request.sid]['player_num'] == room_list[room_id]['buzzedIn']:
            emit('typed_answer', {'answer_input':message['answer']}, room=str(room_id))

    def on_answer_submit(self, message):
        global room_list, req_ids
        room_id = req_ids[request.sid]['room_id']
        answer = message['answer']
        pos = req_ids[request.sid]['player_num']
        if room_list[room_id]['buzzedIn'] == req_ids[request.sid]['player_num']:
            room_list[room_id]['buzzedIn'] = 0
            category, clue = room_list[room_id]['selected_board'].split('|')
            clue = int(clue)
            real_answer = re.sub(r'<.+?>','',room_list[room_id]['board'][category][clue]['answer'])
            real_answer = re.sub(r'(?<=\b)(the|a|an)\s?(?=\b)','',real_answer)
            # match = re.search(re.sub(r'[^A-Za-z0-9\s]','',answer.lower()),re.sub(r'[^A-Za-z0-9\s]','',real_answer.lower()))
            # if match != None:
            #     match = match.group()
            # else:
            #     match = ''

            ratio = fuzz.ratio(re.sub(r'[^A-Za-z0-9\s]','',answer.lower()), re.sub(r'[^A-Za-z0-9\s]','',real_answer.lower()))
            token_sort = fuzz.token_sort_ratio(re.sub(r'[^A-Za-z0-9\s]','',answer.lower()), re.sub(r'[^A-Za-z0-9\s]','',real_answer.lower()))
            token_set = fuzz.token_set_ratio(re.sub(r'[^A-Za-z0-9\s]','',answer.lower()), re.sub(r'[^A-Za-z0-9\s]','',real_answer.lower()))

            print_answer = re.sub(r'[^A-Za-z0-9\s]','',answer.lower())
            pint_real_answer = re.sub(r'[^A-Za-z0-9\s]','',real_answer.lower())
            
            # print(fuzz.ratio(re.sub(r'[^A-Za-z0-9\s]','',match), re.sub(r'[^A-Za-z0-9\s]','',real_answer)))
            # print(fuzz.partial_ratio(re.sub(r'[^A-Za-z0-9\s]','',answer.lower()), re.sub(r'[^A-Za-z0-9\s]','',real_answer.lower())))
            # print(fuzz.token_sort_ratio(re.sub(r'[^A-Za-z0-9\s]','',match), re.sub(r'[^A-Za-z0-9\s]','',real_answer)))
            # print(fuzz.token_set_ratio(re.sub(r'[^A-Za-z0-9\s]','',match), re.sub(r'[^A-Za-z0-9\s]','',real_answer)))
            print(f"{print_answer} | {pint_real_answer} | ratio: {ratio}%, sort: {token_sort}%, set: {token_set}% = {(ratio + token_sort + token_set) // 3}")
            # print(len(re.sub(r'[^A-Za-z0-9\s]','',match)) / len(re.sub(r'[^A-Za-z0-9\s]','',real_answer)) * 100)
            if (ratio + token_sort + token_set) // 3 > 50 and (ratio == 100 or token_sort == 100 or token_set == 100) :
                print('correct')
                room_list[room_id]['answer_count'] = room_list[room_id].get('answer_count', 0) + 1
                if room_list[room_id].get('answer_count', 0) >= 5:
                    calculate_winner(room_id)
                room_list[room_id]['players'][pos]['score'] = room_list[room_id]['players'][pos]['score'] + room_list[room_id]['board'][category][clue]['value']
                room_list[room_id]['active_player'] = pos
                emit('answer_response', { 'correct':True, 'position': pos, 'new_score': room_list[room_id]['players'][pos]['score'] }, room=str(room_id))
            else:
                print('wrong')
                room_list[room_id]['players'][pos]['score'] = room_list[room_id]['players'][pos]['score'] - room_list[room_id]['board'][category][clue]['value']
                emit('answer_response', { 'correct':False, 'position': pos, 'new_score':room_list[room_id]['players'][pos]['score'], 'buzzable_players':room_list[room_id]['buzzable_players'] }, room=str(room_id))
                if len(room_list[room_id]['buzzable_players']) == 0:
                    room_list[room_id]['answer_count'] = room_list[room_id].get('answer_count', 0) + 1
                    if room_list[room_id].get('answer_count', 0) >= 5:
                        calculate_winner(room_id)
                    emit('no_buzz', { 'screen_clicked':room_list[room_id]['screen_clicked'] }, room=str(room_id))
                    emit('no_correct_answer', { 'position':room_list[room_id]['active_player'], 'answer': room_list[room_id]['board'][category][clue]['answer']}, room=str(room_id))
                else:
                    room_list[room_id]['buzzedPlayerTimes'] = {'one':'','two':'','three':''}
                    thread_lock_back = Lock()
                    with thread_lock_back:
                        socketio.start_background_task(buzzIn,room_id)
                        room_list[room_id]['buzzed_in_back'] = None
                        room_list[room_id]['buzz_background'] = None
                        room_list[room_id]['buzzedIn'] = 0
                        room_list[room_id]['selected_time'] = datetime.datetime.now()
                        room_list[room_id]['buzz_background'] = socketio.start_background_task(buzzBackground,{'room_id':room_id, 'screen_clicked':room_list[room_id]['screen_clicked']})



    def on_test(self, message):
        print(message['data'])
        emit('test', {'test':'test'})
        