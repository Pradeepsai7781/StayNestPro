
import csv
from datetime import date
from io import BytesIO, StringIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models import User, UserRole
from app.services.report_service import (
    REPORT_TYPES,
    get_report_data,
)


router = APIRouter(
    prefix="/reports",
    tags=["Reports and Export"],
)


def require_admin(current_user: User) -> None:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Only administrators can export platform reports.",
        )


def _get_columns(report_type: str) -> list[str]:
    columns = {
        "bookings": [
            "reservation_id",
            "booking_reference",
            "customer_id",
            "customer_name",
            "hotel_id",
            "hotel_name",
            "room_id",
            "check_in",
            "check_out",
            "guest_count",
            "total_price",
            "status",
            "created_at",
        ],
        "revenue": [
            "period_start",
            "period_end",
            "booking_revenue",
            "service_revenue",
            "total_revenue",
            "total_refunds",
            "net_revenue",
            "successful_booking_count",
            "average_booking_value",
        ],
        "occupancy": [
            "date",
            "total_rooms",
            "occupied_rooms",
            "available_rooms",
            "unavailable_rooms",
            "occupancy_rate",
            "booking_count",
        ],
        "customers": [
            "customer_id",
            "customer_name",
            "booking_frequency",
            "total_spending",
            "average_spending",
            "is_repeat_customer",
        ],
        "hotels": [
            "hotel_id",
            "hotel_name",
            "owner_id",
            "city",
            "state",
            "country",
            "property_type",
            "status",
            "is_reported",
            "created_at",
        ],
        "payments": [
            "payment_id",
            "reservation_id",
            "booking_reference",
            "customer_id",
            "customer_name",
            "amount",
            "currency",
            "status",
            "created_at",
        ],
    }
    return columns[report_type]


def _create_csv(rows: list[dict], columns: list[str]) -> BytesIO:
    text_buffer = StringIO()
    writer = csv.DictWriter(
        text_buffer,
        fieldnames=columns,
        extrasaction="ignore",
    )
    writer.writeheader()
    writer.writerows(rows)

    buffer = BytesIO(text_buffer.getvalue().encode("utf-8-sig"))
    buffer.seek(0)
    return buffer


def _create_excel(rows: list[dict], columns: list[str]) -> BytesIO:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Report"

    worksheet.append(columns)

    for cell in worksheet[1]:
        cell.font = Font(bold=True)

    for row in rows:
        worksheet.append([row.get(column, "") for column in columns])

    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions

    for column_cells in worksheet.columns:
        column_letter = column_cells[0].column_letter
        max_length = max(
            len(str(cell.value or ""))
            for cell in column_cells
        )
        worksheet.column_dimensions[column_letter].width = min(
            max(max_length + 2, 12),
            35,
        )

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer


def _create_pdf(rows: list[dict], columns: list[str]) -> BytesIO:
    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=20,
        leftMargin=20,
        topMargin=24,
        bottomMargin=24,
    )

    table_data = [
        columns,
        *[
            [str(row.get(column, "")) for column in columns]
            for row in rows
        ],
    ]

    table = Table(
        table_data,
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    document.build([table])
    buffer.seek(0)
    return buffer


@router.get("/export")
def export_report(
    report_type: str = Query(...),
    start_date: date = Query(...),
    end_date: date = Query(...),
    file_format: str = Query(..., alias="format"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    if report_type not in REPORT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=(
                "Invalid report_type. Choose bookings, revenue, "
                "occupancy, customers, hotels, or payments."
            ),
        )

    if file_format not in {"csv", "xlsx", "pdf"}:
        raise HTTPException(
            status_code=422,
            detail="Invalid format. Choose csv, xlsx, or pdf.",
        )

    try:
        rows = get_report_data(
            db=db,
            report_type=report_type,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    columns = _get_columns(report_type)

    if file_format == "csv":
        buffer = _create_csv(rows, columns)
        media_type = "text/csv"
        extension = "csv"
    elif file_format == "xlsx":
        buffer = _create_excel(rows, columns)
        media_type = (
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
        extension = "xlsx"
    else:
        buffer = _create_pdf(rows, columns)
        media_type = "application/pdf"
        extension = "pdf"

    filename = (
        f"{report_type}_report_{start_date}_{end_date}.{extension}"
    )

    return StreamingResponse(
        buffer,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )
