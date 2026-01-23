import urllib.request
import urllib.error

BASE_URL = 'http://localhost:5002'

def test_routes():
    routes = [
        '/customers',
        '/suppliers',
        '/suppliers/add',
        '/customers/add'
    ]
    
    for route in routes:
        try:
            r = urllib.request.urlopen(f"{BASE_URL}{route}")
            print(f"GET {route}: {r.getcode()}")
        except urllib.error.HTTPError as e:
            print(f"GET {route}: {e.code}")
        except Exception as e:
            print(f"Error GET {route}: {e}")

if __name__ == "__main__":
    test_routes()
