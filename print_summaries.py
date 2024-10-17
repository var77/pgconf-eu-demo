import os
import sys
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
MODEL = "gpt-4o-mini"

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()
column = "llm_openai"
# column = "llm_ubicloud"

repo = sys.argv[1]
print("repo:", repo)

cur.execute(
    f"""SELECT "name", {column} FROM folders WHERE "name" NOT LIKE '%%/%%/%%' AND "name" <> '.' AND "repo" = %s;""", (repo,))
rows = cur.fetchall()

for row in rows:
    print('--------------------------')
    print("Folder:", row[0])
    print('----------')
    print(row[1])
    print('--------------------------\n')

if len(rows) == 0:
    cur.execute(
        f"""SELECT "name", {column}, "folder" FROM files WHERE "repo" = %s;""", (repo,))
    rows = cur.fetchall()

    for row in rows:
        print('--------------------------')
        print("Folder:", row[2], "File:", row[0])
        print('----------')
        print(row[1])
        print('--------------------------\n')
