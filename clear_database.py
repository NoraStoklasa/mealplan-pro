#!/usr/bin/env python3
"""
Script to delete all ingredients and recipes from the database.
WARNING: This is destructive and cannot be undone!
"""

import sqlite3
from config import DB_PATH, RECIPE_DB_PATH

print("⚠️  WARNING: This will DELETE all ingredients and recipes!")
confirm = input("Type 'YES' to confirm: ").strip()

if confirm != "YES":
    print("Cancelled.")
    exit()

# Clear ingredients
print("Deleting all ingredients...")
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("DELETE FROM ingredients")
conn.commit()
conn.close()
print("✓ Ingredients cleared")

# Clear recipes and recipe_ingredients
print("Deleting all recipes...")
conn = sqlite3.connect(RECIPE_DB_PATH)
cur = conn.cursor()
cur.execute("DELETE FROM recipe_ingredients")
cur.execute("DELETE FROM recipes")
conn.commit()
conn.close()
print("✓ Recipes cleared")

print("\n✅ All data deleted!")
