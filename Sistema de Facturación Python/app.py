from flask import Flask, flash, render_template, request, redirect, url_for, send_file, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from mysql.connector import connect, Error
from mysql.connector.cursor import MySQLCursorDict
import mysql.connector
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
import io
import json
from flask import jsonify

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta'

# Configuración de la conexión a la base de datos
MYSQL_HOST = "viaduct.proxy.rlwy.net"
MYSQL_PORT = 47723
MYSQL_USER = "root"
MYSQL_PASSWORD = "tuDTbAoAjOIBSzzcOKScThPiHeUkKvaB"
MYSQL_DATABASE = "railway"
codigo_vendedor_global = 1001

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

# Modelo de usuario
class User(UserMixin):
    def __init__(self, username, password):
        self.username = username
        self.password = password

    def get_id(self):
        return self.username

# Obtener usuario desde la base de datos
def get_user(username):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute('SELECT * FROM USUARIO WHERE NOMBRE_USUARIO = %s', (username,))
        user = cursor.fetchone()
        cursor.close()
        connection.close()
        if user:
            return User(user['NOMBRE_USUARIO'], user['CONTRASENA'])
        else:
            return None
    except Exception as e:
        print("Error al obtener usuario:", e)
        return None
    
# Configurar Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

# Cargar usuario actual para Flask-Login
@login_manager.user_loader
def load_user(username):
    return get_user(username)


@app.route('/login', methods=['POST'])
def login():
    try:
        username = request.form['username']
        password = request.form['password']
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute('SELECT * FROM USUARIO WHERE NOMBRE_USUARIO = %s AND CONTRASENA = %s', (username, password))
        user = cursor.fetchone()
        cursor.close()
        connection.close()

        if user:
            user_obj = User(user['NOMBRE_USUARIO'], user['CONTRASENA'])
            login_user(user_obj)
            global codigo_vendedor_global
            codigo_vendedor_global = user['COD_VENDEDOR']
            return redirect(url_for('index'))
        else:
            flash('Código de Vendedor o contraseña incorrectos', 'error')
            return redirect(url_for('home'))

    except Exception as e:
        print("Error durante la autenticación:", e)
        flash('Error interno del servidor. Por favor intente de nuevo.', 'error')
        return redirect(url_for('home'))
    
@app.route('/', methods=['GET'])
def home():
    return render_template('login.html')  # Asegúrate de que 'login.html' exista

@app.route('/index', methods=['GET'])
@login_required
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
        return render_template('principal.html', data=facturas)
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
@app.route('/nuevo_comprobante', methods=['GET', 'POST'])
@login_required
def nuevo_comprobante():
    # Obtener el código de vendedor del parámetro de la URL
    global codigo_vendedor_global

    connection = get_db_connection()
    if connection is None:
        return "Error de conexión a la base de datos", 500

    if request.method == 'POST':
        cursor = None
        try:
            cursor = connection.cursor()
            ruc_cliente = request.form.get('cliente')
            fecha_emision = request.form.get('fecha_emision')
            total_afecto = request.form.get('totalAfecto')
            total_igv = request.form.get('totalIGV')
            total_general = request.form.get('totalGeneral')

            cursor.execute(
                "INSERT INTO CABECERA_FACTURA (FECHA_FACTURA, RUC_CLIENTE, CODIGO_VENDEDOR) VALUES (%s, %s, %s)",
                (fecha_emision, ruc_cliente, codigo_vendedor_global)  # Usar el código de vendedor obtenido del parámetro de la URL
            )
            factura_id = cursor.lastrowid
            
            # Obtener los datos de los items del formulario
            datos_items = request.form.get('datos_items')
            if datos_items:
                datos_items = json.loads(datos_items)
                for item_data in datos_items:
                    cantidad = item_data.get('cantidad')
                    codigo_item = item_data.get('codigo_item')
                    precio_unitario = item_data.get('precio_unitario')
                    
                    cursor.execute(
                        "INSERT INTO CUERPO_FACTURA (NUMERO_FACTURA, CODIGO_ITEM, CANTIDAD, PRECIO_VENTA) VALUES (%s, %s, %s, %s)",
                        (factura_id, codigo_item, cantidad, precio_unitario)
                    )

            cursor.execute(
                "UPDATE CABECERA_FACTURA SET SUBTOTAL = %s, IGV = %s, TOTAL = %s WHERE NUMERO_FACTURA = %s",
                (total_afecto, total_igv, total_general, factura_id)
            )

            connection.commit()
            return redirect(url_for('index'))
        except Exception as e:
            if connection:
                connection.rollback()
            print("Error al procesar el formulario:", e)
            return render_template('nuevo_comprobante.html', mensaje_error="Error al procesar el formulario: " + str(e))
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
    else:
        return manejar_get_nuevo_comprobante(connection)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))  # Redirige al inicio de sesión

