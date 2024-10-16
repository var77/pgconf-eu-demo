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
MODEL = "gpt-4o-mini"
CONTEXT_WINDOW = 128000

# Establish DB connection
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# SQL queries
INSERT_FILE = f"""INSERT INTO files ("name", "code", "repo") VALUES (%s, %s, %s, %s) ON CONFLICT ("name", "repo") DO NOTHING;"""

# Database insert functions


def insert_file(file_name, file_content, repo_name):
    cur.execute(INSERT_FILE, (file_name, file_content, repo_name))
    conn.commit()

# Asking functions


def ask(prompt: str, type: str = "text") -> str:
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model=MODEL,
        response_format={"type": type},
    )
    response = chat_completion.choices[0].message.content
    if not response:
        raise Exception("No response from OpenAI")
    if type == 'json_object':
        return json.loads(response)
    return response


# Summarization prompt
FILE_PROMPT = "Here is some code. Summarize what the code does."

# Processing files


def process_file(file_path, repo_name):
    cur.execute(
        """SELECT 1 FROM files WHERE "name" = %s AND "model" = %s AND "repo" = %s;""", (file_path, MODEL, repo_name))
    row = cur.fetchone()
    if row:
        return

    print(file_path)
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        file_content = f.read()
        insert_file(file_path, file_content, repo_name)


valid_endings = ['.rb', '.c', '.cpp', '.rs', '.cc', '.h']


def main(repo_name, repo_path):
    # Walk through the directory tree
    for root, dirs, files in os.walk(repo_path, topdown=False):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            if os.path.isfile(file_path) and os.path.splitext(file_name)[-1] in valid_endings:
                process_file(file_path, repo_name)


if __name__ == '__main__':
    if len(sys.argv) > 2:
        repo_name = sys.argv[1]
        repo_path = sys.argv[2]
        main(repo_name, repo_path)
        cur.close()
        conn.close()
    else:
        print("Usage: python process_repo.py <repo_name> <path_to_repo>")
