from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

@app.route('/vamonos')
def abajo():
    return "vamonos"
    
@app.route('/')
def metodo():
    return "hola mundo"    
    
@app.route('/index')
def index():
    return render_template('index.html')
    
if __name__=='__main__':
    app.run(host='0.0.0.0', port=8001)