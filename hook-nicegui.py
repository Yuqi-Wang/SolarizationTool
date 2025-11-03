# hook-nicegui.py
from PyInstaller.utils.hooks import collect_data_files
datas = collect_data_files('nicegui', include_py_files=False)