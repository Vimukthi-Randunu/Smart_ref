import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    with app.test_client() as client:
        yield client

def test_app_starts(client):
    """Test that the app starts and homepage responds"""
    response = client.get('/')
    assert response.status_code == 200

def test_login_page_loads(client):
    """Test that login page is accessible"""
    response = client.get('/login')
    assert response.status_code == 200

def test_signup_page_loads(client):
    """Test that signup page is accessible"""
    response = client.get('/signup')
    assert response.status_code == 200