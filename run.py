#!/usr/bin/env python3
"""
Run script for the Web Scraper Flask API
"""
import os
import sys
import subprocess

def install_dependencies():
    """Install required dependencies"""
    print("Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
        print("Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError:
        print("Failed to install dependencies")
        return False

def run_app():
    """Run the Flask application"""
    print("Starting Web Scraper API...")
    try:
        # Set environment variables
        os.environ['FLASK_APP'] = 'app.py'
        os.environ['FLASK_ENV'] = 'development'
        
        # Import and run the app
        from app import app
        app.run(host='0.0.0.0', port=5000, debug=True)
    except ImportError:
        print("Failed to import app. Make sure dependencies are installed.")
        return False
    except Exception as e:
        print(f"Failed to start app: {e}")
        return False

def main():
    """Main function"""
    if len(sys.argv) > 1 and sys.argv[1] == '--install':
        if not install_dependencies():
            sys.exit(1)
    
    if not os.path.exists('requirements.txt'):
        print("requirements.txt not found. Make sure you're in the project directory.")
        sys.exit(1)
    
    run_app()

if __name__ == '__main__':
    main()
