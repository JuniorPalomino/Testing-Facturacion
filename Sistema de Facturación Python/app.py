from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

class Producto:
    def __init__(self, nombre, precio, cantidad):
        self.nombre = nombre
        self.precio = precio
        self.cantidad = cantidad
        self.subtotal = precio * cantidad

class Factura:
    def __init__(self, numero_factura, fecha_factura, ruc_cliente, cod_vendedor, detalles, total_factura):
        self.numero_factura = numero_factura
        self.fecha_factura = fecha_factura
        self.ruc_cliente = ruc_cliente
        self.cod_vendedor = cod_vendedor
        self.detalles = detalles
        self.total_factura = total_factura

productos = []
facturas = []

@app.route('/')
def index():
    return render_template('index.html', productos=productos)

@app.route('/agregar_producto', methods=['POST'])
def agregar_producto():
    nombre = request.form['nombre_producto']
    precio = float(request.form['precio_producto'])
    cantidad = int(request.form['cantidad_producto'])
    productos.append(Producto(nombre, precio, cantidad))
    return redirect(url_for('index'))

@app.route('/generar_factura', methods=['POST'])
def generar_factura():
    total_factura = sum(producto.subtotal for producto in productos)
    detalles_factura = [producto for producto in productos]
    factura = Factura(numero_factura=len(facturas) + 1, fecha_factura='25/04/2024', ruc_cliente='123456789', cod_vendedor='V001', detalles=detalles_factura, total_factura=total_factura)
    facturas.append(factura)
    productos.clear()
    return redirect(url_for('lista_facturas'))

@app.route('/factura/<int:numero_factura>')
def factura(numero_factura):
    factura = next((f for f in facturas if f.numero_factura == numero_factura), None)
    if factura:
        return render_template('factura.html', factura=factura)
    else:
        return "Factura no encontrada", 404

@app.route('/lista_facturas')
def lista_facturas():
    return render_template('lista_facturas.html', facturas=facturas)

if __name__ == '__main__':
    app.run(debug=True)
