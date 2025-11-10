# src/backend/server.py
from api import app

if __name__ == "__main__":
    # Run with: python server.py
    app.run(host="127.0.0.1", port=5000, debug=True)
