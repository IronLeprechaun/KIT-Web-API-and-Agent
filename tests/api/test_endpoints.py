#!/usr/bin/env python3
"""
API Endpoints Test
Tests backend API endpoints for functionality and response formats.
"""

import json
import requests
import sys
from pathlib import Path

class APITest:
    def __init__(self):
        self.base_url = "http://localhost:8000/api"
        self.results = {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': [],
            'errors': []
        }
    
    def test_health_check(self):
        """Test if the API is responding"""
        print("🏥 Testing API health...")
        
        try:
            response = requests.get(f"{self.base_url}/notes/", timeout=5)
            if response.status_code == 200:
                print("✅ API health check passed")
                return True
            else:
                print(f"❌ API health check failed: status {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ API health check failed: {e}")
            return False
    
    def test_get_notes(self):
        """Test GET /api/notes/ endpoint"""
        print("📝 Testing GET /notes/ endpoint...")
        
        try:
            response = requests.get(f"{self.base_url}/notes/")
            
            if response.status_code != 200:
                print(f"❌ GET /notes/ failed: status {response.status_code}")
                return False
            
            try:
                data = response.json()
                if not isinstance(data, list):
                    print("❌ GET /notes/ should return a list")
                    return False
                
                print(f"✅ GET /notes/ passed - returned {len(data)} notes")
                return True
                
            except json.JSONDecodeError:
                print("❌ GET /notes/ returned invalid JSON")
                return False
                
        except Exception as e:
            print(f"❌ GET /notes/ failed: {e}")
            return False
    
    def run_all_tests(self):
        """Run all API tests"""
        print("🧪 Running API Endpoint Tests...")
        print("="*50)
        
        tests = [
            ("API Health", self.test_health_check),
            ("GET Notes", self.test_get_notes)
        ]
        
        for test_name, test_func in tests:
            self.results['total_tests'] += 1
            
            try:
                success = test_func()
                if success:
                    self.results['passed_tests'] += 1
                else:
                    self.results['failed_tests'].append(test_name)
            except Exception as e:
                self.results['failed_tests'].append(test_name)
                self.results['errors'].append(f"{test_name}: {str(e)}")
            
            print()  # Add spacing between tests
        
        # Print summary
        passed = self.results['passed_tests']
        total = self.results['total_tests']
        
        print("="*50)
        print(f"🧪 API Test Results: {passed}/{total} passed")
        
        if self.results['failed_tests']:
            print("❌ Failed tests:")
            for test in self.results['failed_tests']:
                print(f"  - {test}")
        
        if passed == total:
            print("✅ All API tests PASSED")
            return True
        else:
            print("❌ API tests FAILED")
            return False

def main():
    """Run the API tests"""
    api_test = APITest()
    success = api_test.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 