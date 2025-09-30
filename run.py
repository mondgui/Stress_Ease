"""Local development entry point."""

from stressease import create_app
from config import Config

# Validate configuration before starting the application
try:
    Config.validate_config()
    print("[PASS] Configuration validation passed")
except ValueError as e:
    print(f"[ERROR] Configuration error: {e}")
    exit(1)

# Create the Flask application instance
app = create_app()

if __name__ == '__main__':
    print("Starting StressEase Backend API...")
    print(f"Debug mode: {Config.DEBUG}")
    
    # Run the application
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=Config.DEBUG
    )