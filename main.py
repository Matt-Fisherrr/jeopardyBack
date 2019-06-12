from flask import Flask
from flask_socketio import SocketIO
import psycopg2, os

app = Flask(__name__, static_folder="build/static", template_folder="build")
app.secret_key = 'app secret key'
socketio = SocketIO(app, async_mode='eventlet')

with app.app_context():
    from files.auth import Auth
    from files.global_vars import global_variables
    global_vars = global_variables()
    import files.routes
    from files.socketControl import jeopardy_socket



if __name__ == '__main__':
    socketio.run(app, debug=True, host= '0.0.0.0')
    # , host= '0.0.0.0'














#old imports

# from flask import Flask, request, jsonify, render_template, send_from_directory
# from flask_cors import cross_origin, CORS
# from flask_socketio import SocketIO, Namespace, emit, join_room, leave_room, close_room, rooms, disconnect
# from threading import Lock
# from jose import jwt


# from fuzzywuzzy import fuzz
# import json, os, hashlib, requests, random, datetime, copy, re, psycopg2