import os
import sys
import numpy as np
from pgvector.psycopg2 import register_vector
import psycopg2
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

# OpenAI client
client = OpenAI(api_key=OPENAI_KEY)
MODEL = "gpt-4o-mini"  # You can switch the model if needed
EMBEDDING_MODEL = "text-embedding-3-small"

# Establish DB connection
conn = psycopg2.connect(DATABASE_URL)
register_vector(conn)
cur = conn.cursor()

# SQL queries for fetching files and folders based on vector similarity
FETCH_FILES = """
    SELECT "name", "code", "folder", "description" 
    FROM files 
    WHERE repo = %s AND model = %s
    ORDER BY vector <-> %s
    LIMIT %s
"""

FETCH_FOLDERS = """
    SELECT "name", "description" 
    FROM folders 
    WHERE repo = %s AND model = %s
    ORDER BY vector <-> %s
    LIMIT %s
"""


def ask(prompt: str) -> str:
    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        model=MODEL,
    )
    response = chat_completion.choices[0].message.content
    if not response:
        raise Exception("No response from OpenAI")
    return response


# Function to generate embeddings using OpenAI's API


def generate_embedding(text: str) -> list:
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    embedding = np.array(response.data[0].embedding)
    return embedding

# Function to query files based on vector similarity


def query_files(repo, question_embedding, top_k=5):
    cur.execute(FETCH_FILES, (repo, MODEL, question_embedding, top_k))
    files = cur.fetchall()
    return files

# Function to query folders based on vector similarity


def query_folders(repo, question_embedding, top_k=5):
    cur.execute(FETCH_FOLDERS, (repo, MODEL, question_embedding, top_k))
    folders = cur.fetchall()
    return folders

# Main function to handle user questions


def get_context(question: str, repo: str) -> str:
    # Generate embedding for the question
    question_embedding = generate_embedding(question)

    # Query files and folders based on vector similarity
    files = query_files(repo, question_embedding)
    folders = query_folders(repo, question_embedding)

    # Build context from the query results
    context = ""
    for folder in folders:
        name, description = folder
        context += f"Folder: {name}\nDescription: {description}\n\n"

    for file in files:
        name, code, folder_name, description = file
        context += f"File: {name}\nFolder: {folder_name}\nDescription: {description}\n\n"

    if not context:
        return "No relevant information found to answer your question."

    # Build prompt for the OpenAI API
    prompt = f"Answer the following question based on the provided context.\n\nQuestion: {question}\n\nContext:\n{context}\n"

    # answer = ask(prompt)
    print(prompt)
    return prompt

# Main entry point of the script


def main(repo, question):
    get_context(question.strip(), repo)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python qa_rag.py <repo> <question>")
        sys.exit(1)

    repo_name = sys.argv[1]
    question = sys.argv[2]
    main(repo_name, question)

    # Close database connection
    cur.close()
    conn.close()
