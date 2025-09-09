from flask import Flask, jsonify, request
import json

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'success',
        'message': 'Web Scraper API is working!',
        'version': '1.0.0'
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'message': 'API is running'
    })

@app.route('/test', methods=['POST'])
def test():
    try:
        data = request.get_json()
        return jsonify({
            'status': 'success',
            'received': data,
            'message': 'Test endpoint working'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=False)
