import json
import sqlite3
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
from app.core.database import get_db
from app.core.context import RequestContext, get_request_context
from app.security.rbac import RBACService
from app.security.projection import FieldProjector
from app.services.audit import AuditService

router = APIRouter(prefix="/api/dashboards", tags=["Analytics & Dashboards"])

@router.get("")
def list_dashboards(
    ctx: RequestContext = Depends(get_request_context),
    db: sqlite3.Connection = Depends(get_db)
):
    cursor = db.cursor()
    cursor.execute("SELECT id, title FROM dashboards WHERE tenant_id = ?;", (ctx.tenant_id,))
    rows = cursor.fetchall()
    return [{"id": r["id"], "title": r["title"]} for r in rows]

@router.get("/{dashboard_id}")
def get_dashboard_metrics(
    dashboard_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: sqlite3.Connection = Depends(get_db)
):
    cursor = db.cursor()
    cursor.execute("""
        SELECT id, title, widgets FROM dashboards
        WHERE id = ? AND tenant_id = ?;
    """, (dashboard_id, ctx.tenant_id))
    dash_row = cursor.fetchone()
    if not dash_row:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    widgets_config = json.loads(dash_row["widgets"])
    computed_widgets = []

    for w in widgets_config:
        w_id = w.get("widget_id")
        w_title = w.get("title")
        w_type = w.get("type")
        obj_type = w.get("object_type")
        metric_cfg = w.get("metric", {})
        group_by = w.get("group_by")
        agg_type = metric_cfg.get("agg", "count")
        metric_field = metric_cfg.get("field")

        # 1. Check Object Permission
        perms = RBACService.get_permissions(db, ctx.tenant_id, obj_type, ctx.actor_role)
        if not perms["can_read"]:
            computed_widgets.append({
                "widget_id": w_id,
                "title": w_title,
                "type": w_type,
                "status": "RESTRICTED",
                "error": "Access denied: persona cannot view this entity"
            })
            continue

        # 2. Strict Anti-Leakage Check on Metric and Group-By Fields
        field_perms = perms["field_permissions"]
        required_fields = []
        if metric_field and metric_field not in ["id", "state", "version"]:
            required_fields.append(metric_field)
        if group_by and group_by not in ["id", "state", "version"]:
            required_fields.append(group_by)

        if not FieldProjector.can_read_fields(required_fields, field_perms):
            AuditService.log(
                db, ctx.tenant_id, ctx.actor_id, ctx.actor_role,
                action="DASHBOARD_METRIC_ACCESS", outcome="DENIED",
                object_type=obj_type,
                reason=f"Widget '{w_title}' references hidden fields: {required_fields}"
            )
            computed_widgets.append({
                "widget_id": w_id,
                "title": w_title,
                "type": w_type,
                "status": "RESTRICTED",
                "error": "This metric is hidden because it aggregates or groups by restricted fields."
            })
            continue

        # 3. Authorized Calculation
        cursor.execute("""
            SELECT id, state, data FROM records
            WHERE tenant_id = ? AND object_type = ? AND is_deleted = 0;
        """, (ctx.tenant_id, obj_type))
        records = cursor.fetchall()

        if w_type == "kpi":
            if agg_type == "count":
                kpi_val = len(records)
            elif agg_type == "sum" and metric_field:
                kpi_val = sum(float(json.loads(r["data"]).get(metric_field, 0) or 0) for r in records)
            elif agg_type == "avg" and metric_field:
                vals = [float(json.loads(r["data"]).get(metric_field, 0) or 0) for r in records]
                kpi_val = round(sum(vals) / len(vals), 2) if vals else 0
            else:
                kpi_val = len(records)

            computed_widgets.append({
                "widget_id": w_id,
                "title": w_title,
                "type": "kpi",
                "status": "AVAILABLE",
                "value": kpi_val,
                "aggregation": agg_type
            })

        elif w_type == "chart":
            group_counts: Dict[str, float] = {}
            for r in records:
                r_data = json.loads(r["data"])
                if group_by == "state":
                    key = r["state"]
                else:
                    key = str(r_data.get(group_by, "Unspecified"))

                if agg_type == "count":
                    group_counts[key] = group_counts.get(key, 0) + 1
                elif agg_type == "sum" and metric_field:
                    val = float(r_data.get(metric_field, 0) or 0)
                    group_counts[key] = group_counts.get(key, 0) + val

            chart_data = [{"label": k, "value": v} for k, v in group_counts.items()]
            computed_widgets.append({
                "widget_id": w_id,
                "title": w_title,
                "type": "chart",
                "status": "AVAILABLE",
                "group_by": group_by,
                "metric": metric_cfg,
                "data": chart_data
            })

        elif w_type == "table":
            limit = w.get("limit", 5)
            table_items = []
            for r in records[:limit]:
                r_dict = {
                    "id": r["id"],
                    "state": r["state"],
                    "data": json.loads(r["data"])
                }
                table_items.append(FieldProjector.project_read_record(r_dict, field_perms))

            computed_widgets.append({
                "widget_id": w_id,
                "title": w_title,
                "type": "table",
                "status": "AVAILABLE",
                "items": table_items
            })

    return {
        "id": dash_row["id"],
        "title": dash_row["title"],
        "tenant_id": ctx.tenant_id,
        "widgets": computed_widgets
    }
