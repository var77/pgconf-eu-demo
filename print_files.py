import os
import sys
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
MODEL = "gpt-4o-mini"

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()


def list_nested_files(repo, folders):
    for folder in folders:
        # Query for the folder and its nested files
        cur.execute(
            """SELECT f."name", f."description", f."folder"
               FROM files f
               INNER JOIN folders fo ON f."folder" = fo."name"
               WHERE fo."repo" = %s AND fo."name" LIKE %s || '%%' AND f."model" = %s;""",
            (repo, folder, MODEL))
        rows = cur.fetchall()

        if rows:
            print(f"\nListing files for folder: {folder}")
            print("--------------------------")
            for row in rows:
                folder_name = row[2]
                file_name = row[0]
                file_description = row[1]

                print(f"Folder: {folder_name} - File: {file_name}")
                print(f"Description: {file_description}")
                print('--------------------------\n')
        else:
            print(f"No files found in the folder: {folder}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: print_files.py <repo> <folder1> <folder2> ... <folderN>")
        sys.exit(1)

    repo = sys.argv[1]
    folders = sys.argv[2:]

    list_nested_files(repo, folders)

    cur.close()
    conn.close()
