import os

MODULE_PATHS = []
for root, _, _ in os.walk(".\\src\\ext"):
    # pylint: disable=cell-var-from-loop
    module_root = root.replace("\\", ".").strip(".")

    module_names = filter(
        lambda p: p.endswith(".py") and not p.startswith("_"), os.listdir(root)
    )

    #
    modules_absolute = map(lambda p: f"{module_root}.{p[:-3]}", module_names)

    MODULE_PATHS.extend(modules_absolute)