@app.route('/guardar_items', methods=['POST'])
@login_required
def guardar_items():

    try:
        # Obtener los datos de los items del formulario
        datos_items = request.form.get('datos_items')

        # Convertir los datos a un objeto Python
        datos_items = json.loads(datos_items)

        # Conectarse a la base de datos
        connection = get_db_connection()

        # Iterar sobre los datos de los items y realizar la inserción en la tabla CUERPO_FACTURA
        for item in datos_items:
            cantidad = int(item['cantidad'])
            codigo_item = int(item['codigo_item'])
            precio_unitario = float(item['precio_unitario'])
            print(str(id) + " - " + str(cantidad) + " - " + str(codigo_item) + " - " + str(precio_unitario))

            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO CUERPO_FACTURA (NUMERO_FACTURA, CODIGO_ITEM, CANTIDAD, PRECIO_VENTA) VALUES (%s, %s, %s, %s)",
                (id, codigo_item, cantidad, precio_unitario)
            )
            cursor.close()

        # Confirmar los cambios en la base de datos y cerrar la conexión
        connection.commit()
        connection.close()

        # Devolver una respuesta al cliente si es necesario
        return 'Datos ingresados correctamente en la base de datos', 200
    except Exception as e:
        # Manejar cualquier error que pueda ocurrir
        print("Error al procesar los datos:", e)
        return 'Error al procesar los datos', 500


    
@app.route('/get_producto/<int:codigo_producto>')
@login_required
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
@login_required
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
                data.append([item['CANTIDAD'], item['DESC_ITEM'], f"{item['PRECIO']:.2f}", f"{(item['PRECIO_VENTA'] * item['CANTIDAD']):.2f}"])
            
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
@login_required
def nuevo_cliente():
    error_message = None
    if request.method == 'POST':
        nombre = request.form['nombre']
        apellidos = request.form['apellidos']
        ruc = request.form['ruc']
        nombre_completo = f"{nombre} {apellidos}"

        connection = get_db_connection()
        if connection is not None:
            try:
                cursor = connection.cursor(dictionary=True)
                # Verificar si el RUC ya existe
                cursor.execute("SELECT RUC_CLIENTE FROM CLIENTE WHERE RUC_CLIENTE = %s", (ruc,))
                ruc_existente = cursor.fetchone()
                if ruc_existente:
                    # Si el RUC ya existe, mostrar un mensaje de error y no insertar
                    error_message = "No se pudo registrar un nuevo cliente porque el RUC ya está registrado."
                    return render_template('nuevo_cliente.html', error=error_message)

                # Insertar el nuevo cliente si el RUC no existe
                cursor.execute("INSERT INTO CLIENTE (NOMBRE, RUC_CLIENTE) VALUES (%s, %s)", (nombre_completo, ruc))
                connection.commit()
                cursor.close()
                connection.close()
                return redirect(url_for('index'))
            except Exception as e:
                print("Error al insertar cliente en la base de datos:", e)
                error_message = "Error al insertar cliente en la base de datos."
                return render_template('nuevo_cliente.html', error=error_message)
        else:
            error_message = "Error de conexión a la base de datos. Por favor, inténtalo de nuevo más tarde."
            return render_template('nuevo_cliente.html', error=error_message)
    return render_template('nuevo_cliente.html', error=error_message)


if __name__ == '__main__':
    app.run(debug=True)