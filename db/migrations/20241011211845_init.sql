-- migrate:up
create extension vector;

create table repos (
    "name" text primary key
);

create table folders (
    "model" text,
    "repo" text,
    "name" text,
    "description" text,
    "vector" vector(1536),
    primary key ("model", "name", "repo")
);

create table files (
    "model" text,
    "repo" text,
    "folder" text,
    "name" text,
    "code" text,
    "description" text,
    "vector" vector(1536),
    primary key ("model", "name", "folder", "repo")
);

create table commits (
    "model" text,
    "repo" text,
    "id" text,
    "author" text,
    "date" text,
    "changes" text,
    "message" text,
    "description" text,
    "vector" vector(1536),
    primary key ("model", "repo", "id")
);

-- migrate:down

drop table files;
drop table folders;
drop table repos;
drop table commits;