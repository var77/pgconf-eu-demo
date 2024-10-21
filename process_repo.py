import os
import time
import re
import sys
import json
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
LLM_BATCH_SIZE = os.getenv('LLM_BATCH_SIZE', 150) # Adjust based on OpenAI tier limits
DATABASE_URL = os.getenv('DATABASE_URL')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# SQL queries
INSERT_FILE = f"""INSERT INTO files ("name", "code", "repo") VALUES (%s, %s, %s) ON CONFLICT ("name", "repo") DO NOTHING;"""
ASK_FUNCTION_SQL = '''
CREATE OR REPLACE FUNCTION ask(user_query TEXT, repo_name TEXT default 'citus')
RETURNS TEXT AS $$
DECLARE
    context TEXT;
BEGIN
    -- Concatenate the descriptions from the subquery into a single string
    WITH context_cte AS (
        SELECT STRING_AGG(description, ' ') AS combined_description
        FROM (
            SELECT description
            FROM files
            WHERE repo=repo_name
            ORDER BY vector <=> openai_embedding('text-embedding-3-small', user_query)
            LIMIT 3
        ) subquery
    )
    SELECT 'Answer user questions using the following context: ' || combined_description
    INTO context
    FROM context_cte;

    -- Return the result of the openai_completion function
    RETURN llm_completion(user_query, 'gpt-4o-mini', context);
END;
$$ LANGUAGE plpgsql;
'''

# Database insert functions


def insert_file(cur, file_name, file_content,  repo_name):
    cur.execute(INSERT_FILE, (file_name, file_content,
                repo_name))

# Processing files
def process_file(cur, file_path, repo_name):
    file_name = os.path.basename(file_path)

    print(file_path)
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        file_content = f.read()
        insert_file(cur, file_name, file_content, repo_name)


valid_endings = ['.rb', '.c', '.cpp', '.rs', '.cc', '.h']

def process_files(cur, repo_name, repo_path):
    for root, dirs, files in os.walk(repo_path, topdown=False):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            if os.path.isfile(file_path) and os.path.splitext(file_name)[-1] in valid_endings:
                process_file(cur, file_path, repo_name)

def main(repo_name, repo_path):
    # Check environment variables
    if not DATABASE_URL:
        raise EnvironmentError("Please set the DATABASE_URL environment variable")

    if not OPENAI_API_KEY:
        raise EnvironmentError("Please set the OPENAI_API_KEY environment variable")

    # Establish DB connection
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True  # Enable auto commit to immediately execute commands
    cursor = conn.cursor()

    cursor.execute('CREATE TABLE IF NOT EXISTS files(id serial PRIMARY KEY, name text, code text, folder text, repo text);')
    cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS name_repo_idx ON files (name, repo);')

    process_files(cursor, repo_name, repo_path)
    
    cursor.execute('ALTER SYSTEM SET lantern_extras.enable_daemon=true;')
    cursor.execute(f"ALTER DATABASE postgres SET lantern_extras.llm_token='{OPENAI_API_KEY}';")
    cursor.execute('SELECT pg_reload_conf();')

    cursor.execute(f"SELECT add_completion_job('files', 'code', 'description', 'Summarize this code', 'TEXT', 'openai/gpt-4o-mini', {LLM_BATCH_SIZE});")

    # Monitor progress of the completion job
    while True:
        time.sleep(10)
        cursor.execute('SELECT progress FROM get_completion_jobs() LIMIT 1;')
        progress = cursor.fetchone()[0]
        print(f"Completion Job Progress is {progress}%")
        if progress == 100:
            break

    cursor.execute("SELECT add_embedding_job('files', 'description', 'vector', 'text-embedding-3-small', 'openai');")

    # Monitor progress of the embedding job
    while True:
        time.sleep(10)
        cursor.execute('SELECT progress FROM get_embedding_jobs() LIMIT 1;')
        progress = cursor.fetchone()[0]
        print(f"Embedding Job Progress is {progress}%")
        if progress == 100:
            break
        
    cursor.execute(ASK_FUNCTION_SQL)

    cursor.close()
    conn.close()
    
    print("Setup completed successfully!")
    print("Use: 'python ask_repo.py <repo> <question>' to ask questions")

if __name__ == '__main__':
    if len(sys.argv) > 2:
        repo_name = sys.argv[1]
        repo_path = sys.argv[2]
        main(repo_name, repo_path)
    else:
        print("Usage: python process_repo.py <repo_name> <path_to_repo>")
