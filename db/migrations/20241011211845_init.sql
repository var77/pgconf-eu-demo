-- migrate:up
create table files (
    "id" serial primary key,
    "repo" text,
    "name" text,
    "code" text,
    unique ("name", "repo")
);

-- migrate:down

drop table files;