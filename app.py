from api.index import app
import os

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    print(f"Starting Flask app on port {port} with debug={debug}")
    app.run(host='0.0.0.0', port=port, debug=debug)
