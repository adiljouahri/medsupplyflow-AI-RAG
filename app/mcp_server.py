"""Model Context Protocol (MCP) Server for MedSupplyFlow-AI.

Allows any MCP-compliant client (Claude Desktop, Cursor, Antigravity, Voice Agents)
to securely query medical inventory and execute actions while respecting clinic isolation.
"""

from typing import Any

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select

from app.agent.graph import run_request
from app.db.models import Clinic, Product
from app.db.session import SessionLocal

mcp = FastMCP("MedSupplyFlow-AI", dependencies=["mcp", "sqlalchemy", "pydantic"])


@mcp.tool()
def search_inventory(query: str, clinic_code: str = "demo-clinic-a") -> list[dict[str, Any]]:
    """Search available surgical catalog products and current stock levels for a specific clinic.
    
    Args:
        query: Item name or keyword (e.g., 'scalpel', 'forceps', 'catheter').
        clinic_code: Clinic identifier ensuring multi-tenant isolation.
    """
    with SessionLocal() as session:
        stmt = (
            select(Product)
            .where(
                Product.clinic_code == clinic_code,
                Product.canonical_name.ilike(f"%{query}%"),
            )
            .limit(10)
        )
        products = session.execute(stmt).scalars().all()
        return [
            {
                "id": p.id,
                "sku": p.sku,
                "name": p.canonical_name,
                "category": p.category,
                "sterile_type": p.sterile_type,
                "stock_quantity": p.stock_quantity,
                "status": p.status,
            }
            for p in products
        ]


@mcp.tool()
def list_clinics() -> list[dict[str, Any]]:
    """List available registered clinics."""
    with SessionLocal() as session:
        clinics = session.execute(select(Clinic)).scalars().all()
        return [
            {
                "clinic_code": c.clinic_code,
                "name": c.canonical_name,
                "region": c.region,
            }
            for c in clinics
        ]


@mcp.tool()
def execute_clinic_request(
    client_name: str,
    clinic_name: str,
    clinic_code: str,
    request_text: str,
) -> dict[str, Any]:
    """Execute a natural language supply inquiry or order request via the LangGraph AI agent.
    
    Args:
        client_name: Name of the requesting doctor or clinic staff.
        clinic_name: Canonical name of the clinic.
        clinic_code: Isolation code for the clinic (e.g. 'demo-clinic-a').
        request_text: Natural language supply or order request (multilingual: DE/EN/ES/FR).
    """
    return run_request(
        client_name=client_name,
        clinic_name=clinic_name,
        clinic_code=clinic_code,
        request_text=request_text,
    )


if __name__ == "__main__":
    mcp.run()
