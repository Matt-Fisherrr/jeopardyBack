import files.global_vars as gv
from threading import Lock

class Room():
    def __init__(self):
        # Basic information
        self.name = ''
        self.room_id = 0

        # Board related information
        self.board = {}
        self.started = 0
        self.screen_clicked = ''
        self.selected_time = None
        self.answer_count = 0
        self.answer_timer = None
        self.thread_answer_timer = Lock()

        # Players
        self.active_player = 0
        self.players = {
            1: {
                'auth0_code': '',
                'score': 0,
                'ping': 0,
                'ready': False
            },
            2: {
                'auth0_code': '',
                'score': 0,
                'ping': 0,
                'ready': False
            },
            3: {
                'auth0_code': '',
                'score': 0,
                'ping': 0,
                'ready': False
            }
        }
        self.player_counts = {
            'count': 0,
            'total_count': 0,
            'ready_count': 0
        }

        #Buzz in related
        self.buzzedIn = 0
        self.buzz_background = None
        self.thread_lock_buzz_background = Lock()
        self.buzzed_in_back = None
        self.thread_lock_buzzed_in_back = Lock()
        self.buzzable_players = []
        self.buzzedPlayerTimes = {
            1: '',
            2: '',
            3: ''
        }

        # Viewers
        self.viewers = []

        def save_new_board(self):
            cur.execute()
