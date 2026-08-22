from __future__ import annotations

import unittest

from src.database import EXPECTED_COLUMNS, normalize_database_url
from src.models import Employee, KnowledgeArticle, Ticket


class DatabaseModelTests(unittest.TestCase):
    def test_orm_models_define_the_expected_schema(self) -> None:
        self.assertEqual(
            EXPECTED_COLUMNS[Employee.__tablename__],
            {"employee_id", "name", "department", "email", "location"},
        )
        self.assertEqual(
            EXPECTED_COLUMNS[KnowledgeArticle.__tablename__],
            {"article_id", "title", "tags", "content", "last_updated"},
        )
        self.assertIn("ticket_id", EXPECTED_COLUMNS[Ticket.__tablename__])
        self.assertIn("employee_id", EXPECTED_COLUMNS[Ticket.__tablename__])

    def test_standard_postgres_url_uses_psycopg_v3_driver(self) -> None:
        self.assertEqual(
            normalize_database_url("postgresql://user:pass@localhost/it_support"),
            "postgresql+psycopg://user:pass@localhost/it_support",
        )


if __name__ == "__main__":
    unittest.main()
