from flask import Flask, render_template, request, redirect, url_for
import mysql.connector

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
        SELECT FECHA_FACTURA as fecha_emision, 'Factura' as tipo, CONCAT('F001-', NUMERO_FACTURA) as serie_numero, 
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


@app.route('/nuevo_comprobante', methods=['GET', 'POST'])
def nuevo_comprobante():
    connection = get_db_connection()
    if request.method == 'POST':
        # Extracción de datos del formulario
        ruc_cliente = request.form['cliente']
        serie = request.form['serie']
        fecha_emision = request.form['fecha_emision']
        items = request.form.getlist('items')

        # Inserción de la cabecera de la factura
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO CABECERA_FACTURA (FECHA_FACTURA, RUC_CLIENTE, CODIGO_VENDEDOR, TOTAL) VALUES (%s, %s, %s, %s)",
            (fecha_emision, ruc_cliente, 1, sum([float(i['total']) for i in items]))  # Suponiendo un vendedor por defecto
        )
        factura_id = cursor.lastrowid

        # Inserción de cada item de la factura
        for item in items:
            cursor.execute(
                "INSERT INTO CUERPO_FACTURA (NUMERO_FACTURA, CODIGO_ITEM, CANTIDAD, PRECIO_VENTA) VALUES (%s, %s, %s, %s)",
                (factura_id, item['codigo_item'], item['cantidad'], item['precio_unitario'])
            )

        connection.commit()
        cursor.close()
        connection.close()
        return redirect(url_for('index'))

    # Obtener el último número de factura y calcular el siguiente
    if connection is not None:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT MAX(NUMERO_FACTURA) as ultimo_numero FROM CABECERA_FACTURA")
        resultado = cursor.fetchone()
        ultimo_numero = resultado['ultimo_numero'] if resultado['ultimo_numero'] is not None else 0
        siguiente_numero = ultimo_numero + 1

        # Obtener clientes y productos
        cursor.execute("SELECT RUC_CLIENTE as id, NOMBRE FROM CLIENTE")
        clientes = cursor.fetchall()
        cursor.execute("SELECT CODIGO_ITEM as id, DESC_ITEM as descripcion FROM ARTICULOS")
        productos = cursor.fetchall()
        
        cursor.close()
        connection.close()

        return render_template('nuevo_comprobante.html', clientes=clientes, productos=productos, siguiente_numero=siguiente_numero)
    else:
        return "Error al conectar con la base de datos"
    
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


if __name__ == '__main__':
    app.run(debug=True)