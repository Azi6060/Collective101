# Approved organization knowledge

Place only documents you deliberately want product agents to read here. Documents supplied to live agents are sent to your configured model provider. Never put credentials or unrelated private files here.

- `shared/`: reference documents available to eligible agents in every department.
- `<department>/`: private reference documents for that department, e.g. `engineering/` or `operations/`.
- Supported: UTF-8 `.md`, `.txt`, `.csv`, `.json`; at most 64 KiB per file. Reads return at most 12,000 characters; searches inspect at most 200 files and return five excerpts.
- Hidden paths, absolute paths, traversal, symlinks and junctions are rejected. Agents cannot write or import files, read arbitrary host paths, or read another department's folder.
- Files are ignored by Git by default. The directory is a local knowledge source, not a vector database. There is no upload/ingestion UI yet.
- Agent memory is separate: reviewed same-agent episodes in SQLite, separated by provider signature. Only reference material is recalled; roles and permissions remain authoritative in code and definition files.
