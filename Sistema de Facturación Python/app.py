from flask import Flask, render_template, request, redirect, url_for, send_file
from mysql.connector import connect, Error
from mysql.connector.cursor import MySQLCursorDict
import mysql.connector
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
import io

app = Flask(__name__)

# Configuración de la conexión a la base de datos
MYSQL_HOST = "viaduct.proxy.rlwy.net"
MYSQL_PORT = 47723
MYSQL_USER = "root"
MYSQL_PASSWORD = "tuDTbAoAjOIBSzzcOKScThPiHeUkKvaB"
MYSQL_DATABASE = "railway"

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE
        )
        return connection
    except Exception as e:
        print("Error al conectarse a MySQL:", e)
        return None

@app.route('/')
def index():
    connection = get_db_connection()
    if connection is not None:
        cursor = connection.cursor(dictionary=True)
        query = """
        SELECT FECHA_FACTURA as fecha_emision, 'Factura' as tipo, NUMERO_FACTURA as serie_numero, 
               C.NOMBRE as receptor, TOTAL
        FROM CABECERA_FACTURA CF
        JOIN CLIENTE C ON CF.RUC_CLIENTE = C.RUC_CLIENTE
        ORDER BY FECHA_FACTURA DESC;
        """
        cursor.execute(query)
        facturas = cursor.fetchall()
        cursor.close()
        connection.close()
        return render_template('index.html', data=facturas)
    else:
        return "Error al conectar con la base de datos"

def manejar_get_nuevo_comprobante(connection):
    if connection is not None:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT MAX(NUMERO_FACTURA) as ultimo_numero FROM CABECERA_FACTURA")
        resultado = cursor.fetchone()
        ultimo_numero = resultado['ultimo_numero'] if resultado['ultimo_numero'] is not None else 0
        siguiente_numero = ultimo_numero + 1

        cursor.execute("SELECT RUC_CLIENTE as id, NOMBRE FROM CLIENTE")
        clientes = cursor.fetchall()
        cursor.execute("SELECT CODIGO_ITEM as id, DESC_ITEM as descripcion FROM ARTICULOS")
        productos = cursor.fetchall()

        cursor.close()
        connection.close()

        return render_template('nuevo_comprobante.html', clientes=clientes, productos=productos, siguiente_numero=siguiente_numero)
    else:
        return "Error al conectar con la base de datos", 500
    
#este no funca ##
# Este import te permitirá acceder a la función redirect y url_for
from flask import redirect, url_for

@app.route('/nuevo_comprobante', methods=['GET', 'POST'])
def nuevo_comprobante():
    connection = get_db_connection()
    if connection is None:
        return "Error de conexión a la base de datos", 500  # Más explícito para el error de DB

    if request.method == 'POST':
        cursor = None  # Inicializamos el cursor como None
        try:
            cursor = connection.cursor(dictionary=True)
            # Extracción de datos del formulario
            ruc_cliente = request.form['cliente']
            fecha_emision = request.form['fecha_emision']
            items = request.form.getlist('items[]')

            # Ejemplo de inserción inicial en la cabecera de la factura sin SUBTOTAL, IGV, ni TOTAL
            cursor.execute(
                "INSERT INTO CABECERA_FACTURA (FECHA_FACTURA, RUC_CLIENTE, CODIGO_VENDEDOR) VALUES (%s, %s, %s)",
                (fecha_emision, ruc_cliente, 1001)  # Asignando un vendedor por defecto
            )
            factura_id = cursor.lastrowid

            # Inserción de cada ítem en cuerpo_factura
            for item in items:
                cantidad, id_item, precio_unitario = item.split(',')
                cursor.execute(
                    "INSERT INTO CUERPO_FACTURA (NUMERO_FACTURA, CODIGO_ITEM, CANTIDAD, PRECIO_VENTA) VALUES (%s, %s, %s, %s)",
                    (factura_id, id_item, cantidad, precio_unitario)
                )

            # Calcular y actualizar la cabecera de la factura
            cursor.execute(
                "SELECT SUM(CANTIDAD * PRECIO_VENTA) AS TOTAL FROM CUERPO_FACTURA WHERE NUMERO_FACTURA = %s",
                (factura_id,)
            )
            total = cursor.fetchone()['TOTAL']
            if total is None:
                total = 0  # Asigna 0 si el total es None para evitar errores de cálculo

            igv = total * 18 / 118
            subtotal = total - igv

            cursor.execute(
                "UPDATE CABECERA_FACTURA SET SUBTOTAL = %s, IGV = %s, TOTAL = %s WHERE NUMERO_FACTURA = %s",
                (subtotal, igv, total, factura_id)
            )

            connection.commit()
            return redirect(url_for('index'))  # Asumiendo que 'index' es una función/ruta definida
        except Exception as e:
            if connection:
                connection.rollback()
            print("Error al procesar el formulario:", e)
            return "Error al procesar el formulario", 500
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
    else:
        # Si es una solicitud GET, obtén los clientes de la base de datos
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT RUC_CLIENTE as id, NOMBRE FROM CLIENTE")
        clientes = cursor.fetchall()
        cursor.close()

        # Renderiza el template y pasa la lista de clientes
        return render_template('nuevo_comprobante.html', clientes=clientes)


