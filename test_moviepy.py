import sys
print("Python version:", sys.version)
print("Python path:", sys.path)

try:
    import moviepy
    print("moviepy imported successfully")
    print("moviepy path:", moviepy.__file__)
    
    # Проверим содержимое пакета moviepy
    print("\nContents of moviepy package:")
    print(dir(moviepy))
    
    # Проверим, есть ли модуль editor
    if hasattr(moviepy, 'editor'):
        print("moviepy.editor exists as an attribute")
    else:
        print("moviepy.editor does not exist as an attribute")
    
    # Проверим, есть ли файл editor.py
    import os
    editor_path = os.path.join(os.path.dirname(moviepy.__file__), "editor.py")
    print(f"editor.py exists: {os.path.exists(editor_path)}")
    
    # Проверим другие возможные пути
    init_path = os.path.join(os.path.dirname(moviepy.__file__), "editor", "__init__.py")
    print(f"editor/__init__.py exists: {os.path.exists(init_path)}")
    
except ImportError as e:
    print("Error importing moviepy:", e)