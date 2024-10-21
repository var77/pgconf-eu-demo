import os
import sys
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# Establish DB connection
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()
# Main function to handle user questions

def main(repo: str, question: str) -> str:
    print("QUESTION")
    print(question)

    cur.execute("SELECT ask(%s, %s);", (question, repo))
    answer = cur.fetchone()[0]
    print("\nANSWER")
    print(answer)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python ask_repo.py <repo> <question>")
        sys.exit(1)

    repo_name = sys.argv[1]
    question = sys.argv[2]
    main(repo_name, question)

    # Close database connection
    cur.close()
    conn.close()
