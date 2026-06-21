import os
import sys
import django

# 1. Ajustar el Path al directorio raíz de tu proyecto
path = '/home/proyectoafmgde/proyectoafmgde'
if path not in sys.path:
    sys.path.append(path)

# 2. Inicializar el entorno de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

# 3. Importaciones de tus modelos específicos
from django.db import connection
from stability.models import Chamber, StorageCondition

def vaciar_tablas_maestras():
    print("Iniciando el vaciado forzado de tablas maestras...")
    
    with connection.cursor() as cursor:
        # Desactivamos restricciones de integridad en SQLite temporalmente
        print("- Desactivando verificación de restricciones (FOREIGN KEY)...")
        cursor.execute('PRAGMA foreign_keys = OFF;')
        
        try:
            # Vaciado en crudo de Chamber (se salta las señales de audit)
            print("- Eliminando todos los registros de Chamber...")
            Chamber.objects.all()._raw_delete(using='default')
            print("  -> Tabla Chamber vaciada.")
            
            # Vaciado en crudo de StorageCondition
            print("- Eliminando todos los registros de StorageCondition...")
            StorageCondition.objects.all()._raw_delete(using='default')
            print("  -> Tabla StorageCondition vaciada.")
            
            print("\n[ÉXITO] Ambas tablas se han limpiado por completo.")
            
        except Exception as e:
            print(f"\n[ERROR] Ocurrió un fallo inesperado: {e}")
            
        finally:
            # Reactivamos las restricciones para mantener la BD íntegra y segura
            print("- Reactivando verificación de restricciones (FOREIGN KEY)...")
            cursor.execute('PRAGMA foreign_keys = ON;')

if __name__ == '__main__':
    vaciar_tablas_maestras()