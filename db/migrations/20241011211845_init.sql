-- migrate:up
create table files (
    "repo" text,
    "folder" text,
    "name" text,
    "code" text,
    "description" text,
    "vector" vector(1536),
    primary key ("name", "folder", "repo")
);

-- migrate:down

drop table files;