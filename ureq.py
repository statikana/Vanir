import os


with open("req.txt", "rb") as f:
    for line in f:
        if not f:
            continue
        s = line.decode("utf-8", errors="ignore").strip("\n")
        print(f"'{s}' end")
        os.system("uv pip uninstall " + s)
