Aplicación web desarrollada en **Django**, optimizada para uso en escritorio y dispositivos móviles (enfoque *mobile-first*), diseñada para administrar el inventario de repuestos de refrigeración, salidas de bodega, cotizaciones comerciales en PDF y órdenes de servicio técnico.
## Características Principales

* **Control de Inventario de Repuestos:**
  * Registro de productos con fotografía (vista previa instantánea y captura directa desde cámara móvil), descripción técnica, existencias y precio en Quetzales (`Q`).
  * Edición completa de repuestos y bajas lógicas (`activo=False`) para conservar el historial de movimientos sin comprometer la integridad referencial.
  * Consultor rápido de precios de mostrador (`F2` en escritorio) con búsqueda instantánea en tiempo real.
* **Descarga de Inventario y Auditoría de Salidas:**
  * Descuento simultáneo de múltiples repuestos mediante transacciones atómicas (`transaction.atomic`) con validación de stock y bloqueo de concurrencia (`select_for_update`).
  * Asociación a clientes registrados o consumidores eventuales, cálculo automático de costos y bitácora completa filtrable con acceso directo al detalle de órdenes técnicas vinculadas.
* **Generador de Cotizaciones en PDF:**
  * Autocompletado de repuestos del catálogo o ingreso de ítems personalizados (servicios/mano de obra), cálculo de subtotales en vivo y exportación inmediata en PDF con **ReportLab**.
  * Historial de cotizaciones con vista previa desplegable y re-descarga de PDF.
* **Clientes y Taller de Servicio Técnico:**
  * Gestión de órdenes técnicas por pestañas (*Órdenes de Taller* y *Directorio de Clientes*), cambio rápido de estado (`Pendiente`, `En reparación`, `Completado`, `Cancelado`) y carga directa de repuestos consumidos (descontados automáticamente de bodega) más costo opcional de mano de obra.
  * Emisión de **Constancia Digital de Reparación y Entrega en PDF** optimizada para envío por WhatsApp, además de integración directa con WhatsApp Web/móvil para contacto con clientes.

---

## Stack Tecnológico

* **Backend:** Python 3, Django (ORM, Auth, Transactions)
* **Base de Datos:** SQLite3 (desarrollo)
* **Frontend:** HTML5, CSS3 (variables personalizadas, diseño responsivo), JavaScript Vanilla (filtros en tiempo real, modales, clonación dinámica de filas y autocompletado)
* **Generación de Documentos:** ReportLab & Pillow

---

## Estructura del Proyecto

```text
InventarioChomin/
├── InventarioChomin/       # Configuración principal del proyecto Django (settings, urls, wsgi)
├── usuario/                # Módulo de autenticación y control de acceso
├── inventario/             # Módulo principal: modelos, vistas, URLs y plantillas
│   ├── migrations/
│   └── templates/inventario/
├── static/                 # Hojas de estilo (theme.css, login.css) y scripts (app.js)
├── manage.py
├── requirements.txt
└── .gitignore
git clone https://github.com/MelvinGTE/InventarioRefrigeracion.git
cd inventario-chomin
python -m venv venv
# En Windows (Git Bash):
source venv/Scripts/activate
# En Linux / macOS:
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
Accede desde tu navegador en http://127.0.0.1:8000/.
