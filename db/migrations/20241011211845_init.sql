-- migrate:up
create table files (
    "id" serial primary key,
    "repo" text,
    "name" text,
    "code" text
);

-- migrate:down

drop table files;