""" @app.route('/nuevo_comprobante', methods=['GET', 'POST'])
def nuevo_comprobante():
    connection = get_db_connection()
    if request.method == 'POST' and connection is not None:
        try:
            cursor = connection.cursor(cursor_class=MySQLCursorDict)  # Usando cursor que soporta acceso por nombre de columna
            # Extracción de datos del formulario
            ruc_cliente = request.form['cliente']
            serie = request.form['serie']
            fecha_emision = request.form['fecha_emision']
            items = request.form.getlist('items[]')

            # Inserción inicial en la cabecera de la factura
            cursor.execute(
                "INSERT INTO CABECERA_FACTURA (FECHA_FACTURA, RUC_CLIENTE, CODIGO_VENDEDOR ) VALUES (%s, %s, %s)",
                (fecha_emision, ruc_cliente, 1001)  # Asignando un vendedor por defecto
            )
            factura_id = cursor.lastrowid

            # Inserción de cada ítem en cuerpo_factura
            for item in items:
                cantidad, id_item, precio_unitario = item.split(',')
                cursor.execute(
                    "INSERT INTO CUERPO_FACTURA (NUMERO_FACTURA, CODIGO_ITEM, CANTIDAD, PRECIO_VENTA) VALUES (%s, %s, %s, %s)",
                    (factura_id, id_item, cantidad, precio_unitario)
                )

            # Calcular y actualizar la cabecera de la factura
            cursor.execute(
                "SELECT SUM(CANTIDAD * PRECIO_VENTA) AS TOTAL FROM CUERPO_FACTURA WHERE NUMERO_FACTURA = %s",
                (factura_id,)  # Asegurando que se pasen como tuplas
            )
            total = cursor.fetchone()['TOTAL']  # Acceso como diccionario
            igv = total * 18 / 118
            subtotal = total - igv

            cursor.execute(
                "UPDATE CABECERA_FACTURA SET SUBTOTAL = %s, IGV = %s, TOTAL = %s WHERE NUMERO_FACTURA = %s",
                (subtotal, igv, total, factura_id)
            )
            
            connection.commit()
            return redirect(url_for('index'))
        except Exception as e:
            connection.rollback()
            print("Error al procesar el formulario:", e)
            return "Error al procesar el formulario", 500
        finally:
            cursor.close()
            connection.close()
    else:
        return manejar_get_nuevo_comprobante(connection) """
    
@app.route('/get_producto/<int:codigo_producto>')
def get_producto(codigo_producto):
    connection = get_db_connection()
    if connection is not None:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT PRECIO FROM ARTICULOS WHERE CODIGO_ITEM = %s", (codigo_producto,))
        producto = cursor.fetchone()
        cursor.close()
        connection.close()
        if producto:
            return {'precio': float(producto['PRECIO'])}
        else:
            return {'error': 'Producto no encontrado'}, 404
    return {'error': 'Error al conectar con la base de datos'}, 500

