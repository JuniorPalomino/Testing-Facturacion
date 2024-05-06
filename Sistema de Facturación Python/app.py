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

comprobantes = []
clientes = []
@app.route('/nuevo_comprobante', methods=['GET', 'POST'])
def nuevo_comprobante():
    if request.method == 'POST':
        comprobante = {
            "cliente": request.form['cliente'],
            "documento": request.form['documento'],
            "serie": request.form['serie'],
            "fecha_emision": request.form['fecha_emision']
        }
        comprobantes.append(comprobante)
        return redirect(url_for('index'))
    return render_template('nuevo_comprobante.html')

@app.route('/nuevo_cliente', methods=['GET', 'POST'])
def nuevo_cliente():
    if request.method == 'POST':
        cliente = {
            "nombre": request.form['nombre'],
            "documento": request.form['documento']
        }
        clientes.append(cliente)
        return redirect(url_for('nuevo_comprobante'))  # Redirige al formulario de comprobante
    return render_template('nuevo_cliente.html')

if __name__ == '__main__':
    app.run(debug=True)


#DATABASE
