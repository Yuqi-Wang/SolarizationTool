import pathlib, sys
bad=[]
for p in pathlib.Path('.').rglob('*.py'):
    try:
        b = p.read_bytes()
    except Exception as e:
        print("READ ERROR", p, e)
        continue
    if b'\x00' in b:
        bad.append(p)
if bad:
    print("NUL bytes found in:")
    for p in bad: print(" -", p)
    sys.exit(1)
else:
    print("No NUL bytes in *.py files.")