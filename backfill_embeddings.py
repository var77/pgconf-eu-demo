import os
import sys
import json
import psycopg2
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

# OpenAI client
client = OpenAI(api_key=OPENAI_KEY)
LLM_MODEL = "gpt-4o-mini"
EMBEDDING_MODEL = "text-embedding-3-small"
USE_OPENAI = True

# Establish DB connection
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# SQL queries to fetch repos, folders, and files missing embeddings
FETCH_FOLDERS = """SELECT "name", "description" FROM folders WHERE "vector" IS NULL AND "model" = %s AND "repo" = %s;"""
FETCH_FILES = """SELECT "name", "folder", "description" FROM files WHERE "vector" IS NULL AND "model" = %s AND "repo" = %s;"""

# SQL query to update embedding
UPDATE_EMBEDDING_FOLDER = """UPDATE folders SET vector = %s WHERE "name" = %s AND repo = %s;"""
UPDATE_EMBEDDING_FILE = """UPDATE files SET vector = %s WHERE "name" = %s AND folder = %s AND repo = %s;"""

# Function to generate embeddings using OpenAI


def generate_embedding(text: str) -> list:
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    embedding = response.data[0].embedding
    return embedding


# Function to backfill embeddings for folders


def backfill_folders(repo: str):
    cur.execute(FETCH_FOLDERS, (LLM_MODEL, repo))
    folders = cur.fetchall()
    print(f"Backfilling {len(folders)} folders...")
    for folder in folders:
        name, description = folder
        if description:
            embedding = generate_embedding(description)
            cur.execute(UPDATE_EMBEDDING_FOLDER,
                        (json.dumps(embedding), name, repo))
            conn.commit()
    print("Backfilling for folders complete.")

# Function to backfill embeddings for files


def backfill_files(repo: str):
    cur.execute(FETCH_FILES, (LLM_MODEL, repo))
    files = cur.fetchall()
    print(f"Backfilling {len(files)} files...")
    for file in files:
        name, folder, description = file
        if description:
            embedding = generate_embedding(description)
            cur.execute(UPDATE_EMBEDDING_FILE,
                        (json.dumps(embedding), name, folder, repo))
            conn.commit()
    print("Backfilling for files complete.")


def main():
    # Backfill embeddings for repos, folders, and files
    repo = sys.argv[1]
    backfill_folders(repo)
    backfill_files(repo)
    print("Backfilling complete.")


if __name__ == '__main__':
    main()

    # Close DB connection
    cur.close()
    conn.close()
