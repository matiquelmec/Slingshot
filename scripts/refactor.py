import os
import re

ENGINE_DIR = r"c:\Users\Matías Riquelme\Desktop\Proyectos documentados\Slingshot_Trading\engine"

# Regex para buscar print( y reemplazar por logger.info(
print_pattern = re.compile(r'\bprint\s*\(')

# Plantillas de importaciones extra necesarias
import_logging = "from engine.core.logger import logger\n"

def process_file(filepath):
    # Algunos archivos como logger.py se ignoran
    if filepath.endswith("logger.py") or filepath.endswith("refactor.py"):
        return

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Si no hay print, no tocar
    if not print_pattern.search(content):
        return

    # Si ya tiene el import de logger, check. Si no, añadir al principio de los imports
    lines = content.splitlines()
    has_logger = any("from engine.core.logger import logger" in line for line in lines)
    
    new_lines = []
    import_inserted = has_logger
    
    for i, line in enumerate(lines):
        # Insertar import_logging después de los imports (o al inicio seguro si no lo hay)
        if not import_inserted and (line.startswith("import ") or line.startswith("from ")):
            # Vamos a ignorar para insertar el logger. Simplemente lo metemos en la lista.
            new_lines.append(import_logging.strip())
            import_inserted = True
            
        # Transformar prints
        # Esto es un poco bruto pero funciona: print( -> logger.info(
        # Convertiremos todo a info() a menos que diga error o warning
        if "print(" in line:
            if "error" in line.lower() or "falló" in line.lower() or "failed" in line.lower():
                line = line.replace("print(", "logger.error(")
            elif "warning" in line.lower()  or "precaución" in line.lower():
                line = line.replace("print(", "logger.warning(")
            else:
                line = line.replace("print(", "logger.info(")
        
        new_lines.append(line)
        
    if not import_inserted:
        new_lines.insert(0, import_logging.strip())
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("\n".join(new_lines) + "\n")
    print(f"Refactorizado: {filepath}")

for root, _, files in os.walk(ENGINE_DIR):
    for file in files:
        if file.endswith(".py"):
            process_file(os.path.join(root, file))

print("Terminado.")
