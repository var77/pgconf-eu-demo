import os
import re
import sys
import json
import psycopg2
from openai import OpenAI
import replicate
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

# OpenAI client
client = OpenAI(api_key=OPENAI_KEY)
MODEL = "gpt-4o-mini"
USE_OPENAI = False

# Establish DB connection
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# SQL queries
INSERT_REPO = """INSERT INTO repos ("name", "description") VALUES (%s, %s) ON CONFLICT ("name") DO NOTHING;"""
INSERT_FOLDER = """INSERT INTO folders ("name", "repo", "description") VALUES (%s, %s, %s) ON CONFLICT ("name") DO NOTHING;"""
INSERT_FILE = """INSERT INTO files ("name", "folder", "description") VALUES (%s, %s, %s) ON CONFLICT ("name") DO NOTHING;"""
INSERT_COMPONENT = """INSERT INTO components ("name", "file", "type", "code", "description") 
                     VALUES (%s, %s, %s, %s, %s) 
                     ON CONFLICT ("name", "file") DO NOTHING;"""

# Database insert functions


def insert_repo(repo_name, repo_description):
    cur.execute(INSERT_REPO, (repo_name, repo_description.strip()))
    conn.commit()


def insert_folder(folder_name, repo_name, folder_description):
    cur.execute(INSERT_FOLDER, (folder_name,
                repo_name, folder_description.strip()))
    conn.commit()


def insert_file(file_name, folder_name, file_content, file_description):
    cur.execute(INSERT_FILE, (file_name, folder_name, file_content,
                file_description.strip()))
    conn.commit()


def insert_component(component_name, file_name, component_type, code, description):
    cur.execute(INSERT_COMPONENT, (component_name, file_name,
                component_type, code, description.strip()))
    conn.commit()

# Asking functions


def ask_replicate(prompt: str) -> str:
    answer = ""
    for event in replicate.stream("meta/meta-llama-3-70b-instruct", input={"prompt": prompt, "max_tokens": 4000}):
        print(event, end="")
        answer += str(event)
    return answer


def ask_openai(prompt: str, type: str = "text") -> str:
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


def ask(prompt: str, type: str = "text", level=0) -> str:
    if level > 3:
        print("Max recursion level reached. Returning empty string.")
        return "[]"
    if USE_OPENAI:
        response = ask_openai(prompt, type)
    else:
        response = ask_replicate(prompt)
    if type == 'json_object':
        try:
            return json.loads(response)
        except Exception as e:
            print(f"Error parsing JSON: {e}")
            return ask(prompt, type, level + 1)
    return response


# Summarization prompts
COMPONENT_PROMPT = """
Here is some code that belongs to a Postgres extension. Return a valid JSON array containing the following schema. Do not include any comments or text other than the JSON array. Try to keep it under 300 words.
{
'name': 'component_name',
'type': 'component_type',
'code': '<the code>',
'description': 'What the component does'
}
"""

FILE_PROMPT = """
Here is some code that belongs to a Postgres extension. Summarize what the code does. Try to keep it under 1000 words.
"""

FILE_SUMMARIES_PROMPT = """
Here are multiple summaries of sections of a file that belongs to a Postgres extension. Summarize what the code does. Try to keep it under 1000 words.
"""

FILE_CHUNK_PROMPT = """
Here is part of the code that belongs to a Postgres extension. Summarize what the code does. Try to keep it under 1000 words.
"""

FOLDER_PROMPT = """
Here are the summaries of the files in this folder, which belongs to a Postgres extension. Summarize what the folder does. Try to keep it under 1000 words.
"""

# Processing files and folders


def chunk_file_by_function(file_content, max_chars=10000):
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

        # If we've reached a size limit, look for the next `}` at the start of a line
        if current_size >= max_chars and re.match(r'^\s*\}', line):
            # Join the current chunk into a string and add it to the list of chunks
            chunks.append("\n".join(current_chunk))
            current_chunk = []
            current_size = 0

    # Add the remaining chunk if any content is left
    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


def process_file(file_path, folder_name):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        file_name = os.path.basename(file_path)
        file_content = f.read()

        # Break the file into chunks, ensuring we don't split in the middle of functions
        chunks = chunk_file_by_function(file_content)

        # Summarize each chunk and combine summaries
        final_summary = ""
        if len(chunks) == 1:
            final_summary = ask(FILE_PROMPT + "\n\nFile: " +
                                file_name + "\n\n" + chunks[0])
            final_components = ask(
                COMPONENT_PROMPT + "\n\nFile: " + file_name +
                "\n\n" + file_content, 'json_object'
            )
            final_components = final_components
        else:
            all_summaries = []
            final_components = []
            for chunk in chunks:
                summary = ask(FILE_CHUNK_PROMPT + chunk)
                all_summaries.append(summary)
                components = ask(
                    COMPONENT_PROMPT + "\n\nPart of file: " + file_name +
                    "\n\n" + chunk, 'json_object'
                )
                components = components
                final_components.extend(components)
            final_summary = ask(FILE_SUMMARIES_PROMPT +
                                "\n\nFile: " + file_name + "\n\n" + "\n".join(all_summaries))

        # Insert the file and its components into the database
        insert_file(file_name, folder_name, file_content, final_summary)
        for component in final_components:
            insert_component(component['name'], file_name, component['type'],
                             component['code'], component['description'])

        return final_summary


def process_folder(folder_path, repo_name):
    # Full relative folder path
    folder_name = os.path.relpath(folder_path, repo_name)
    file_summaries = []

    # Process each file in the folder
    for file in os.listdir(folder_path):
        if file.endswith('.c'):
            file_path = os.path.join(folder_path, file)
            file_summary = process_file(file_path, folder_name)
            file_summaries.append(file_summary)

    # Summarize the folder based on its files
    combined_summary = "\n".join(file_summaries)
    folder_summary = ask(FOLDER_PROMPT + "\n\n" + combined_summary)

    # Insert the folder and its summary into the database
    insert_folder(folder_name, repo_name, folder_summary)

    return folder_summary


def main(repo_path):
    repo_name = os.path.basename(repo_path)

    # Insert the repo as the top-level folder
    repo_summary = ""
    folder_summaries = []

    # Walk through the directory tree
    for root, dirs, files in os.walk(repo_path, topdown=False):
        # Pass repo_path to get relative paths
        folder_summary = process_folder(root, repo_path)
        folder_summaries.append(folder_summary)

    # Combine all folder summaries for the repo summary
    repo_summary = "\n".join(folder_summaries)
    insert_repo(repo_name, repo_summary)

    print(f"\nSummary for the entire repository:\n{repo_summary}")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        print("Usage: python script.py <path_to_repo>")
