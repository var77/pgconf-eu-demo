-- migrate:up
create extension vector;

create table repos (
    "name" text primary key
);

create table folders (
    "repo" text,
    "name" text,
    "llm_openai" text,
    "llm_ubicloud" text,
    "vector_openai" vector(1536),
    "vector_ubicloud" vector(4096),
    primary key ("name", "repo")
);

create table files (
    "repo" text,
    "folder" text,
    "name" text,
    "code" text,
    "llm_openai" text,
    "llm_ubicloud" text,
    "vector_openai" vector(1536),
    "vector_ubicloud" vector(4096),
    primary key ("name", "folder", "repo")
);

create table commits (
    "repo" text,
    "id" text,
    "author" text,
    "date" text,
    "changes" text,
    "message" text,
    "llm_openai" text,
    "llm_ubicloud" text,
    "vector_openai" vector(1536),
    "vector_ubicloud" vector(4096),
    primary key ("repo", "id")
);

-- migrate:down

drop table files;
drop table folders;
drop table repos;
drop table commits;