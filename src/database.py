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
        Employee(employee_id="EMP4010", name="Meera Kapoor", department="Human Resources", email="meera.kapoor@example.com", location="Delhi"),
        Employee(employee_id="EMP5099", name="Vikram Sethi", department="IT Operations", email="vikram.sethi@example.com", location="Hyderabad"),
        Employee(employee_id="EMP6123", name="Ananya Rao", department="Legal", email="ananya.rao@example.com", location="Chennai"),
    ]
    articles = [
        KnowledgeArticle(article_id="KB-001", title="Reset VPN Password", tags=["vpn", "password", "reset", "remote-access"], content="Open the Self-Service Portal, choose 'Reset Network Password', complete MFA, and wait 2 minutes before reconnecting VPN.", last_updated=date(2026, 5, 10)),
        KnowledgeArticle(article_id="KB-002", title="Fix Outlook Not Syncing", tags=["email", "outlook", "sync"], content="Check internet connectivity, restart Outlook, then recreate your profile from Control Panel > Mail if sync issues continue.", last_updated=date(2026, 4, 22)),
        KnowledgeArticle(article_id="KB-003", title="Laptop Battery Health Check", tags=["laptop", "battery", "hardware"], content="Run the vendor diagnostics app and submit the generated battery report to IT support if health is below 60%.", last_updated=date(2026, 6, 15)),
        KnowledgeArticle(article_id="KB-004", title="Corporate Wi-Fi Troubleshooting", tags=["wifi", "network", "connectivity"], content="Forget the corporate SSID, reconnect using your company credentials, and verify your device time is set automatically.", last_updated=date(2026, 7, 1)),
        KnowledgeArticle(article_id="KB-005", title="MFA Unlock for Account Access", tags=["mfa", "account", "access", "unlock"], content="Open the identity portal, choose 'Unlock Account', verify with backup method, and wait 5 minutes before retrying sign in.", last_updated=date(2026, 7, 20)),
        KnowledgeArticle(article_id="KB-006", title="Laptop Screen Flicker Troubleshooting", tags=["laptop", "hardware", "display", "screen"], content="Update graphics drivers, disable adaptive refresh, test with an external monitor, and raise a hardware ticket if flicker continues.", last_updated=date(2026, 8, 3)),
        KnowledgeArticle(article_id="KB-007", title="Office Printer Offline Fix", tags=["printer", "hardware", "office", "connectivity"], content="Power cycle the printer, verify LAN cable or Wi-Fi signal, then remove and re-add the printer profile from system settings.", last_updated=date(2026, 8, 11)),
        KnowledgeArticle(article_id="KB-008", title="SSO Login Loop Resolution", tags=["sso", "authentication", "login", "access"], content="Clear browser cookies for company domains, sync device time, and retry login in an incognito window before escalating.", last_updated=date(2026, 8, 28)),
    ]
    tickets = [
        Ticket(ticket_id="TKT1001", employee_id="EMP1024", summary="VPN disconnects every 10 minutes", category="network", priority="high", status="in_progress", created_at=datetime(2026, 8, 15, 9, 30, tzinfo=timezone.utc), updated_at=datetime(2026, 8, 20, 11, 10, tzinfo=timezone.utc), notes=["Initial diagnostics completed", "Awaiting user logs"]),
        Ticket(ticket_id="TKT1002", employee_id="EMP2048", summary="Outlook mailbox not syncing", category="software", priority="medium", status="open", created_at=datetime(2026, 8, 18, 12, 5, tzinfo=timezone.utc), updated_at=datetime(2026, 8, 18, 12, 5, tzinfo=timezone.utc), notes=["Assigned to messaging support queue"]),
        Ticket(ticket_id="TKT1003", employee_id="EMP4010", summary="Laptop screen flickers intermittently", category="hardware", priority="high", status="open", created_at=datetime(2026, 8, 19, 10, 15, tzinfo=timezone.utc), updated_at=datetime(2026, 8, 21, 9, 40, tzinfo=timezone.utc), notes=["Display diagnostics requested", "Awaiting asset team pickup"]),
        Ticket(ticket_id="TKT1004", employee_id="EMP5099", summary="MFA approval prompt not received", category="access", priority="medium", status="in_progress", created_at=datetime(2026, 8, 20, 14, 10, tzinfo=timezone.utc), updated_at=datetime(2026, 8, 22, 8, 30, tzinfo=timezone.utc), notes=["Token re-registered", "Monitoring login attempts"]),
        Ticket(ticket_id="TKT1005", employee_id="EMP6123", summary="Teams calls dropping after 15 minutes", category="collaboration", priority="medium", status="resolved", created_at=datetime(2026, 8, 12, 11, 0, tzinfo=timezone.utc), updated_at=datetime(2026, 8, 23, 16, 45, tzinfo=timezone.utc), notes=["QoS policy updated", "User confirmed issue resolved"]),
    ]
    systems = [
        SystemStatus(service="VPN Gateway", status="operational", updated_at=datetime(2026, 8, 22, 8, 0, tzinfo=timezone.utc)),
        SystemStatus(service="Email Service", status="degraded", updated_at=datetime(2026, 8, 22, 7, 45, tzinfo=timezone.utc)),
        SystemStatus(service="SSO Authentication", status="operational", updated_at=datetime(2026, 8, 22, 8, 5, tzinfo=timezone.utc)),
        SystemStatus(service="Laptop Hardware Support", status="operational", updated_at=datetime(2026, 8, 22, 8, 10, tzinfo=timezone.utc)),
        SystemStatus(service="Collaboration Platform", status="degraded", updated_at=datetime(2026, 8, 22, 8, 20, tzinfo=timezone.utc)),
        SystemStatus(service="Endpoint Management", status="operational", updated_at=datetime(2026, 8, 22, 8, 25, tzinfo=timezone.utc)),
        SystemStatus(service="Office Printer Service", status="operational", updated_at=datetime(2026, 8, 22, 8, 30, tzinfo=timezone.utc)),
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
