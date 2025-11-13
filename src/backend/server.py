# src/backend/server.py
from api import app

from flask_cors import CORS

if __name__ == "__main__":
    # app = Flask(__name__)  # 你已有
    CORS(app, resources={r"/api/*": {"origins": "*"}})  # 开发期先放开；上线可收紧

    # Run with: python server.py
    app.run(host="0.0.0.0", port=5000, debug=True,threaded=True)
