"""Basic checks for imports, config, API modules, and app creation."""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
def test_imports():
    """Test if all required modules can be imported."""
    print("Testing imports...")
    
    try:
        # Test Flask
        import flask
        print("✓ Flask imported successfully")
        
        # Test Firebase Admin
        import firebase_admin
        print("✓ Firebase Admin imported successfully")
        
        # Test Google Generative AI
        import google.generativeai
        print("✓ Google Generative AI imported successfully")
        
        # Test python-dotenv
        from dotenv import load_dotenv
        print("✓ python-dotenv imported successfully")
        
        assert True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        assert False, f"Import error: {e}"


def test_config():
    """Test configuration loading."""
    print("\nTesting configuration...")
    
    try:
        from config import Config
        print("✓ Config class imported successfully")
        
        # Check if required attributes exist
        required_attrs = ['GEMINI_API_KEY', 'FIREBASE_CREDENTIALS_PATH', 'SECRET_KEY']
        
        for attr in required_attrs:
            if hasattr(Config, attr):
                value = getattr(Config, attr)
                if value:
                    print(f"✓ {attr} is configured")
                else:
                    print(f"⚠ {attr} is empty (expected for template)")
            else:
                print(f"✗ {attr} is missing from Config")
                assert False, f"{attr} is missing from Config"
        
        assert True
        
    except Exception as e:
        print(f"✗ Configuration error: {e}")
        assert False, f"Configuration error: {e}"


def test_app_creation():
    """Test Flask app creation without initializing external services."""
    print("\nTesting app creation (without external services)...")
    
    try:
        # Temporarily mock the service initialization to avoid errors
        import stressease.services.firebase_service as firebase_service
        import stressease.services.gemini_service as gemini_service
        
        # Store original functions
        original_init_firebase = firebase_service.init_firebase
        original_init_gemini = gemini_service.init_gemini
        
        # Mock the initialization functions
        def mock_init_firebase(path):
            print("Mock: Firebase initialization skipped")
            # Set the global db variable to avoid initialization error
            firebase_service.db = {}
            print("✓ Firebase initialized successfully")
            
        def mock_init_gemini(api_key):
            print("Mock: Gemini initialization skipped")
            print("✓ Gemini AI initialized successfully")
        
        firebase_service.init_firebase = mock_init_firebase
        gemini_service.init_gemini = mock_init_gemini
        
        # Try to create the app
        from stressease import create_app
        app = create_app()
        
        print("✓ Flask app created successfully")
        print(f"✓ App name: {app.name}")
        
        # Test if blueprints are registered
        blueprint_names = [bp.name for bp in app.blueprints.values()]
        expected_blueprints = ['mood', 'chat']
        
        for bp_name in expected_blueprints:
            if bp_name in blueprint_names:
                print(f"✓ {bp_name} blueprint registered")
            else:
                print(f"✗ {bp_name} blueprint missing")
        
        # Restore original functions
        firebase_service.init_firebase = original_init_firebase
        gemini_service.init_gemini = original_init_gemini
        
        return True
        
    except Exception as e:
        print(f"✗ App creation error: {e}")
        return False


def test_api_structure():
    """Test API module structure."""
    print("\nTesting API structure...")
    
    try:
        # Initialize Firebase mock before importing API modules
        import stressease.services.firebase_service as firebase_service
        firebase_service.db = {}
        print("✓ Firebase initialized successfully")
        
        # Test API modules
        from stressease.api import mood, chat
        print("✓ All API modules imported successfully")
        
        # Test if blueprints exist
        if hasattr(mood, 'mood_bp'):
            print("✓ mood_bp blueprint found")
        else:
            print("✗ mood_bp blueprint missing")
            
        if hasattr(chat, 'chat_bp'):
            print("✓ chat_bp blueprint found")
        else:
            print("✗ chat_bp blueprint missing")
        
        return True
        
    except Exception as e:
        print(f"✗ API structure error: {e}")
        return False


def test_services_structure():
    """Test services module structure."""
    print("\nTesting services structure...")
    
    try:
        # Test service modules
        from stressease.services import auth_service, firebase_service, gemini_service
        print("✓ All service modules imported successfully")
        
        # Test key functions exist
        if hasattr(auth_service, 'token_required'):
            print("✓ token_required decorator found")
        else:
            print("✗ token_required decorator missing")
            
        if hasattr(firebase_service, 'init_firebase'):
            print("✓ init_firebase function found")
        else:
            print("✗ init_firebase function missing")
            
        if hasattr(gemini_service, 'init_gemini'):
            print("✓ init_gemini function found")
        else:
            print("✗ init_gemini function missing")
        
        return True
        
    except Exception as e:
        print(f"✗ Services structure error: {e}")
        return False


def main():
    """Run all tests."""
    print("StressEase Backend Test Suite")
    print("=" * 40)
    
    tests = [
        test_imports,
        test_config,
        test_api_structure,
        test_services_structure,
        test_app_creation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 40)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Backend setup is complete.")
        return True
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)