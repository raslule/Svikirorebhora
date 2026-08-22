# Data Loss Prevention Policy

**CRITICAL AGENT RULE**: You MUST NOT execute any commands or scripts that result in data deletion, truncation, or destruction without explicit, prior authorization from the user.

This specifically includes, but is not limited to:
- Deleting or dropping the SQLite database (soccer_oracle.db) or any tables within it.
- Deleting, modifying, or truncating backup files (.sqlite or .bak files) in the ackend/data/backups/ directory.
- Running DROP, DELETE, or TRUNCATE SQL commands on production datasets without a WHERE clause or explicit consent.
- Running Remove-Item or m on critical data directories.

When asked to perform an action that could lead to data loss, you must STOP, clearly explain the risks to the user, and wait for them to explicitly reply with approval before proceeding.
