# Recipe Template

Copy this directory when adding a new notebook-based example:

```bash
cp -r examples/TEMPLATE examples/my-new-recipe
cd examples/my-new-recipe
mv TEMPLATE.ipynb my_new_recipe.ipynb   # use snake_case matching the dir name
```

Then edit the notebook and README. Validate locally before opening a PR:

```bash
python scripts/validate_recipe.py examples/my-new-recipe
```

See [CONTRIBUTING.MD](../../CONTRIBUTING.MD) for the full standards checklist.
