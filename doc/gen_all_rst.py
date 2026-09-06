import os

SRC_ROOT = "avl"
RST_ROOT = "doc/source/modules"
TOP_MODULE = "avl"

def pyfile_to_modname(path):
    module_path, _ = os.path.splitext(path)
    return module_path.replace(os.sep, ".").replace("/", ".").replace("\\", ".")

def should_include(file):
    return file.endswith(".py") and not file.startswith("__")

def main():
    all_mods = []

    for dirpath, _, filenames in os.walk(SRC_ROOT):
        for fname in filenames:
            if should_include(fname):
                full_path = os.path.join(dirpath, fname)
                rel_path, _ = os.path.splitext(os.path.relpath(full_path, start="."))
                modname = pyfile_to_modname(rel_path)
                all_mods.append(modname)

                # Write .rst file
                rst_path = os.path.join(RST_ROOT, f"{modname}.rst")
                os.makedirs(os.path.dirname(rst_path), exist_ok=True)

                with open(rst_path, "w") as f:
                    f.write(f"""{modname} module
{'=' * (len(modname) + 7)}

.. automodule:: {modname}
   :members:
   :undoc-members:
""")

    # Write a toctree index you can include in index.rst
    toctree_path = os.path.join(RST_ROOT, "all_modules.rst")
    with open(toctree_path, "w") as f:
        f.write(f"""All Modules
============

.. toctree::
   :maxdepth: 2
   :caption: API Modules

""")
        for mod in sorted(all_mods):
            f.write(f"   {mod}\n")

    print(f"✅ Generated {len(all_mods)} .rst files in {RST_ROOT}")

if __name__ == "__main__":
    main()
