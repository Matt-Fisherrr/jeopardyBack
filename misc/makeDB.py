import psycopg2
import os

conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()

cur.execute("DROP TABLE IF EXISTS players")

cur.execute("""CREATE TABLE players(
  player_id SERIAL PRIMARY KEY,
  username TEXT NOT NULL,
  auth0_code TEXT NOT NULL
);""")

cur.execute("DROP TABLE IF EXISTS rooms")

cur.execute("""CREATE TABLE rooms(
  room_id SERIAL PRIMARY KEY,
  room_name TEXT NOT NULL,
  room_owner TEXT NOT NULL,
  player1 TEXT,
  player1score INT,
  player2 TEXT,
  player2score INT,
  player3 TEXT,
  player3score INT,
  board_id INT,
  started INT NOT NULL,
  complete INT NOT NULL,
  activate_player INT NOT NULL
);""")

cur.execute("DROP TABLE IF EXISTS boards")

cur.execute("""CREATE TABLE boards(
  board_id SERIAL PRIMARY KEY,
  cat_one INT NOT NULL,
  cat_two INT NOT NULL,
  cat_three INT NOT NULL,
  cat_four INT NOT NULL,
  cat_five INT NOT NULL
);""")

cur.execute("DROP TABLE IF EXISTS categories")

cur.execute("""CREATE TABLE categories(
  cat_id SERIAL PRIMARY KEY,
  cat_name TEXT NOT NULL,
  clue_one INT NOT NULL,
  clue_two INT NOT NULL,
  clue_three INT NOT NULL,
  clue_four INT NOT NULL,
  clue_five INT NOT NULL
);""")

cur.execute("DROP TABLE IF EXISTS clues")

cur.execute("""CREATE TABLE clues(
  clue_id SERIAL PRIMARY KEY,
  api_id INT NOT NULL,
  question TEXT NOT NULL,
  answer TEXT NOT NULL,
  value INT NOT NULL,
  answered BOOLEAN NOT NULL
)""")


conn.commit()

cur.close()
conn.close()