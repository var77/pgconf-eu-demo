import os
import sys
from pgvector.psycopg2 import register_vector
import psycopg2
from dotenv import load_dotenv

load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
COMPLETION_MODEL = "gpt-4o-mini"
EMBEDDING_MODEL = "text-embedding-3-small"

conn = psycopg2.connect(DATABASE_URL)
register_vector(conn)
cur = conn.cursor()


def query_files(repo, question, top_k=5):
    query = """
        SELECT "name", "code", "description" 
        FROM files 
        WHERE repo = %s
        ORDER BY vector <-> openai_embedding(%s, %s)
        LIMIT %s
    """
    cur.execute(query, (repo, EMBEDDING_MODEL, question, top_k))
    files = cur.fetchall()
    return files


def ask(question, context) -> str:
    query = """
        SELECT openai_completion(%s, %s, %s)
    """
    cur.execute(query, (question, COMPLETION_MODEL, context))


def main(repo: str, question: str) -> str:
    print("QUESTION")
    print(question)

    files = query_files(repo, question)

    print("\RELEVANT FILES")
    for file in files:
        name, code, description = file
        print('-', name)
        context += f"File: {name}\nDescription: {description}\n\n"
    if not context:
        return "No relevant information found to answer your question."

    context = f"Answer user questions using the following context.\n\nContext:\n{context}\n"
    answer = ask(question, context)
    print("\nANSWER")
    print(answer)


if len(sys.argv) != 3:
    print("Usage: python qa_rag.py <repo> <question>")
    sys.exit(1)

repo_name = sys.argv[1]
question = sys.argv[2]
main(repo_name, question)

# Close database connection
cur.close()
conn.close()
