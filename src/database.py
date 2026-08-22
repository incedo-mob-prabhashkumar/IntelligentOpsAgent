from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import Engine, create_engine, inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from src.models import Base, Employee, KnowledgeArticle, SystemStatus, Ticket


logger = logging.getLogger(__name__)

EXPECTED_COLUMNS = {
    table.name: {column.name for column in table.columns}
    for table in Base.metadata.sorted_tables
}


@dataclass(frozen=True)
class DatabaseStatus:
    ready: bool
    message: str
    schema_created: bool = False


def normalize_database_url(postgres_dsn: str) -> str:
    """Use psycopg v3 explicitly when a standard PostgreSQL URL is supplied."""
    if postgres_dsn.startswith("postgresql://"):
        return postgres_dsn.replace("postgresql://", "postgresql+psycopg://", 1)
    if postgres_dsn.startswith("postgres://"):
        return postgres_dsn.replace("postgres://", "postgresql+psycopg://", 1)
    return postgres_dsn


class Database:
    def __init__(self, postgres_dsn: str) -> None:
        self.engine: Engine = create_engine(
            normalize_database_url(postgres_dsn),
            pool_pre_ping=True,
        )
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)

    def initialize(self) -> DatabaseStatus:
        """Create missing ORM tables and seed only records that are not present."""
        try:
            Base.metadata.create_all(self.engine)
            issues = self._validate_schema()
            if issues:
                return DatabaseStatus(False, "Database schema validation failed: " + "; ".join(issues))

            with self.session_factory.begin() as session:
                _seed_data(session)

            logger.info("ORM database schema validated and seed data ensured")
            return DatabaseStatus(True, "Database schema is ready.", schema_created=True)
        except SQLAlchemyError as exc:
            logger.exception("Database initialization failed")
            root_cause = str(getattr(exc, "orig", exc)).splitlines()[0]
            return DatabaseStatus(
                False,
                (
                    "Database is unavailable or incompatible "
                    f"({exc.__class__.__name__}: {root_cause})."
                ),
            )

    def _validate_schema(self) -> list[str]:
        inspector = inspect(self.engine)
        tables = set(inspector.get_table_names())
        issues: list[str] = []
        for table_name, expected_columns in EXPECTED_COLUMNS.items():
            if table_name not in tables:
                issues.append(f"required table is missing: {table_name}")
                continue
            present_columns = {column["name"] for column in inspector.get_columns(table_name)}
            missing_columns = expected_columns - present_columns
            if missing_columns:
                issues.append(
                    f"{table_name} is missing columns: {', '.join(sorted(missing_columns))}"
                )
        return issues


def _seed_data(session: Session) -> None:
    employees = [
        Employee(employee_id="EMP1024", name="Aarav Mehta", department="Finance", email="aarav.mehta@example.com", location="Bengaluru"),
        Employee(employee_id="EMP2048", name="Diya Nair", department="Engineering", email="diya.nair@example.com", location="Pune"),
        Employee(employee_id="EMP3001", name="Rohan Iyer", department="Sales", email="rohan.iyer@example.com", location="Mumbai"),
    ]
    articles = [
        KnowledgeArticle(article_id="KB-001", title="Reset VPN Password", tags=["vpn", "password", "reset", "remote-access"], content="Open the Self-Service Portal, choose 'Reset Network Password', complete MFA, and wait 2 minutes before reconnecting VPN.", last_updated=date(2026, 5, 10)),
        KnowledgeArticle(article_id="KB-002", title="Fix Outlook Not Syncing", tags=["email", "outlook", "sync"], content="Check internet connectivity, restart Outlook, then recreate your profile from Control Panel > Mail if sync issues continue.", last_updated=date(2026, 4, 22)),
        KnowledgeArticle(article_id="KB-003", title="Laptop Battery Health Check", tags=["laptop", "battery", "hardware"], content="Run the vendor diagnostics app and submit the generated battery report to IT support if health is below 60%.", last_updated=date(2026, 6, 15)),
        KnowledgeArticle(article_id="KB-004", title="Corporate Wi-Fi Troubleshooting", tags=["wifi", "network", "connectivity"], content="Forget the corporate SSID, reconnect using your company credentials, and verify your device time is set automatically.", last_updated=date(2026, 7, 1)),
    ]
    tickets = [
        Ticket(ticket_id="TKT1001", employee_id="EMP1024", summary="VPN disconnects every 10 minutes", category="network", priority="high", status="in_progress", created_at=datetime(2026, 8, 15, 9, 30, tzinfo=timezone.utc), updated_at=datetime(2026, 8, 20, 11, 10, tzinfo=timezone.utc), notes=["Initial diagnostics completed", "Awaiting user logs"]),
        Ticket(ticket_id="TKT1002", employee_id="EMP2048", summary="Outlook mailbox not syncing", category="software", priority="medium", status="open", created_at=datetime(2026, 8, 18, 12, 5, tzinfo=timezone.utc), updated_at=datetime(2026, 8, 18, 12, 5, tzinfo=timezone.utc), notes=["Assigned to messaging support queue"]),
    ]
    systems = [
        SystemStatus(service="VPN Gateway", status="operational", updated_at=datetime(2026, 8, 22, 8, 0, tzinfo=timezone.utc)),
        SystemStatus(service="Email Service", status="degraded", updated_at=datetime(2026, 8, 22, 7, 45, tzinfo=timezone.utc)),
        SystemStatus(service="SSO Authentication", status="operational", updated_at=datetime(2026, 8, 22, 8, 5, tzinfo=timezone.utc)),
    ]

    for model, records, primary_key in (
        (Employee, employees, "employee_id"),
        (KnowledgeArticle, articles, "article_id"),
        (Ticket, tickets, "ticket_id"),
        (SystemStatus, systems, "service"),
    ):
        for record in records:
            if session.get(model, getattr(record, primary_key)) is None:
                session.add(record)


def initialize_database(postgres_dsn: str) -> tuple[Database, DatabaseStatus]:
    database = Database(postgres_dsn)
    return database, database.initialize()
