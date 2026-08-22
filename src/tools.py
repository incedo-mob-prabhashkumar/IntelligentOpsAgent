from __future__ import annotations

import logging
import os
import re
from functools import lru_cache
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np

from sqlalchemy import Integer, cast, func, or_, select
from sqlalchemy.exc import SQLAlchemyError

from src.database import Database
from src.models import Employee, KnowledgeArticle, SystemStatus, Ticket


logger = logging.getLogger(__name__)

_DUPLICATE_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "have",
    "has",
    "had",
    "not",
    "are",
    "was",
    "were",
    "your",
    "some",
    "very",
    "issue",
    "ticket",
    "please",
    "help",
    "working",
}

_SEARCH_STOPWORDS = {
    "a",
    "an",
    "the",
    "is",
    "am",
    "are",
    "to",
    "of",
    "for",
    "and",
    "or",
    "in",
    "on",
    "my",
    "i",
    "me",
    "it",
    "with",
}


@lru_cache(maxsize=1)
def _get_sentence_transformer_model() -> Any:
    from sentence_transformers.SentenceTransformer import SentenceTransformer

    model_name = os.getenv("SENTENCE_TRANSFORMER_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    return SentenceTransformer(model_name)


def _dedupe_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9]+", text.lower())
        if len(token) > 2 and token not in _DUPLICATE_STOPWORDS
    }


def _search_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9]+", text.lower())
        if len(token) > 2 and token not in _SEARCH_STOPWORDS
    }


def _article_to_dict(article: KnowledgeArticle) -> dict[str, Any]:
    return {
        "article_id": article.article_id,
        "title": article.title,
        "tags": article.tags,
        "content": article.content,
        "last_updated": article.last_updated,
    }


def _ticket_to_dict(ticket: Ticket) -> dict[str, Any]:
    return {
        "ticket_id": ticket.ticket_id,
        "employee_id": ticket.employee_id,
        "summary": ticket.summary,
        "category": ticket.category,
        "priority": ticket.priority,
        "status": ticket.status,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
        "notes": ticket.notes,
    }


def _system_status_to_dict(row: SystemStatus) -> dict[str, Any]:
    return {
        "service": row.service,
        "status": row.status,
        "updated_at": row.updated_at,
    }


