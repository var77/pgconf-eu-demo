-- migrate:up
create table repos (
    "model" text,
    "name" text,
    "description" text,
    primary key ("model", "name")
);

create table folders (
    "model" text,
    "repo" text,
    "name" text.
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

-- migrate:down

drop table contents;
drop table files;
drop table folders;