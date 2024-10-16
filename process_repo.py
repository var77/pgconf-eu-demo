import os
import re
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
INSERT_REPO = f"""INSERT INTO repos ("name", "description", "model") VALUES (%s, %s, '{MODEL}') ON CONFLICT ("name", "model") DO NOTHING;"""
INSERT_FOLDER = f"""INSERT INTO folders ("name", "repo", "description", "model") VALUES (%s, %s, %s, '{MODEL}') ON CONFLICT ("name", "repo", "model") DO NOTHING;"""
INSERT_FILE = f"""INSERT INTO files ("name", "folder", "repo", "code", "description", "model") VALUES (%s, %s, %s, %s, %s, '{MODEL}') ON CONFLICT ("name", "folder", "repo", "model") DO NOTHING;"""

# Database insert functions


def insert_repo(repo_name, repo_description):
    cur.execute(INSERT_REPO, (repo_name, repo_description.strip()))
    conn.commit()


def insert_folder(folder_name, repo_name, folder_description):
    cur.execute(INSERT_FOLDER, (folder_name,
                repo_name, folder_description.strip()))
    conn.commit()


def insert_file(file_name, folder_name, repo_name, file_content, description):
    cur.execute(INSERT_FILE, (file_name, folder_name,
                repo_name, file_content, description.strip()))
    conn.commit()

# Asking functions


def ask(prompt: str, type: str = "text") -> str:
    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        model=MODEL,
        response_format={
            "type": type,
        },
    )
    response = chat_completion.choices[0].message.content
    if not response:
        raise Exception("No response from OpenAI")
    if type == 'json_object':
        return json.loads(response)
    return response


# Summarization prompts
FILE_PROMPT = """Here is some code. Summarize what the code does."""
FILE_SUMMARIES_PROMPT = """Here are multiple summaries of sections of a file. Summarize what the code does."""
FOLDER_PROMPT = """Here are the summaries of the files and subfolders in this folder. Summarize what the folder does."""
FOLDER_SUMMARIES_PROMPT = """Here are multiple summaries of the files and subfolders in this folder. Summarize what the folder does."""
REPO_PROMPT = """Here are the summaries of the folders in this repository. Summarize what the repository does."""

# Processing files and folders


def chunk_file(file_content):
    """
    Splits the file content into chunks, ensuring that each chunk ends at a function boundary.
    Specifically, it looks for `}` at the beginning of a line as a natural break point.
    """
    chunks = []
    current_chunk = []
    current_size = 0

    # Split the content into lines for easier processing
    lines = file_content.splitlines()

    for line in lines:
        current_chunk.append(line)
        current_size += len(line)

        # If we've reached a size limit
        if (
            (current_size >= CONTEXT_WINDOW and (
                re.match(r'^\}', line) or re.match(r'^\};', line) or re.match(r'^\];$', line)))
            or (current_size >= 2 * CONTEXT_WINDOW and (re.match(r'^\s{2}\}', line)))
            or (current_size >= 3 * CONTEXT_WINDOW)
        ):
            chunks.append("\n".join(current_chunk))
            current_chunk = []
            current_size = 0

    # Add the remaining chunk if any content is left
    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


def process_file(file_path, folder_name, repo_name):
    file_name = os.path.basename(file_path)

    # If file already has a summary, skip processing and just return it
    cur.execute(
        """SELECT "description" FROM files WHERE "name" = %s AND "folder" = %s AND "repo" = %s AND "model" = %s;""", (file_name, folder_name, repo_name, MODEL))
    row = cur.fetchone()
    if row:
        return row[0]

    print(file_path)
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        file_content = f.read()

        # Break the file into chunks, ensuring we don't split in the middle of functions
        chunks = chunk_file(file_content)

        # Summarize each chunk and combine summaries
        description = ""
        if len(chunks) == 1:
            description = ask(FILE_PROMPT + "\n\nFile: " +
                              file_name + "\n\n" + chunks[0])
        else:
            descriptions = []
            for chunk in chunks:
                descriptions.append(
                    ask(FILE_PROMPT + "\n\nFile: " + file_name + "\n\n" + chunk))
            description = ask(FILE_SUMMARIES_PROMPT + "\n\nFile: " +
                              file_name + "\n\n" + "\n".join(descriptions[:10]))

        # Insert the file and its components into the database
        insert_file(file_name, folder_name, repo_name,
                    file_content, description)

        return description


