import json
from pathlib import Path
import sqlite3
from fastapi import APIRouter, Depends, HTTPException
from app.core.database import get_db

router = APIRouter(prefix="/api/tenants", tags=["Tenants & Personas"])
SEEDS_DIR = Path(__file__).resolve().parent.parent / "seeds"

@router.get("")
def list_tenants(db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT id, name, description, created_at FROM tenants ORDER BY name;")
    rows = cursor.fetchall()
    return [{"id": r["id"], "name": r["name"], "description": r["description"]} for r in rows]

@router.get("/{tenant_id}/personas")
def get_tenant_personas(tenant_id: str):
    seed_file = SEEDS_DIR / f"{tenant_id}.json"
    if not seed_file.exists():
        raise HTTPException(status_code=404, detail=f"No seed configuration found for tenant '{tenant_id}'")
    with open(seed_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {
        "tenant_id": tenant_id,
        "tenant_name": data.get("tenant", {}).get("name", tenant_id),
        "personas": data.get("personas", [])
    }