class LocalITTools:
    """Database tools backed by SQLAlchemy ORM sessions."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def search_knowledge(self, query: str, top_k: int = 3) -> dict[str, Any]:
        statement = select(KnowledgeArticle).order_by(KnowledgeArticle.last_updated.desc())

        try:
            with self.database.session_factory() as session:
                candidates = [_article_to_dict(article) for article in session.scalars(statement)]
        except SQLAlchemyError as exc:
            logger.exception("Knowledge search failed")
            return {
                "query": query,
                "matches": [],
                "count": 0,
                "source": "postgres.knowledge_base",
                "error": f"Database error during knowledge search: {exc.__class__.__name__}",
            }

        semantic_matches = self._semantic_rank_articles(query=query, candidates=candidates, top_k=top_k)
        if semantic_matches is not None:
            return {
                "query": query,
                "matches": semantic_matches,
                "count": len(semantic_matches),
                "source": "postgres.knowledge_base",
                "retrieval": "semantic",
            }

        scored: list[tuple[float, dict[str, Any]]] = []
        query_tokens = _search_tokens(query)
        for article in candidates:
            article_text = " ".join(
                [
                    str(article.get("title", "")),
                    " ".join(article.get("tags", []) or []),
                    str(article.get("content", "")),
                ]
            )
            article_tokens = _search_tokens(article_text)
            if not query_tokens or not article_tokens:
                continue

            overlap = query_tokens & article_tokens
            overlap_count = len(overlap)
            ratio = overlap_count / len(query_tokens)

            # Relevance gate:
            # - if query has 3+ strong tokens, require at least 2 overlaps
            # - otherwise require at least 1 overlap
            min_overlap = 2 if len(query_tokens) >= 3 else 1
            if overlap_count < min_overlap or ratio < 0.34:
                continue

            score = ratio + (0.1 * overlap_count)
            scored.append((score, article))

        scored.sort(key=lambda item: item[0], reverse=True)
        matches = [article for _, article in scored[:top_k]]

        return {
            "query": query,
            "matches": matches,
            "count": len(matches),
            "source": "postgres.knowledge_base",
            "retrieval": "lexical_fallback",
        }

    def _semantic_rank_articles(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]] | None:
        try:
            model = _get_sentence_transformer_model()
            query_text = query.strip()
            if not query_text:
                return []

            doc_texts = [
                " ".join(
                    [
                        str(article.get("title", "")),
                        " ".join(article.get("tags", []) or []),
                        str(article.get("content", "")),
                    ]
                )
                for article in candidates
            ]

            if not doc_texts:
                return []

            query_embedding = model.encode(
                [query_text],
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
            doc_embeddings = model.encode(
                doc_texts,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )

            query_vec = query_embedding[0]
            similarities = np.dot(doc_embeddings, query_vec).tolist()

            scored = list(zip(similarities, candidates))
            scored.sort(key=lambda item: item[0], reverse=True)

            # Filter weak matches to avoid unrelated answers.
            filtered = [article for score, article in scored if score >= 0.35][:top_k]
            return filtered
        except Exception:
            logger.exception("Semantic knowledge ranking failed; using lexical fallback")
            return None

    def lookup_tickets(self, employee_id: str, query: str | None = None) -> dict[str, Any]:
        statement = (
            select(Ticket)
            .where(func.upper(Ticket.employee_id) == employee_id.upper())
            .order_by(Ticket.updated_at.desc())
        )
        try:
            with self.database.session_factory() as session:
                tickets = [_ticket_to_dict(ticket) for ticket in session.scalars(statement)]
        except SQLAlchemyError as exc:
            logger.exception("Ticket lookup failed")
            return {
                "employee_id": employee_id.upper(),
                "tickets": [],
                "count": 0,
                "source": "postgres.tickets",
                "error": f"Database error during ticket lookup: {exc.__class__.__name__}",
            }

        return {
            "employee_id": employee_id.upper(),
            "tickets": tickets,
            "count": len(tickets),
            "source": "postgres.tickets",
        }

    def lookup_ticket_by_id(self, ticket_id: str) -> dict[str, Any]:
        statement = select(Ticket).where(func.upper(Ticket.ticket_id) == ticket_id.upper())
        try:
            with self.database.session_factory() as session:
                ticket = session.scalar(statement)
        except SQLAlchemyError as exc:
            logger.exception("Ticket lookup by ID failed")
            return {
                "ticket_id": ticket_id.upper(),
                "employee_id": "",
                "tickets": [],
                "count": 0,
                "source": "postgres.tickets",
                "error": f"Database error during ticket lookup: {exc.__class__.__name__}",
            }

        if ticket is None:
            return {
                "ticket_id": ticket_id.upper(),
                "employee_id": "",
                "tickets": [],
                "count": 0,
                "source": "postgres.tickets",
            }

        ticket_dict = _ticket_to_dict(ticket)
        return {
            "ticket_id": ticket_id.upper(),
            "employee_id": ticket_dict.get("employee_id", ""),
            "tickets": [ticket_dict],
            "count": 1,
            "source": "postgres.tickets",
        }

    def employee_exists(self, employee_id: str) -> bool:
        try:
            with self.database.session_factory() as session:
                return session.get(Employee, employee_id.upper()) is not None
        except SQLAlchemyError:
            logger.exception("Employee validation failed")
            return False

    def lookup_employee_by_id(self, employee_id: str) -> dict[str, Any]:
        try:
            with self.database.session_factory() as session:
                employee = session.get(Employee, employee_id.upper())
        except SQLAlchemyError as exc:
            logger.exception("Employee lookup failed")
            return {
                "employee_id": employee_id.upper(),
                "employees": [],
                "count": 0,
                "source": "postgres.employees",
                "error": f"Database error during employee lookup: {exc.__class__.__name__}",
            }

        if employee is None:
            return {
                "employee_id": employee_id.upper(),
                "employees": [],
                "count": 0,
                "source": "postgres.employees",
            }

        return {
            "employee_id": employee.employee_id,
            "employees": [
                {
                    "employee_id": employee.employee_id,
                    "name": employee.name,
                    "department": employee.department,
                    "email": employee.email,
                    "location": employee.location,
                }
            ],
            "count": 1,
            "source": "postgres.employees",
        }

    def find_duplicate_ticket(self, employee_id: str, issue_summary: str) -> dict[str, Any] | None:
        requested_tokens = _dedupe_tokens(issue_summary)
        if not requested_tokens:
            return None

        try:
            with self.database.session_factory() as session:
                candidates = session.scalars(
                    select(Ticket)
                    .where(
                        func.upper(Ticket.employee_id) == employee_id.upper(),
                        Ticket.status.in_(["open", "in_progress"]),
                        Ticket.created_at >= datetime.now(timezone.utc) - timedelta(days=14),
                    )
                    .order_by(Ticket.updated_at.desc())
                )
                for ticket in candidates:
                    existing_tokens = _dedupe_tokens(ticket.summary)
                    if not existing_tokens:
                        continue

                    overlap = requested_tokens & existing_tokens
                    overlap_count = len(overlap)
                    union_count = len(requested_tokens | existing_tokens)
                    similarity = overlap_count / union_count if union_count else 0.0

                    # Require meaningful overlap to avoid false positives on generic words.
                    if overlap_count >= 2 and similarity >= 0.34:
                        payload = _ticket_to_dict(ticket)
                        payload["duplicate_reason"] = (
                            f"Matched terms: {', '.join(sorted(overlap))}; "
                            f"similarity={similarity:.2f}"
                        )
                        payload["matched_terms"] = sorted(overlap)
                        payload["similarity_score"] = round(similarity, 3)
                        return payload
        except SQLAlchemyError:
            logger.exception("Duplicate ticket check failed")
        return None

    def _next_ticket_id(self, session: Any) -> str:
        max_id = session.scalar(
            select(
                func.coalesce(
                    func.max(cast(func.substring(Ticket.ticket_id, 4), Integer)),
                    1000,
                )
            ).where(Ticket.ticket_id.op("~")(r"^TKT[0-9]+$"))
        )
        return f"TKT{int(max_id) + 1}"

    def create_ticket(
        self,
        employee_id: str,
        issue_summary: str,
        category: str = "general",
        priority: str = "medium",
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        try:
            with self.database.session_factory.begin() as session:
                ticket = Ticket(
                    ticket_id=self._next_ticket_id(session),
                    employee_id=employee_id.upper(),
                    summary=issue_summary.strip(),
                    category=category,
                    priority=priority,
                    status="open",
                    created_at=now,
                    updated_at=now,
                    notes=["Ticket created by AI IT Support Assistant"],
                )
                session.add(ticket)
        except SQLAlchemyError as exc:
            logger.exception("Ticket creation failed")
            return {
                "created": False,
                "ticket": {},
                "source": "postgres.tickets",
                "error": f"Database error during ticket creation: {exc.__class__.__name__}",
            }

        return {
            "created": True,
            "ticket": _ticket_to_dict(ticket),
            "source": "postgres.tickets",
        }

    def update_ticket_summary(self, ticket_id: str, new_summary: str) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        try:
            with self.database.session_factory.begin() as session:
                ticket = session.scalar(
                    select(Ticket).where(func.upper(Ticket.ticket_id) == ticket_id.upper())
                )
                if ticket is None:
                    return {
                        "updated": False,
                        "ticket": {},
                        "ticket_id": ticket_id.upper(),
                        "source": "postgres.tickets",
                        "not_found": True,
                    }

                ticket.summary = new_summary.strip()
                ticket.updated_at = now
                notes = list(ticket.notes or [])
                notes.append("Ticket summary updated by AI IT Support Assistant")
                ticket.notes = notes

                updated_ticket = _ticket_to_dict(ticket)
        except SQLAlchemyError as exc:
            logger.exception("Ticket update failed")
            return {
                "updated": False,
                "ticket": {},
                "ticket_id": ticket_id.upper(),
                "source": "postgres.tickets",
                "error": f"Database error during ticket update: {exc.__class__.__name__}",
            }

        return {
            "updated": True,
            "ticket": updated_ticket,
            "ticket_id": ticket_id.upper(),
            "source": "postgres.tickets",
        }

    def list_employees(self, limit: int = 50) -> list[dict[str, Any]]:
        statement = select(Employee).order_by(Employee.employee_id).limit(limit)
        try:
            with self.database.session_factory() as session:
                rows = session.scalars(statement)
                return [
                    {
                        "employee_id": row.employee_id,
                        "name": row.name,
                        "department": row.department,
                        "email": row.email,
                        "location": row.location,
                    }
                    for row in rows
                ]
        except SQLAlchemyError:
            logger.exception("Employee table listing failed")
            return []

    def list_tickets(self, limit: int = 100) -> list[dict[str, Any]]:
        statement = select(Ticket).order_by(Ticket.updated_at.desc()).limit(limit)
        try:
            with self.database.session_factory() as session:
                rows = session.scalars(statement)
                return [_ticket_to_dict(row) for row in rows]
        except SQLAlchemyError:
            logger.exception("Ticket table listing failed")
            return []

    def list_knowledge_articles(self, limit: int = 50) -> list[dict[str, Any]]:
        statement = select(KnowledgeArticle).order_by(KnowledgeArticle.last_updated.desc()).limit(limit)
        try:
            with self.database.session_factory() as session:
                rows = session.scalars(statement)
                return [_article_to_dict(row) for row in rows]
        except SQLAlchemyError:
            logger.exception("Knowledge base table listing failed")
            return []

    def get_system_status(self, query: str | None = None) -> dict[str, Any]:
        statement = select(SystemStatus).order_by(SystemStatus.service.asc())
        if query:
            wildcard = f"%{query.lower()}%"
            statement = statement.where(
                or_(
                    func.lower(SystemStatus.service).like(wildcard),
                    func.lower(SystemStatus.status).like(wildcard),
                )
            )
        try:
            with self.database.session_factory() as session:
                rows = [_system_status_to_dict(row) for row in session.scalars(statement)]
        except SQLAlchemyError as exc:
            logger.exception("System status lookup failed")
            return {
                "statuses": [],
                "count": 0,
                "source": "postgres.system_status",
                "error": f"Database error during system status lookup: {exc.__class__.__name__}",
            }

        return {
            "statuses": rows,
            "count": len(rows),
            "source": "postgres.system_status",
        }
