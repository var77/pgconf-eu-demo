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

4. Setup Database
```bash
LLM_BATCH_SIZE=150 DATABASE_URL='<db_url>' OPENAI_API_KEY='<openai_api_key>' python3 process_repo.py citus repos/citus/src/backend
```
Batch size is based on OpenAI key tier (~10 for tier1, ~150 for tier5)

4. Ask questions
```bash
 DATABASE_URL='<db_url>' python3 ask_repo.py citus 'How is sharding implemented';
```
