set folder=".\profiles"
if not exist %folder% mkdir %folder%

.\venv\Scripts\python3.14t.exe -m cProfile -o profiles\start.prof start.py
