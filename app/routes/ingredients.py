from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import sqlite3

from ingredients.manual_ingredient import add_ingredient_manually
from ingredients.database import search_ingredient_names
from ingredients.ingredients import (
    search_ingredient,
    extract_nutrients,
    extract_portion,
)

from config import DB_PATH

router = APIRouter(prefix="/ingredients")
templates = Jinja2Templates(directory="app/templates")


# Route to list all ingredients from the database
@router.get("")
def list_ingredients(request: Request):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM ingredients ORDER by lower(name)")
        ingredients = cursor.fetchall()
    return templates.TemplateResponse(
        "ingredients_list.html", {"request": request, "ingredients": ingredients}
    )


# Route to show the form for adding a new ingredient
@router.get("/new")
def new_ingredient_form(request: Request):
    return templates.TemplateResponse("ingredient_form.html", {"request": request})


# Route to handle the submission of a new ingredient
@router.post("/new")
def create_ingredient(
    name: str = Form(...),
    portion_g: float = Form(...),
    energy_kj: float = Form(...),
    protein_g: float = Form(...),
    carbs_g: float = Form(...),
    fat_g: float = Form(...),
    fibre_g: float = Form(...),
):
    add_ingredient_manually(
        name=name,
        portion_g=portion_g,
        energy_kj=energy_kj,
        protein_g=protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g,
        fibre_g=fibre_g,
    )

    return RedirectResponse(
        url="/ingredients",
        status_code=303,
    )


@router.get("/search")
def search_ingredients(q: str = ""):
    query = q.strip()
    if not query:
        return JSONResponse({"results": []})
    names = search_ingredient_names(query)
    return JSONResponse({"results": names})


@router.post("/autofill")
def autofill_ingredient(name: str = Form("")):
    query = name.strip()
    if not query:
        return JSONResponse({"found": False, "message": "Ingredient name is required."})
    try:
        food_data = search_ingredient(query)
    except Exception:
        return JSONResponse(
            {"found": False, "message": "Auto-fill failed. Enter values manually."}
        )
    if not food_data:
        return JSONResponse(
            {"found": False, "message": "No match found. Enter values manually."}
        )
    nutrients = extract_nutrients(food_data)
    portion_g = extract_portion(food_data)
    return JSONResponse(
        {
            "found": True,
            "portion_g": portion_g,
            "energy_kj": nutrients.get("energy_kj"),
            "protein_g": nutrients.get("protein_g"),
            "carbs_g": nutrients.get("carbs_g"),
            "fat_g": nutrients.get("fat_g"),
            "fibre_g": nutrients.get("fibre_g"),
        }
    )


@router.get("/{ingredient_id}")
def ingredient_detail(request: Request, ingredient_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT name, portion_g, energy_kj, protein_g, carbs_g, fat_g, fibre_g
            FROM ingredients
            WHERE id = ?
            """,
            (ingredient_id,),
        )
        row = cursor.fetchone()
    if not row:
        return RedirectResponse(url="/ingredients", status_code=303)
    ingredient = {
        "name": row[0],
        "portion_g": row[1],
        "energy_kj": row[2],
        "protein_g": row[3],
        "carbs_g": row[4],
        "fat_g": row[5],
        "fibre_g": row[6],
    }
    return templates.TemplateResponse(
        "ingredient_detail.html",
        {"request": request, "ingredient": ingredient},
    )


@router.post("/{ingredient_id}")
def update_ingredient(
    ingredient_id: int,
    name: str = Form(...),
    portion_g: float = Form(...),
    energy_kj: float = Form(...),
    protein_g: float = Form(...),
    carbs_g: float = Form(...),
    fat_g: float = Form(...),
    fibre_g: float = Form(...),
):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE ingredients
            SET name = ?, portion_g = ?, energy_kj = ?, protein_g = ?,
                carbs_g = ?, fat_g = ?, fibre_g = ?
            WHERE id = ?
            """,
            (
                name.strip(),
                portion_g,
                energy_kj,
                protein_g,
                carbs_g,
                fat_g,
                fibre_g,
                ingredient_id,
            ),
        )
    return RedirectResponse(url=f"/ingredients/{ingredient_id}", status_code=303)
