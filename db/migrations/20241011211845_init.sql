-- migrate:up
create table repos (
    "name" text primary key,
    "description" text
);

create table folders (
    "name" text.
    "repo" text,
    "description" text,
    primary key ("name", "repo")
);

create table files (
    "name" text,
    "folder" text,
    "repo" text,
    "code" text,
    "description" text,
    primary key ("name", "folder", "repo")
);

-- migrate:down

drop table contents;
drop table files;
drop table folders;