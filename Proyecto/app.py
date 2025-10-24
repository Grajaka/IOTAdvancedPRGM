from flask import Flask

app = Flask(__name__)

@app.route('/')
def index():
    return "Hello from flask"

if __name__== '__name__':
    app.run('0.0.0:',port=8001)