-- migrate:up
create table repos (
    "name" text primary key,
    "description" text
);

create table folders (
    "name" text primary key,
    "repo" text,
    "description" text
);

create table files (
    "name" text primary key,
    "folder" text,
    "code" text,
    "description" text
);

create table components (
    "name" text,
    "file" text,
    "type" text,
    "code" text,
    "description" text,
    primary key ("name", "file")
);

-- migrate:down

