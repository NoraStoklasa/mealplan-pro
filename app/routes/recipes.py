from fastapi import APIRouter, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, FileResponse, PlainTextResponse
import tempfile
from pathlib import Path
from typing import List
from recipes.recipe_database import (
    create_recipe,
    load_recipe,
    add_recipe_ingredient,
    update_recipe,
    replace_recipe_ingredients,
    delete_recipe,
)
from ingredients.database import get_all_ingredient_names
from logic.recalculate_nutrients import recalculate_nutrients
from logic.scaled_recipe import scale_recipe_to_energy
from app.labels import LABELS
from app.routes.recipes_helpers import (
    fetch_recipes_by_category,
    group_recipes_by_category,
    ingredients_from_form,
    parse_float,
    targets_by_category as parse_targets_by_category,
)
from config import RECIPE_DB_PATH

router = APIRouter(prefix="/recipes")
templates = Jinja2Templates(directory="app/templates")


# Route to list all recipes from the database.
@router.get("")
def list_recipes(request: Request):
    recipes_by_category = fetch_recipes_by_category()

    return templates.TemplateResponse(
        "recipes_list.html",
        {
            "request": request,
            "recipes_by_category": recipes_by_category,
        },
    )


# Route to show meal plan selection (export).
@router.get("/meal-plan")
def meal_plan(request: Request):
    recipes_by_category = fetch_recipes_by_category()

    return templates.TemplateResponse(
        "meal_plan.html",
        {
            "request": request,
            "recipes_by_category": recipes_by_category,
        },
    )


# Route to show the form for adding a new recipe.
@router.get("/new")
def new_recipe_form(request: Request):
    return templates.TemplateResponse(
        "recipe_form.html",
        {"request": request},
    )


# Route to handle the submission of a new recipe.
@router.post("/new")
def create_recipe_post(
    name: str = Form(...),
    category: str = Form(...),
    instructions: str = Form(...),
    image_path: str = Form(""),
):
    recipe_id = create_recipe(
        name=name,
        category=category,
        instructions=instructions,
        image_path=image_path,
    )

    return RedirectResponse(
        url=f"/recipes/{recipe_id}/edit",
        status_code=303,
    )


@router.post("/export")
def export_recipes(request: Request, recipe_ids: str = Form("")):
    ids = []
    for rid in recipe_ids.split(","):
        rid = rid.strip()
        if not rid:
            continue
        try:
            ids.append(int(rid))
        except ValueError:
            continue
    recipes = []
    for rid in ids:
        recipe = load_recipe(rid)
        if not recipe:
            continue
        nutrients = recalculate_nutrients(recipe)
        recipes.append(
            {
                "id": rid,
                "energy_kj": nutrients.get("energy_kj", 0) or 0,
                **recipe,
            }
        )
    recipes_by_category = group_recipes_by_category(
        recipes, lambda r: r["category"], lambda r: r["name"]
    )

    return templates.TemplateResponse(
        "recipes_export.html",
        {
            "request": request,
            "recipes_by_category": recipes_by_category,
            "lang": "en",
        },
    )


@router.post("/export/scale")
async def scale_selected_recipes(request: Request):
    form = await request.form()
    recipe_ids = form.getlist("recipe_ids")
    client_name = form.get("client_name") or ""
    lang = form.get("lang") or "en"
    labels = LABELS.get(lang, LABELS["en"])
    targets_by_category = parse_targets_by_category(form)
    recipes = []
    for rid_value in recipe_ids:
        try:
            rid = int(rid_value)
        except ValueError:
            continue
        recipe = load_recipe(rid)
        if recipe:
            recipes.append((rid, recipe))

    scaled_recipes = []
    for rid, recipe in recipes:
        category = recipe.get("category", "")
        recipe_target = parse_float(form.get(f"target_kj_recipe_{rid}"))
        target_kj = recipe_target or (targets_by_category.get(category, 0) or 0)
        if target_kj > 0:
            scaled_recipe, scaled_nutrients = scale_recipe_to_energy(recipe, target_kj)
        else:
            scaled_recipe = recipe
            scaled_nutrients = recalculate_nutrients(recipe)
        scaled_recipes.append(
            {
                "recipe_id": rid,
                "recipe": scaled_recipe,
                "nutrients": scaled_nutrients,
                "category": category,
            }
        )
    return templates.TemplateResponse(
        "recipes_scaled_preview.html",
        {
            "request": request,
            "scaled_recipes": scaled_recipes,
            "targets_by_category": targets_by_category,
            "client_name": client_name,
            "labels": labels,
            "lang": lang,
            "error": None,
        },
    )


@router.post("/export/preview-update")
async def update_preview(request: Request):
    form = await request.form()
    recipe_ids = form.getlist("recipe_ids")
    client_name = form.get("client_name") or ""
    lang = form.get("lang") or "en"
    labels = LABELS.get(lang, LABELS["en"])
    targets_by_category = parse_targets_by_category(form)

    scaled_recipes = []
    for rid_value in recipe_ids:
        try:
            rid = int(rid_value)
        except ValueError:
            continue
        recipe = load_recipe(rid)
        if not recipe:
            continue
        recipe["ingredients"] = ingredients_from_form(form, rid)
        nutrients = recalculate_nutrients(recipe)
        scaled_recipes.append(
            {
                "recipe_id": rid,
                "recipe": recipe,
                "nutrients": nutrients,
                "category": recipe.get("category", ""),
            }
        )

    return templates.TemplateResponse(
        "recipes_scaled_preview.html",
        {
            "request": request,
            "scaled_recipes": scaled_recipes,
            "targets_by_category": targets_by_category,
            "client_name": client_name,
            "labels": labels,
            "lang": lang,
            "error": None,
        },
    )


