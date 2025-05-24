#!/usr/bin/env python3
"""
Enhanced Testing Framework
Comprehensive testing with detailed reporting and automated issue detection.
"""

import argparse
import asyncio
import json
import time
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import requests
import sqlite3

class EnhancedTester:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.backend_dir = self.project_root / "backend"
        self.frontend_dir = self.project_root / "frontend"
        
        # Test results
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "summary": {"total": 0, "passed": 0, "failed": 0, "warnings": 0},
            "tests": [],
            "performance": {},
            "issues": []
        }
        
        # API endpoints
        self.api_base = "http://localhost:8000/api"
        
    def log_test(self, test_name: str, status: str, details: str = "", duration: float = 0):
        """Log a test result"""
        test_result = {
            "name": test_name,
            "status": status,  # "PASS", "FAIL", "WARN"
            "details": details,
            "duration": round(duration, 3),
            "timestamp": datetime.now().isoformat()
        }
        
        self.results["tests"].append(test_result)
        self.results["summary"]["total"] += 1
        
        if status == "PASS":
            self.results["summary"]["passed"] += 1
            print(f"✅ {test_name} - {details}")
        elif status == "FAIL":
            self.results["summary"]["failed"] += 1
            print(f"❌ {test_name} - {details}")
            self.results["issues"].append(f"{test_name}: {details}")
        else:  # WARN
            self.results["summary"]["warnings"] += 1
            print(f"⚠️ {test_name} - {details}")
    
    def test_database_health(self) -> bool:
        """Test database connectivity and schema"""
        start_time = time.time()
        
        try:
            db_path = self.backend_dir / "KITCore" / "database" / "kit_agent.db"
            
            if not db_path.exists():
                self.log_test("Database File", "FAIL", f"Database file not found: {db_path}", time.time() - start_time)
                return False
            
            # Test connection
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Check tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            expected_tables = ["notes", "tags", "note_tags", "user_settings"]
            
            missing_tables = [t for t in expected_tables if t not in tables]
            if missing_tables:
                self.log_test("Database Schema", "WARN", f"Missing tables: {missing_tables}", time.time() - start_time)
            else:
                self.log_test("Database Schema", "PASS", f"All {len(expected_tables)} tables found", time.time() - start_time)
            
            # Test basic operations
            cursor.execute("SELECT COUNT(*) FROM notes")
            note_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM tags")
            tag_count = cursor.fetchone()[0]
            
            conn.close()
            
            self.log_test("Database Connection", "PASS", f"Connected, {note_count} notes, {tag_count} tags", time.time() - start_time)
            return True
            
        except Exception as e:
            self.log_test("Database Connection", "FAIL", str(e), time.time() - start_time)
            return False
    
    def test_backend_health(self) -> bool:
        """Test backend API health"""
        start_time = time.time()
        
        try:
            response = requests.get("http://localhost:8000/health", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "unknown")
                self.log_test("Backend Health", "PASS", f"Status: {status}", time.time() - start_time)
                return True
            else:
                self.log_test("Backend Health", "FAIL", f"HTTP {response.status_code}", time.time() - start_time)
                return False
                
        except requests.exceptions.ConnectionError:
            self.log_test("Backend Health", "FAIL", "Connection refused - server not running?", time.time() - start_time)
            return False
        except Exception as e:
            self.log_test("Backend Health", "FAIL", str(e), time.time() - start_time)
            return False
    
    def test_api_endpoints(self) -> bool:
        """Test key API endpoints"""
        endpoints = [
            ("/notes/", "GET", "List notes"),
            ("/tags/", "GET", "List tags"),
            ("/settings/", "GET", "Get settings")
        ]
        
        all_passed = True
        
        for endpoint, method, description in endpoints:
            start_time = time.time()
            
            try:
                if method == "GET":
                    response = requests.get(f"{self.api_base}{endpoint}", timeout=5)
                else:
                    self.log_test(f"API {method} {endpoint}", "WARN", "Method not implemented in test", 0)
                    continue
                
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        self.log_test(f"API {method} {endpoint}", "PASS", f"{description} - {len(data)} items", time.time() - start_time)
                    else:
                        self.log_test(f"API {method} {endpoint}", "PASS", description, time.time() - start_time)
                else:
                    self.log_test(f"API {method} {endpoint}", "FAIL", f"HTTP {response.status_code}", time.time() - start_time)
                    all_passed = False
                    
            except Exception as e:
                self.log_test(f"API {method} {endpoint}", "FAIL", str(e), time.time() - start_time)
                all_passed = False
        
        return all_passed
    
    def test_note_operations(self) -> bool:
        """Test CRUD operations on notes"""
        start_time = time.time()
        
        try:
            # Test creating a note
            test_note = {
                "content": f"Test note created at {datetime.now().isoformat()}",
                "tags": ["test", "automated"]
            }
            
            response = requests.post(f"{self.api_base}/notes/", json=test_note, timeout=5)
            
            if response.status_code != 201:
                self.log_test("Note Creation", "FAIL", f"Failed to create note: HTTP {response.status_code}", time.time() - start_time)
                return False
            
            note_data = response.json()
            note_id = note_data.get("note_id") or note_data.get("id")
            
            if not note_id:
                self.log_test("Note Creation", "FAIL", "No note ID returned", time.time() - start_time)
                return False
            
            self.log_test("Note Creation", "PASS", f"Created note ID {note_id}", time.time() - start_time)
            
            # Test retrieving the note
            start_time = time.time()
            response = requests.get(f"{self.api_base}/notes/{note_id}", timeout=5)
            
            if response.status_code == 200:
                retrieved_note = response.json()
                if test_note["content"] in retrieved_note.get("content", ""):
                    self.log_test("Note Retrieval", "PASS", f"Retrieved note ID {note_id}", time.time() - start_time)
                else:
                    self.log_test("Note Retrieval", "WARN", "Content mismatch", time.time() - start_time)
            else:
                self.log_test("Note Retrieval", "FAIL", f"HTTP {response.status_code}", time.time() - start_time)
                return False
            
            # Test deleting the note
            start_time = time.time()
            response = requests.delete(f"{self.api_base}/notes/{note_id}", timeout=5)
            
            if response.status_code in [200, 204]:
                self.log_test("Note Deletion", "PASS", f"Deleted note ID {note_id}", time.time() - start_time)
            else:
                self.log_test("Note Deletion", "WARN", f"HTTP {response.status_code} - note may still exist", time.time() - start_time)
            
            return True
            
        except Exception as e:
            self.log_test("Note Operations", "FAIL", str(e), time.time() - start_time)
            return False
    
    def test_frontend_health(self) -> bool:
        """Test frontend availability"""
        start_time = time.time()
        
        try:
            response = requests.get("http://localhost:3000", timeout=10)
            
            if response.status_code == 200:
                # Check if it looks like a React app
                content = response.text
                if "react" in content.lower() or "app" in content.lower():
                    self.log_test("Frontend Health", "PASS", "Frontend responding", time.time() - start_time)
                    return True
                else:
                    self.log_test("Frontend Health", "WARN", "Unexpected content", time.time() - start_time)
                    return False
            else:
                self.log_test("Frontend Health", "FAIL", f"HTTP {response.status_code}", time.time() - start_time)
                return False
                
        except requests.exceptions.ConnectionError:
            self.log_test("Frontend Health", "FAIL", "Connection refused - frontend not running?", time.time() - start_time)
            return False
        except Exception as e:
            self.log_test("Frontend Health", "FAIL", str(e), time.time() - start_time)
            return False
    
    def test_performance(self) -> Dict[str, float]:
        """Test system performance"""
        performance = {}
        
        # Test API response time
        start_time = time.time()
        try:
            response = requests.get(f"{self.api_base}/notes/", timeout=5)
            if response.status_code == 200:
                response_time = (time.time() - start_time) * 1000  # Convert to ms
                performance["api_response_time_ms"] = round(response_time, 2)
                
                if response_time < 500:
                    self.log_test("API Performance", "PASS", f"Response time: {response_time:.2f}ms")
                elif response_time < 1000:
                    self.log_test("API Performance", "WARN", f"Slow response: {response_time:.2f}ms")
                else:
                    self.log_test("API Performance", "FAIL", f"Very slow: {response_time:.2f}ms")
        except Exception as e:
            self.log_test("API Performance", "FAIL", str(e))
        
        # Test database query performance
        start_time = time.time()
        try:
            db_path = self.backend_dir / "KITCore" / "database" / "kit_agent.db"
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Run a complex query
            cursor.execute("""
                SELECT n.*, COUNT(nt.tag_id) as tag_count 
                FROM notes n 
                LEFT JOIN note_tags nt ON n.note_id = nt.note_version_id 
                GROUP BY n.note_id 
                LIMIT 100
            """)
            results = cursor.fetchall()
            
            query_time = (time.time() - start_time) * 1000
            performance["db_query_time_ms"] = round(query_time, 2)
            
            conn.close()
            
            if query_time < 100:
                self.log_test("Database Performance", "PASS", f"Query time: {query_time:.2f}ms, {len(results)} results")
            elif query_time < 500:
                self.log_test("Database Performance", "WARN", f"Slow query: {query_time:.2f}ms")
            else:
                self.log_test("Database Performance", "FAIL", f"Very slow query: {query_time:.2f}ms")
                
        except Exception as e:
            self.log_test("Database Performance", "FAIL", str(e))
        
        self.results["performance"] = performance
        return performance
    
    def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run all tests and return results"""
        print("🧪 Starting Comprehensive Test Suite")
        print("=" * 60)
        
        # Test order matters - database first, then backend, then API
        test_functions = [
            ("Database Health", self.test_database_health),
            ("Backend Health", self.test_backend_health),
            ("API Endpoints", self.test_api_endpoints),
            ("Note Operations", self.test_note_operations),
            ("Frontend Health", self.test_frontend_health),
            ("Performance", lambda: self.test_performance() and True)
        ]
        
        for test_name, test_func in test_functions:
            print(f"\n🔍 Running {test_name} tests...")
            try:
                test_func()
            except Exception as e:
                self.log_test(test_name, "FAIL", f"Test crashed: {e}")
        
        # Generate summary
        print("\n" + "=" * 60)
        print("📊 Test Summary")
        print("=" * 60)
        
        summary = self.results["summary"]
        total = summary["total"]
        passed = summary["passed"]
        failed = summary["failed"]
        warnings = summary["warnings"]
        
        print(f"✅ Passed: {passed}/{total}")
        print(f"❌ Failed: {failed}/{total}")
        print(f"⚠️ Warnings: {warnings}/{total}")
        
        if failed == 0:
            print("\n🎉 All critical tests passed!")
        else:
            print(f"\n🚨 {failed} test(s) failed - see details above")
        
        # Save results
        results_file = self.project_root / "test_results.json"
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n📁 Detailed results saved to: {results_file}")
        
        return self.results

def main():
    parser = argparse.ArgumentParser(description="Enhanced Testing Framework")
    parser.add_argument("--comprehensive", action="store_true", help="Run comprehensive test suite")
    parser.add_argument("--database", action="store_true", help="Test database only")
    parser.add_argument("--backend", action="store_true", help="Test backend only")
    parser.add_argument("--frontend", action="store_true", help="Test frontend only")
    parser.add_argument("--api", action="store_true", help="Test API endpoints only")
    parser.add_argument("--performance", action="store_true", help="Test performance only")
    parser.add_argument("--notes", action="store_true", help="Test note operations only")
    
    args = parser.parse_args()
    
    tester = EnhancedTester()
    
    if args.comprehensive or not any([args.database, args.backend, args.frontend, args.api, args.performance, args.notes]):
        tester.run_comprehensive_test()
    else:
        if args.database:
            tester.test_database_health()
        if args.backend:
            tester.test_backend_health()
        if args.frontend:
            tester.test_frontend_health()
        if args.api:
            tester.test_api_endpoints()
        if args.performance:
            tester.test_performance()
        if args.notes:
            tester.test_note_operations()
    
    # Print final status
    if tester.results["summary"]["failed"] > 0:
        sys.exit(1)  # Exit with error code if tests failed

if __name__ == "__main__":
    main() 