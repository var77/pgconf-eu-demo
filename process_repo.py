import os
import re
import sys
import json
import psycopg2
from openai import OpenAI
from dotenv import load_dotenv

FILE_PROMPT = """Here is some code. Summarize what the code does."""
FILE_SUMMARIES_PROMPT = """Here are multiple summaries of sections of a file. Summarize what the code does."""
FOLDER_PROMPT = """Here are the summaries of the files and subfolders in this folder. Summarize what the folder does."""
FOLDER_SUMMARIES_PROMPT = """Here are multiple summaries of the files and subfolders in this folder. Summarize what the folder does."""
REPO_PROMPT = """Here are the summaries of the folders in this repository. Summarize what the repository does."""
COMMIT_PROMPT = """Here is a commit, including the commit message, and the changes made in the commit. Summarize the commit."""

load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
client = OpenAI(api_key=OPENAI_KEY)
MODEL = "gpt-4o-mini"
CONTEXT_WINDOW = 128000
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()


def is_acceptable_file(file_name):
    return False


def is_acceptable_folder(folder_name):
    return False


def insert_repo(repo_name, repo_description):
    INSERT_REPO = f"""INSERT INTO repos ("name", "description", "model") VALUES (%s, %s, '{MODEL}') ON CONFLICT ("name", "model") DO NOTHING;"""
    cur.execute(INSERT_REPO, (repo_name, repo_description.strip()))
    conn.commit()


def insert_folder(folder_name, repo_name, folder_description):
    INSERT_FOLDER = f"""INSERT INTO folders ("name", "repo", "description", "model") VALUES (%s, %s, %s, '{MODEL}') ON CONFLICT ("name", "repo", "model") DO NOTHING;"""
    cur.execute(INSERT_FOLDER, (folder_name,
                repo_name, folder_description.strip()))
    conn.commit()


def insert_file(file_name, folder_name, repo_name, file_content, description):
    INSERT_FILE = f"""INSERT INTO files ("name", "folder", "repo", "code", "description", "model") VALUES (%s, %s, %s, %s, %s, '{MODEL}') ON CONFLICT ("name", "folder", "repo", "model") DO NOTHING;"""
    cur.execute(INSERT_FILE, (file_name, folder_name,
                repo_name, file_content, description.strip()))
    conn.commit()


def insert_commit(model, repo_name, commit_id, author, date, changes, message, description):
    INSERT_COMMIT = """
        INSERT INTO commits ("model", "repo", "id", "author", "date", "changes", "message", "description")
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT ("model", "repo", "id") DO NOTHING;
    """
    cur.execute(INSERT_COMMIT, (model, repo_name,
                commit_id, author, date, changes, message, description))
    conn.commit()


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
        if os.path.isfile(item_path):
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


def process_commits(repo_path, repo_name):
    # Extract commit data using git log
    os.system(
        f"git -C {repo_path} log -p --pretty=format:'COMMIT_HASH:%H|AUTHOR_NAME:%an|AUTHOR_EMAIL:%ae|DATE:%ad|TITLE:%s|MESSAGE:%b' --date=iso > commit_data.txt"
    )

    # Read commit data from file
    with open('commit_data.txt', 'r') as file:
        lines = file.readlines()

    # Variables to store commit data
    commit_id = author_name = author_email = commit_date = title = message = ""
    changes = ""
    in_diff_section = False

    def maybe_save_commit():
        if commit_id:
            # Concatenate title, description, author, and email into the message field
            author = f"{author_name} <{author_email}>"
            description_input = f"{title}\n{message}\nChanges: {changes}\nAuthor: {author}>\nDate: {commit_date}"
            description = ask(COMMIT_PROMPT + "\n\n" +
                              description_input).strip()
            insert_commit(MODEL, repo_name, commit_id, author, commit_date,
                          changes, message, description)

    # Process each line to extract and insert commit data
    for line in lines:
        line = line.strip()

        if line.startswith("COMMIT_HASH:"):
            maybe_save_commit()

            # Start reading a new commit
            commit_id = line.split("COMMIT_HASH:")[1].strip()
            in_diff_section = False
            changes = ""  # Reset the diff for the next commit

        elif line.startswith("AUTHOR_NAME:"):
            author_name = line.split("AUTHOR_NAME:")[1].strip()
        elif line.startswith("AUTHOR_EMAIL:"):
            author_email = line.split("AUTHOR_EMAIL:")[1].strip()
        elif line.startswith("DATE:"):
            commit_date = line.split("DATE:")[1].strip()
        elif line.startswith("TITLE:"):
            title = line.split("TITLE:")[1].strip()
        elif line.startswith("MESSAGE:"):
            message = line.split("MESSAGE:")[1].strip()
        elif line == "" and commit_id:
            # Empty line indicates the start of the diff section
            in_diff_section = True
        elif in_diff_section:
            # Accumulate the diff (changes)
            changes += line + "\n"

    # Insert the last commit's data
    maybe_save_commit()


def main(repo_name):
    cur.execute(
        """SELECT "name" FROM repos WHERE "name" = %s""", (repo_name,))
    row = cur.fetchone()
    if row:
        print(f"Repository '{repo_name}' already processed. Exiting...")
        return

    # Validate the correct repo path
    repo_path = f"repos/{repo_name}"
    if not os.path.exists(repo_path):
        print(
            f"Repository '{repo_name}' not found at expected path {repo_path}. Exiting...")
        return

    # Process commits
    process_commits(repo_path, repo_name)

    # Walk through the directory tree
    for root, dirs, files in os.walk(repo_path, topdown=False):
        process_folder(root, repo_path, repo_name)
    insert_repo(repo_name)


if __name__ == '__main__':
    if len(sys.argv) == 2:
        main(sys.argv[1])
        cur.close()
        conn.close()
    else:
        print("Usage: python process_repo.py <repo>")
