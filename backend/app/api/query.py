from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.deps import require_role, tenant_id
from app.db.database import session
from app.nlq.engine import answer_question

router = APIRouter(tags=["query"])


class QueryRequest(BaseModel):
    question: str


@router.post("/query")
def post_query(class_id: int, req: QueryRequest, current_user=Depends(require_role("admin"))):
    # Known v1 limitation: the regex/LLM NLQ engine has no per-teacher
    # section-scoping hook, so this stays admin-only until that's built
    # (rather than relying on the frontend simply hiding the Ask bar).
    with session() as conn:
        result = answer_question(conn, tenant_id(current_user), class_id, req.question)
        return {
            "answer": result.answer,
            "intent": result.intent,
            "table": result.table,
            "chart": result.chart,
            "suggestions": result.suggestions,
        }
