import os
import sys
import numpy as np
from pgvector.psycopg2 import register_vector
import psycopg2
from dotenv import load_dotenv
from pgconf_utils import generate_openai_embedding, generate_ubicloud_embedding, ask_openai, ask_ubicloud

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL)
register_vector(conn)
cur = conn.cursor()


def query_files(provider, repo, vector, top_k=5):
    FETCH_FILES = f"""
        SELECT "name", "code", "folder", llm_{provider}
        FROM files 
        WHERE repo = %s
        ORDER BY vector_{provider} <-> %s
        LIMIT %s
    """
    if type(vector) == list:
        vector = np.array(vector)
    cur.execute(FETCH_FILES, (repo, vector, top_k))
    files = cur.fetchall()
    return files

# Function to query folders based on vector similarity


def query_folders(provider, repo, vector, top_k=5):
    FETCH_FOLDERS = f"""
        SELECT "name", llm_{provider}
        FROM folders 
        WHERE repo = %s
        ORDER BY vector_{provider} <-> %s
        LIMIT %s
    """
    if type(vector) == list:
        vector = np.array(vector)
    cur.execute(FETCH_FOLDERS, (repo, vector, top_k))
    folders = cur.fetchall()
    return folders


def get_prompt(provider: str, repo: str, question: str, context_types=[]) -> str:
    if provider not in ["openai", "ubicloud"]:
        raise ValueError("Invalid provider. Must be 'openai' or 'ubicloud'.")

    vector = generate_openai_embedding(
        question) if provider == "openai" else generate_ubicloud_embedding(question)
    folders = query_folders(provider, repo, vector)
    files = query_files(provider, repo, vector)

    context = ""

    if len(context_types) == 0 or "folders" in context_types:
        for folder in folders:
            name, description = folder
            context += f"Folder: {name}\nDescription: {description}\n\n"

    if len(context_types) == 0 or "files" in context_types:
        for file in files:
            name, code, folder_name, description = file
            context += f"File: {name}\nFolder: {folder_name}\nDescription: {description}\n\n"

    if not context:
        return "No relevant information found to answer your question."

    prompt = f"Answer the following question based on the provided context.\n\nQuestion: {question}\n\nContext:\n{context}\n"
    return prompt


def ask_with_context(provider: str, repo: str, question: str, context_types=[]) -> str:
    if provider not in ["openai", "ubicloud"]:
        raise ValueError("Invalid provider. Must be 'openai' or 'ubicloud'.")

    prompt = get_prompt(provider, repo, question, context_types)
    ask = ask_openai if provider == "openai" else ask_ubicloud
    answer = ask(prompt)
    return answer


if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Usage: python qa_rag.py <provider> <repo> <question>")
        sys.exit(1)

    provider = sys.argv[1]
    repo_name = sys.argv[2]
    question = sys.argv[3]
    prompt = get_prompt(provider, repo_name, question)
    print(prompt)

    answer = ask_with_context(provider, repo_name, question)
    print("Answer:")
    print(answer)

    # Close database connection
    cur.close()
    conn.close()
