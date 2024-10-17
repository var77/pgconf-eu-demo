import os
import sys
import json
import psycopg2
from pgconf_utils import generate_openai_embedding, generate_ubicloud_embedding
from dotenv import load_dotenv
load_dotenv()

# DB connection
DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# SQL queries to fetch repos, folders, and files missing embeddings
FETCH_FOLDERS = """SELECT "name", "llm_openai", "llm_ubicloud" FROM folders WHERE "vector_openai" IS NULL AND "repo" = %s;"""
FETCH_FILES = """SELECT "name", "folder", "llm_openai", "llm_ubicloud" FROM files WHERE "vector_openai" IS NULL AND "repo" = %s;"""
FETCH_COMMITS = """SELECT "repo", "id", "llm_openai", "llm_ubicloud" FROM commits WHERE "vector_openai" IS NULL AND "repo" = %s;"""

# SQL query to update embedding
UPDATE_EMBEDDING_FOLDER = """UPDATE folders SET vector_openai = %s, vector_ubicloud = %s WHERE "name" = %s AND repo = %s"""
UPDATE_EMBEDDING_FILE = """UPDATE files SET vector_openai = %s, vector_ubicloud = %s WHERE "name" = %s AND folder = %s AND repo = %s;"""
UPDATE_EMBEDDING_COMMIT = """UPDATE commits SET vector_openai = %s, vector_ubicloud = %s WHERE "repo" = %s AND "id" = %s;"""


def backfill_folders(repo: str):
    cur.execute(FETCH_FOLDERS, (repo, ))
    folders = cur.fetchall()
    print(f"Backfilling {len(folders)} folders...")
    for folder in folders:
        name, llm_openai, llm_ubicloud = folder
        if llm_openai:
            vector_ubicloud = generate_ubicloud_embedding(llm_ubicloud)
            vector_openai = generate_openai_embedding(llm_openai)
            cur.execute(UPDATE_EMBEDDING_FOLDER,
                        (json.dumps(vector_openai), json.dumps(vector_ubicloud), name, repo))
            conn.commit()
    print("Backfilling for folders complete.")


def backfill_files(repo: str):
    cur.execute(FETCH_FILES, (repo, ))
    files = cur.fetchall()
    print(f"Backfilling {len(files)} files...")
    for file in files:
        name, folder, llm_openai, llm_ubicloud = file
        if llm_openai:
            vector_ubicloud = generate_ubicloud_embedding(llm_ubicloud)
            vector_openai = generate_openai_embedding(llm_openai)
            cur.execute(UPDATE_EMBEDDING_FILE,
                        (json.dumps(vector_openai), json.dumps(vector_ubicloud), name, folder, repo))
            conn.commit()
    print("Backfilling for files complete.")


def backfill(repo):
    backfill_folders(repo)
    backfill_files(repo)
    print("Backfilling complete.")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python backfill_embeddings.py <repo_name>")
        sys.exit(1)
    repo = sys.argv[1]
    backfill(repo)

    cur.close()
    conn.close()
