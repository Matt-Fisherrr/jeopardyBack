from flask import Flask, render_template, send_from_directory, current_app as app

@app.route('/')
def index():
    return "<a href='https://Jeopardy.MattFisher.ca'>Jeopardy</a>"

# def index(path):
#     if path == 'favicon.ico':
#         return send_from_directory('build/',path)
#     return render_template('index.html')