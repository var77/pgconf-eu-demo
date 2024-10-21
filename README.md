## Setup

1. Clone the repo you want to index under repos/
```bash
git clone --depth 1 https://github.com/citusdata/citus.git repos/citus
```

2. Setup python dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

3. Create Lantern Database from Ubicloud Dashboard
Go to https://www.ubicloud.com/ and create a new Lantern Database

4. Setup environment variables
```bash
export DATABASE_URL='<db_url>'
export OPENAI_API_KEY='<openai_token>'
export LLM_BATCH_SIZE=150
```
5. Setup Database
```bash
python3 process_repo.py citus repos/citus/src/backend
```
Batch size is based on OpenAI key tier (~10 for tier 1, ~150 for tier 5)

6. Ask questions
```bash
python3 ask_repo.py citus 'How is sharding implemented';
```
