from fastapi import FastAPI, File, Form, UploadFile, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Optional
from PyPDF2 import PdfReader
import io

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

PT_PER_INCH = 72.0
MM_PER_INCH = 25.4
def mm_to_pt(mm: float) -> float:
    return mm * PT_PER_INCH / MM_PER_INCH

# Trim sizes (width, height) in mm
TRIM_SIZES_MM = {
    "A5": (148.0, 210.0),
    "B5": (176.0, 250.0),
    "A4": (210.0, 297.0),
}

# Paper thickness (mm per page)
PAPER_THICKNESS_MM = {
    "נטול עץ לבן 70": 0.09,
    "נטול עץ לבן 80": 0.10,
    "נטול עץ לבן 90": 0.13,
    "נטול עץ לבן 110": 0.15,
    "נטול עץ קרם 70": 0.09,
    "נטול עץ קרם 80": 0.10,
    "נטול עץ קרם 90": 0.13,
    "נטול עץ קרם 110": 0.15,
    "כרומו מט 105": 0.10,
    "כרומו מט 115": 0.11,
    "כרומו מט 130": 0.125,
    "כרומו מט 170": 0.16,
}

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "trim_sizes": TRIM_SIZES_MM.keys(),
            "paper_types": PAPER_THICKNESS_MM.keys(),
        },
    )

def read_pdf_first_page_size_pts(pdf_bytes: bytes):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    if len(reader.pages) == 0:
        raise ValueError("ה-PDF ריק.")
    page = reader.pages[0]
    mediabox = page.mediabox
    width = float(mediabox.right - mediabox.left)
    height = float(mediabox.top - mediabox.bottom)
    return width, height, len(reader.pages)

def near(a: float, b: float, tol: float = 1.0) -> bool:
    # tolerance in points (~0.35 mm)
    return abs(a - b) <= tol

@app.post("/validate", response_class=HTMLResponse)
async def validate(
    request: Request,
    content_pdf: UploadFile = File(...),
    cover_pdf: UploadFile = File(...),
    trim: str = Form(...),
    bleed_mm: float = Form(...),
    paper_type: str = Form(...),
    content_pages: Optional[int] = Form(None)
):
    errors = []
    warnings = []
    checks = []

    if trim not in TRIM_SIZES_MM:
        errors.append(f"גדל גזירה לא נתמך: {trim}")
    if paper_type not in PAPER_THICKNESS_MM:
        errors.append(f"סוג נייר לא נתמך: {paper_type}")
    if errors:
        return templates.TemplateResponse(
            "result.html",
            {"request": request, "errors": errors, "warnings": warnings, "checks": checks},
        )

    trim_w_mm, trim_h_mm = TRIM_SIZES_MM[trim]
    spine_mm_per_page = PAPER_THICKNESS_MM[paper_type]

    # Content PDF
    content_bytes = await content_pdf.read()
    try:
        c_w_pt, c_h_pt, c_pages = read_pdf_first_page_size_pts(content_bytes)
    except Exception as e:
        errors.append(f"שגיאה בקריאת PDF התוכן: {e}")

    # Cover PDF
    cover_bytes = await cover_pdf.read()
    try:
        k_w_pt, k_h_pt, k_pages = read_pdf_first_page_size_pts(cover_bytes)
    except Exception as e:
        errors.append(f"שגיאה בקריאת PDF הכריכה: {e}")

    if errors:
        return templates.TemplateResponse(
            "result.html",
            {"request": request, "errors": errors, "warnings": warnings, "checks": checks},
        )

    pages = content_pages if (content_pages and content_pages > 0) else c_pages
    if pages != c_pages:
        warnings.append(f"מס' עמודים שסופק ({pages}) שונה ממספר העמודים ב-PDF ({c_pages}). נחשב לפי {pages}.")

    bleed_pt = mm_to_pt(bleed_mm)
    trim_w_pt = mm_to_pt(trim_w_mm)
    trim_h_pt = mm_to_pt(trim_h_mm)
    expected_content_w_pt = trim_w_pt + 2 * bleed_pt
    expected_content_h_pt = trim_h_pt + 2 * bleed_pt

    if not near(c_w_pt, expected_content_w_pt) or not near(c_h_pt, expected_content_h_pt):
        errors.append(
            f"ממד עמודי התוכן לא תואם. צפוי ~{round(expected_content_w_pt)}×{round(expected_content_h_pt)}pt "
            f"(trim {trim} + bleed {bleed_mm} מ\"מ), בפועל {round(c_w_pt)}×{round(c_h_pt)}pt."
        )
    else:
        checks.append("תוכן: המידות תואמות את ה-trim וה-bleed שנבחרו.")

    if pages % 2 != 0:
        warnings.append("מומלץ שמספר העמודים יהיה זוגי (שיקולי חתימות/עימוד).")

    # Spine & cover
    spine_mm = pages * spine_mm_per_page
    expected_cover_w_pt = mm_to_pt(2 * trim_w_mm + spine_mm + 2 * bleed_mm)
    expected_cover_h_pt = mm_to_pt(trim_h_mm + 2 * bleed_mm)

    if k_pages != 1:
        warnings.append(f"כריכה: מומלץ קובץ בעמוד אחד (קדמי+שדרה+אחורי). זוהו {k_pages} עמודים.")

    if not near(k_w_pt, expected_cover_w_pt) or not near(k_h_pt, expected_cover_h_pt):
        errors.append(
            f"כריכה: המידות אינן תואמות. צפוי ~{round(expected_cover_w_pt)}×{round(expected_cover_h_pt)}pt "
            f"(2×trim + spine({spine_mm:.2f} מ\"מ) + 2×bleed), בפועל {round(k_w_pt)}×{round(k_h_pt)}pt."
        )
    else:
        checks.append(f"כריכה: המידות תקינות. שדרה מחושבת ≈ {spine_mm:.2f} מ\"מ.")

    warnings.append("ודא/י ייצוא PDF 'שטוח' וללא שכבות, ללא סימני חיתוך, וכל הפונטים סגורים/מוטמעים.")
    warnings.append("אם יש הדפסה פנימית על הכריכה, השאר/י מקום לברקוד 1.5×4 ס\"מ בצד השמאלי הפנימי.")

    return templates.TemplateResponse(
        "result.html",
        {
            "request": request,
            "errors": errors,
            "warnings": warnings,
            "checks": checks,
            "summary": {
                "trim": trim,
                "bleed_mm": bleed_mm,
                "paper_type": paper_type,
                "pages": pages,
                "spine_mm": round(spine_mm, 2),
            },
        },
    )
