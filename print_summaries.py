import os
import sys
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()


repo = sys.argv[1]
print("repo:", repo)

# Select folders where zero slash or one slash is present
cur.execute(
    """SELECT "name", "description" FROM folders WHERE "name" NOT LIKE '%%/%%/%%' AND "name" <> '.' AND "repo" = %s;""", (repo,))
rows = cur.fetchall()

for row in rows:
    print('--------------------------')
    print("Folder:", row[0])
    print('----------')
    print(row[1])
    print('--------------------------\n')
