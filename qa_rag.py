import os
import psycopg2
import openai
from dotenv import load_dotenv
from psycopg2.extensions import register_adapter, AsIs

# Load environment variables
load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

# OpenAI client
openai.api_key = OPENAI_KEY

# Establish DB connection
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Adapter to convert lists to PostgreSQL arrays


def adapt_array(arr):
    return AsIs("ARRAY[%s]" % ','.join(map(str, arr)))


register_adapter(list, adapt_array)

# Function to generate embeddings using OpenAI's API


def generate_embedding(text):
    response = openai.Embedding.create(
        input=text,
        model="text-embedding-ada-002"
    )
    embedding = response['data'][0]['embedding']
    return embedding

# Functions to process each table and generate embeddings


def process_components():
    select_query = "SELECT name, file, description FROM components WHERE embedding IS NULL"
    cur.execute(select_query)
    components = cur.fetchall()
    for component in components:
        name, file, description = component
        embedding = generate_embedding(description)
        update_query = "UPDATE components SET embedding = %s WHERE name = %s AND file = %s"
        cur.execute(update_query, (embedding, name, file))
        conn.commit()


def process_files():
    select_query = "SELECT name, folder, description FROM files WHERE embedding IS NULL"
    cur.execute(select_query)
    files = cur.fetchall()
    for file in files:
        name, folder, description = file
        embedding = generate_embedding(description)
        update_query = "UPDATE files SET embedding = %s WHERE name = %s AND folder = %s"
        cur.execute(update_query, (embedding, name, folder))
        conn.commit()


def process_folders():
    select_query = "SELECT name, repo, description FROM folders WHERE embedding IS NULL"
    cur.execute(select_query)
    folders = cur.fetchall()
    for folder in folders:
        name, repo, description = folder
        embedding = generate_embedding(description)
        update_query = "UPDATE folders SET embedding = %s WHERE name = %s AND repo = %s"
        cur.execute(update_query, (embedding, name, repo))
        conn.commit()


def process_repos():
    select_query = "SELECT name, description FROM repos WHERE embedding IS NULL"
    cur.execute(select_query)
    repos = cur.fetchall()
    for repo in repos:
        name, description = repo
        embedding = generate_embedding(description)
        update_query = "UPDATE repos SET embedding = %s WHERE name = %s"
        cur.execute(update_query, (embedding, name))
        conn.commit()

# Functions to query the database using vector similarity


def query_components(question_embedding, top_k=5):
    query = "SELECT name, file, type, code, description FROM components ORDER BY embedding <-> %s LIMIT %s"
    cur.execute(query, (question_embedding, top_k))
    results = cur.fetchall()
    return results


def query_files(question_embedding, top_k=5):
    query = "SELECT name, folder, description FROM files ORDER BY embedding <-> %s LIMIT %s"
    cur.execute(query, (question_embedding, top_k))
    results = cur.fetchall()
    return results


def query_folders(question_embedding, top_k=5):
    query = "SELECT name, repo, description FROM folders ORDER BY embedding <-> %s LIMIT %s"
    cur.execute(query, (question_embedding, top_k))
    results = cur.fetchall()
    return results


def query_repos(question_embedding, top_k=5):
    query = "SELECT name, description FROM repos ORDER BY embedding <-> %s LIMIT %s"
    cur.execute(query, (question_embedding, top_k))
    results = cur.fetchall()
    return results

# Function to interact with the LLM and get an answer


def ask(prompt):
    chat_completion = openai.ChatCompletion.create(
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        model="gpt-3.5-turbo",  # or "gpt-4" if you have access
    )
    response = chat_completion.choices[0].message.content
    if not response:
        raise Exception("No response from OpenAI")
    return response

# Main function to process the user's question


def answer_question(question):
    # Generate embedding for the question
    question_embedding = generate_embedding(question)

    # Query the database
    components = query_components(question_embedding)
    files = query_files(question_embedding)
    folders = query_folders(question_embedding)
    repos = query_repos(question_embedding)

    # Build the context
    context = ""

    for repo in repos:
        name, description = repo
        context += f"Repository: {name}\nDescription: {description}\n\n"

    for folder in folders:
        name, repo_name, description = folder
        context += f"Folder: {name}\nRepository: {repo_name}\nDescription: {description}\n\n"

    for file in files:
        name, folder_name, description = file
        context += f"File: {name}\nFolder: {folder_name}\nDescription: {description}\n\n"

    for component in components:
        name, file_name, comp_type, code, description = component
        context += f"Component: {name}\nFile: {file_name}\nType: {comp_type}\nDescription: {description}\n\n"

    # Build the prompt
    prompt = f"Answer the following question based on the provided context.\n\nQuestion: {question}\n\nContext:\n{context}\n"

    # Get the answer from the LLM
    answer = ask(prompt)

    return answer

# Entry point of the script


def main():
    # Process embeddings
    print("Generating embeddings for the data...")
    process_repos()
    process_folders()
    process_files()
    process_components()
    print("Embeddings generated and stored.")

    # Start accepting user queries
    while True:
        question = input("Enter your question (or 'exit' to quit): ")
        if question.lower() == 'exit':
            break
        answer = answer_question(question)
        print("\nAnswer:\n", answer)


if __name__ == "__main__":
    main()