@app.route('/factura/<int:num_factura>')
def factura_pdf(num_factura):
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        try:
            # Obtener detalles de la cabecera de la factura
            cursor.execute("""
                SELECT CF.NUMERO_FACTURA, CF.FECHA_FACTURA, CF.SUBTOTAL, CF.IGV, CF.TOTAL,
                       CL.NOMBRE AS CLIENTE_NOMBRE, CL.RUC_CLIENTE,
                       VD.NOMBRE AS VENDEDOR_NOMBRE
                FROM CABECERA_FACTURA CF
                JOIN CLIENTE CL ON CF.RUC_CLIENTE = CL.RUC_CLIENTE
                JOIN VENDEDOR VD ON CF.CODIGO_VENDEDOR = VD.COD_VENDEDOR
                WHERE CF.NUMERO_FACTURA = %s
            """, (num_factura,))
            factura = cursor.fetchone()
            
            # Obtener los ítems de la factura
            cursor.execute("""
                SELECT CI.DESC_ITEM, CF.CANTIDAD, CI.PRECIO, CF.PRECIO_VENTA
                FROM CUERPO_FACTURA CF
                JOIN ARTICULOS CI ON CF.CODIGO_ITEM = CI.CODIGO_ITEM
                WHERE CF.NUMERO_FACTURA = %s
            """, (num_factura,))
            items = cursor.fetchall()
            
            if not factura:
                return "Factura no encontrada", 404

            # Crear el PDF
            buffer = io.BytesIO()
            p = canvas.Canvas(buffer, pagesize=letter)
            width, height = letter
            
            # Información del emisor (ficticia)
            p.drawString(72, 750, "SERVICIOS GENERALES S.A.C.")
            p.drawString(72, 735, "R.U.C. Nº: 100770490571")

            # Encabezado del PDF
            p.drawString(72, 700, f"R.U.C. Nº: {factura['RUC_CLIENTE']}")
            p.drawString(72, 685, f"Factura Nº: {factura['NUMERO_FACTURA']}")
            p.drawString(72, 670, f"Cliente: {factura['CLIENTE_NOMBRE']}")
            p.drawString(72, 655, f"Fecha: {factura['FECHA_FACTURA'].strftime('%d/%m/%Y')}")
            p.drawString(72, 640, f"Vendedor: {factura['VENDEDOR_NOMBRE']}")

            # Tabla de ítems
            data = [["Cantidad", "Descripción", "Precio Unitario", "Total"]]
            for item in items:
                data.append([item['CANTIDAD'], item['DESC_ITEM'], f"{item['PRECIO']:.2f}", f"{item['PRECIO_VENTA']:.2f}"])
            
            table = Table(data, colWidths=[50, 200, 100, 100])
            table.setStyle(TableStyle([
               ('BACKGROUND', (0,0), (-1,0), colors.grey),
               ('GRID', (0,0), (-1,-1), 1, colors.black),
               ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
               ('ALIGN', (0,0), (-1,-1), 'CENTER')
            ]))
            table.wrapOn(p, width, height)
            table.drawOn(p, 72, 500)

            # Mostrar total e IGV
            p.drawString(72, 465, f"Subtotal: {factura['SUBTOTAL']:.2f} PEN")
            p.drawString(72, 450, f"IGV: {factura['IGV']:.2f} PEN")
            p.drawString(72, 435, f"Importe a Pagar: {factura['TOTAL']:.2f} PEN")

            # Final del PDF
            p.showPage()
            p.save()
            buffer.seek(0)
            return send_file(buffer, as_attachment=True, download_name=f'factura_{num_factura}.pdf')
        except Exception as e:
            print("Error al generar el PDF: ", e)
            import traceback
            traceback.print_exc()
            return "Error interno", 500
        finally:
            cursor.close()
            connection.close()
    else:
        return "Error al conectar con la base de datos", 500
    
@app.route('/nuevo_cliente', methods=['GET', 'POST'])
def nuevo_cliente():
    if request.method == 'POST':
        nombre = request.form['nombre']
        ruc = request.form['ruc']
        connection = get_db_connection()
        if connection is not None:
            try:
                cursor = connection.cursor(dictionary=True)
                cursor.execute("INSERT INTO CLIENTE (NOMBRE, RUC_CLIENTE) VALUES (%s, %s)", (nombre, ruc))
                connection.commit()
                cursor.close()
                connection.close()
                return redirect(url_for('index'))  # Redirecciona a la página principal
            except Exception as e:
                print("Error al insertar cliente en la base de datos:", e)
                return "Error al insertar cliente en la base de datos", 500
        else:
            return "Error de conexión a la base de datos", 500
    return render_template('nuevo_cliente.html')

if __name__ == '__main__':
    app.run(debug=True)