from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.routes.ingredients import router as ingredients_router
from app.routes.recipes import router as recipes_router


app = FastAPI(title="MealPlan Pro")

templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "hide_home": True},
    )


# Registering routers
app.include_router(ingredients_router)
app.include_router(recipes_router)
