# Security

[Русская версия](SECURITY.ru.md)

## Reporting a vulnerability

Write to **admin@besk.tech** with "Askbase" in the subject. Do not open a
public issue for a vulnerability, and do not attach a real database or real
data from one. You will get an answer within 7 days.

Only the latest release is supported. Today that is 0.1.1.

A wrong answer or a wrong query is a quality problem, not a vulnerability, and
belongs in a public issue with an invented database. A vulnerability is, for
example, a way to make the application write to a database, run more than one
statement, send anything off the machine, or read a file other than the one
that was opened.


## What the application protects and what it does not

**The model is never given the database.** It receives a snapshot of the
schema, a sample of column values and the question, and it returns text. That
text is parsed and checked before anything is executed. A model that produced
`DROP TABLE` would have it refused at the check, not obeyed.

**Every statement is parsed before it runs.** One statement, `SELECT` only, a
leading `WITH` allowed, no `PRAGMA`, no transaction control, no recursive
`WITH`, tables and qualified columns checked against the snapshot taken at
connection time, and a `LIMIT` added when the model did not write one. The
list and the reasoning are on
[askbase.besk.tech/read-only-access/](https://askbase.besk.tech/read-only-access/).

**The connection is read-only and that is verified, not assumed.** On opening
a file the application attempts a write that must fail. A database that
accepts the write is not opened at all.

**Each query is bounded** by a row cap, a timeout, and a limit on the size of
a single value. Without the last of those, one generated expression occupied
3 GB of memory and 57 seconds against a 2 second timeout, because the timeout
could not interrupt the work inside SQLite.

**Nothing leaves the machine.** The application blocks outbound connections at
startup and reaches the model over the loopback address. The block covers TCP
connect, UDP send and name resolution. You can check it rather than believe
it: `Askbase.app/Contents/MacOS/Askbase --selftest`.

**The limits of that block, stated plainly.** It is installed by replacing
functions in the Python `socket` module, so it governs this application and
the libraries it imports. `_socket.socket` is an immutable C type and cannot
be replaced, so code reaching the C layer directly would not be stopped. This
is a control over our own code, not a sandbox around the process. If you need
a guarantee at the level of the operating system, use a firewall rule.

**The journal holds no data from your database.** It keeps the question as
typed, the generated query, the number of rows, the elapsed time and the path
to the file. Never a result row. It lives beside the settings and can be
emptied from the settings screen.

**The build is not signed.** There is no Apple developer certificate and no
notarisation yet, so macOS asks you to allow the application once. Check the
SHA-256 of the disk image against the one in the release notes before you open
it.

**Prompt injection is a real risk and the parser is the answer to it.** Text
in your own data, a column comment or a crafted table name can steer a model.
What keeps that from reaching the database is the static check, not the
model's good behaviour. For the same reason, identifiers from the database are
quoted before the schema snapshot is taken: a prepared file could otherwise
inject SQL through a column name, before any check had run.

**The application's own rules are a second line, not the first.** Give it a
role in the database that can only read. The SQL for PostgreSQL, MySQL and
SQLite is on the read-only access page linked above.