@router.post("/export/docx")
async def export_docx(request: Request):
    try:
        from docx import Document
    except ModuleNotFoundError:
        return PlainTextResponse(
            "python-docx is not installed. Run: pip install python-docx",
            status_code=500,
        )

    form = await request.form()
    recipe_ids = form.getlist("recipe_ids")
    client_name = (form.get("client_name") or "").strip()
    lang = form.get("lang") or "en"
    labels = LABELS.get(lang, LABELS["en"])

    recipes = []
    for rid_value in recipe_ids:
        try:
            rid = int(rid_value)
        except ValueError:
            continue
        recipe = load_recipe(rid)
        if not recipe:
            continue
        recipe["ingredients"] = ingredients_from_form(form, rid)
        nutrients = recalculate_nutrients(recipe)
        recipes.append({"recipe": recipe, "nutrients": nutrients})

    doc = Document()
    doc.add_heading(labels["export_title"], level=1)
    if client_name:
        doc.add_paragraph(f"{labels['client']}: {client_name}")

    for item in recipes:
        recipe = item["recipe"]
        nutrients = item["nutrients"]
        doc.add_heading(recipe.get("name", "Recipe"), level=2)
        doc.add_paragraph(f"Category: {recipe.get('category', '')}")

        image_path = recipe.get("image_path")
        if image_path and Path(image_path).exists():
            try:
                doc.add_picture(image_path, width=None)
            except Exception:
                pass

        doc.add_paragraph(f"{labels['ingredients']}:")
        for ing in recipe.get("ingredients", []):
            doc.add_paragraph(
                f"- {ing.get('name', '')} – {ing.get('portion_g', 0)} g",
                style="List Bullet",
            )

        instructions = recipe.get("instructions") or ""
        if instructions:
            doc.add_paragraph(f"{labels['instructions']}:")
            doc.add_paragraph(instructions)

        doc.add_paragraph(f"{labels['nutrition_summary']}:")
        doc.add_paragraph(f"{labels['energy']}: {nutrients['energy_kj']} kJ")
        doc.add_paragraph(f"{labels['protein']}: {nutrients['protein_g']} g")
        doc.add_paragraph(f"{labels['carbs']}: {nutrients['carbs_g']} g")
        doc.add_paragraph(f"{labels['fat']}: {nutrients['fat_g']} g")
        doc.add_paragraph(f"{labels['fibre']}: {nutrients['fibre_g']} g")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        temp_path = tmp.name
    doc.save(temp_path)

    return FileResponse(
        temp_path,
        filename="mealplan_pro_export.docx",
        media_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
    )


# Route to show the details of a specific recipe.
@router.get("/{recipe_id}")
def recipe_detail(request: Request, recipe_id: int):
    recipe = load_recipe(recipe_id)
    if not recipe:
        return RedirectResponse(url="/recipes", status_code=303)
    ingredients = get_all_ingredient_names()

    nutrients = recalculate_nutrients(recipe)

    return templates.TemplateResponse(
        "recipe_detail.html",
        {
            "request": request,
            "recipe_id": recipe_id,
            "recipe": recipe,
            "ingredients": ingredients,
            "nutrients": nutrients,
        },
    )


@router.get("/{recipe_id}/edit")
def edit_recipe_form(request: Request, recipe_id: int):
    recipe = load_recipe(recipe_id)
    if not recipe:
        return RedirectResponse(url="/recipes", status_code=303)
    return templates.TemplateResponse(
        "recipe_edit.html",
        {
            "request": request,
            "recipe_id": recipe_id,
            "recipe": recipe,
        },
    )


# Route to handle adding an ingredient to a specific recipe
@router.post("/{recipe_id}")
def add_ingredient_to_recipe(
    recipe_id: int,
    ingredient_name: str = Form(...),
    portion_g: float = Form(...),
):
    add_recipe_ingredient(
        recipe_id=recipe_id,
        ingredient_name=ingredient_name,
        portion_g=portion_g,
    )

    return RedirectResponse(
        url=f"/recipes/{recipe_id}",
        status_code=303,
    )


@router.post("/{recipe_id}/edit")
def update_recipe_post(
    recipe_id: int,
    name: str = Form(...),
    category: str = Form(...),
    instructions: str = Form(...),
    image_path: str = Form(""),
    ingredient_name: List[str] = Form([]),
    portion_g: List[str] = Form([]),
):
    update_recipe(
        recipe_id=recipe_id,
        name=name,
        category=category,
        instructions=instructions,
        image_path=image_path,
    )
    ingredients = []
    for name_value, portion_value in zip(ingredient_name, portion_g):
        name_value = (name_value or "").strip()
        if not name_value:
            continue
        try:
            portion = float(portion_value)
        except (TypeError, ValueError):
            continue
        if portion <= 0:
            continue
        ingredients.append({"name": name_value, "portion_g": portion})
    replace_recipe_ingredients(recipe_id, ingredients)

    return RedirectResponse(
        url=f"/recipes/{recipe_id}",
        status_code=303,
    )


@router.post("/{recipe_id}/delete")
def delete_recipe_post(recipe_id: int):
    delete_recipe(recipe_id)
    return RedirectResponse(url="/recipes", status_code=303)