valid_endings = ['.rb', '.c', '.cpp', '.rs', '.cc', '.h', '.py']


def process_folder(folder_path, repo_path, repo_name):
    # If folder already has a summary, skip processing and just return it
    cur.execute(
        """SELECT "description" FROM folders WHERE "name" = %s AND "repo" = %s AND "model" = %s;""", (folder_path, repo_name, MODEL))
    row = cur.fetchone()
    if row:
        return row[0]

    # Full relative folder path
    folder_name = os.path.relpath(folder_path, repo_path)
    descriptions = []

    # Process each file in the folder
    for item in os.listdir(folder_path):
        item_path = os.path.join(folder_path, item)
        if os.path.isfile(item_path) and os.path.splitext(item)[-1] in valid_endings:
            description = process_file(item_path, folder_name, repo_name)
            descriptions.append(description)
        elif os.path.isdir(item_path):
            # Retrieve the summary of the subfolder from the database
            subfolder_name = os.path.relpath(item_path, repo_path)
            cur.execute(
                """SELECT "description" FROM folders WHERE "name" = %s AND "repo" = %s AND "model" = %s;""", (subfolder_name, repo_name, MODEL))
            subfolder_row = cur.fetchone()
            if subfolder_row and subfolder_row[0]:
                descriptions.append(subfolder_row[0])

    if len(descriptions) == 0:
        return ""

    if len(descriptions) < 300:
        combined_description = ask(
            FOLDER_PROMPT + "\n\n" + "\n".join(descriptions))
    else:
        combined_descriptions = []
        for i in range(0, min(len(descriptions),  90000), 300):
            combined_description = ask(
                FOLDER_PROMPT + "\n\n" + "\n".join(descriptions[i:i+300]))
            combined_descriptions.append(combined_description)
        combined_description = ask(
            FOLDER_SUMMARIES_PROMPT + "\n\n" + "\n".join(combined_descriptions))

    combined_description = combined_description.strip()

    # Insert the folder and its summary into the database
    insert_folder(folder_name, repo_name,  combined_description)

    return combined_description


def main(repo_name, repo_path):
    cur.execute(
        """SELECT "name" FROM repos WHERE "name" = %s AND "model" = %s;""", (repo_name, MODEL))
    row = cur.fetchone()
    if row:
        print(f"Repository '{repo_name}' already processed. Exiting...")
        return

    # Insert the repo as the top-level folder
    repo_summary = ""
    folder_summaries = []

    # Walk through the directory tree
    for root, dirs, files in os.walk(repo_path, topdown=False):
        folder_summary = process_folder(root, repo_path, repo_name)
        if folder_summary:
            folder_summaries.append(folder_summary)

    if len(folder_summaries) == 0:
        print("No valid files found in the repository. Exiting...")
        return

    # Combine all folder summaries for the repo summary
    if len(folder_summaries) < 300:
        repo_summary = ask(REPO_PROMPT + "\n\n" + "\n".join(folder_summaries))
    else:
        combined_folder_summaries = []
        for i in range(0, min(len(folder_summaries), 90000), 300):
            combined_folder_summary = ask(
                REPO_PROMPT + "\n\n" + "\n".join(folder_summaries[i:i+300]))
            combined_folder_summaries.append(combined_folder_summary)
        repo_summary = ask(
            REPO_PROMPT + "\n\n" + "\n".join(combined_folder_summaries))
    insert_repo(repo_name, repo_summary.strip())


if __name__ == '__main__':
    if len(sys.argv) > 1:
        main(sys.argv[1], sys.argv[2])
        cur.close()
        conn.close()
    else:
        print("Usage: python process_repo.py <repo> <path_to_repo>")
