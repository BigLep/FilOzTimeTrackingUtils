# The playbook and day proposals stay out of git

The drafting process (glossary, ADRs, skill) is committed, but the playbook and the day proposals live in a gitignored `local/` folder. They are full of people, channel, and family names, and this repo must never commit PII. We accepted that these files are backed up only by the machine's own backups. Timing's context store holds a one-line pointer to the playbook, not a copy, so there is a single source of truth.

## Considered Options

- Everything in Timing's `AGENTS.md` store: available to any Timing client, but awkward to diff and review, and it would split the process docs from the knowledge.
- A separate private git repo: gives off-machine backup and history, at the cost of another repo to maintain. Worth revisiting if the playbook becomes valuable enough to lose sleep over.
