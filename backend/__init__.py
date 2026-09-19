"""Direct Democracy Cali backend package.

Layer boundaries are defined in ARCHITECTURE.md §2:
routers -> services -> repositories -> database; clients talk to external
processes; jobs call services; config reads .env and YAML.
"""
