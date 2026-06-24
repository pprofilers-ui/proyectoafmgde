import os

def consolidar_archivos():
    # 1. Obtener la ruta donde se está ejecutando el script
    directorio_actual = os.getcwd()
    
    # 2. Obtener el nombre de la carpeta raíz (ej. "CotizadorBack")
    nombre_carpeta = os.path.basename(directorio_actual)
    
    # 3. Construir la ruta hacia la carpeta "Descargas" del usuario en Windows/Mac/Linux
    ruta_descargas = os.path.join(os.path.expanduser('~'), 'Downloads')
    
    # 4. Crear la ruta final del archivo de texto (.txt)
    archivo_salida = os.path.join(ruta_descargas, f"{nombre_carpeta}.txt")
    
    print(f"Generando archivo en: {archivo_salida}")
    
    # Carpetas que probablemente no quieras volcar a texto (para que el archivo no sea gigante)
    directorios_ignorados = {'.git', '.vscode', 'bin', 'obj', 'node_modules', 'packages', 'venv'}
    # Extensiones de archivos binarios que no se pueden leer como texto
    extensiones_ignoradas = {'.dll', '.exe', '.png', '.jpg', '.pdf', '.zip', '.pyc'}

    # Abrimos el archivo en modo 'w' para sobrescribirlo siempre que se ejecute
    with open(archivo_salida, 'w', encoding='utf-8') as f_out:
        
        for raiz, directorios, archivos in os.walk(directorio_actual):
            # Filtramos las carpetas ignoradas para no entrar en ellas
            directorios[:] = [d for d in directorios if d not in directorios_ignorados]
            
            for archivo in archivos:
                # Evitar que el propio script se lea a sí mismo si se llama generador.py
                if archivo == os.path.basename(__file__):
                    continue
                    
                _, extension = os.path.splitext(archivo)
                if extension.lower() in extensiones_ignoradas:
                    continue
                    
                ruta_completa = os.path.join(raiz, archivo)
                
                try:
                    # Leemos el contenido del archivo
                    with open(ruta_completa, 'r', encoding='utf-8') as f_in:
                        contenido = f_in.read()
                        
                    # Escribimos con la estructura solicitada
                    f_out.write(f"{ruta_completa}\n")
                    f_out.write("----\n")
                    f_out.write(f"{contenido}\n")
                    f_out.write("----\n\n")
                    
                except UnicodeDecodeError:
                    # Si el archivo es binario y no estaba en la lista de ignorados
                    f_out.write(f"{ruta_completa}\n")
                    f_out.write("----\n")
                    f_out.write("[El contenido de este archivo es binario y no se puede leer como texto]\n")
                    f_out.write("----\n\n")
                    
                except Exception as e:
                    # Si hay algún problema de permisos u otro error
                    f_out.write(f"{ruta_completa}\n")
                    f_out.write("----\n")
                    f_out.write(f"[Error al intentar leer el archivo: {e}]\n")
                    f_out.write("----\n\n")
                    
    print(f"¡Listo! Revisa tu carpeta de Descargas, se ha creado el archivo {nombre_carpeta}.txt")

if __name__ == "__main__":
    consolidar_archivos()