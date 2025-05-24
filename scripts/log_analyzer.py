#!/usr/bin/env python3
"""
Log Analyzer Tool
Helps analyze and debug application logs.
"""

import argparse
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any
import json

class LogAnalyzer:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.log_dir = self.project_root / "backend" / "logs"
        
    def find_log_files(self, hours_back: int = 24) -> List[Path]:
        """Find log files modified within the specified hours"""
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        log_files = []
        
        if self.log_dir.exists():
            for log_file in self.log_dir.glob("*.log"):
                if datetime.fromtimestamp(log_file.stat().st_mtime) > cutoff_time:
                    log_files.append(log_file)
                    
        return sorted(log_files, key=lambda x: x.stat().st_mtime, reverse=True)
    
    def parse_log_entry(self, line: str) -> Dict[str, Any]:
        """Parse a log line into structured data"""
        # Pattern for typical log format: TIMESTAMP - LOGGER - LEVEL - MESSAGE
        pattern = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - ([^-]+) - (\w+) - (.*)"
        match = re.match(pattern, line.strip())
        
        if match:
            return {
                "timestamp": match.group(1),
                "logger": match.group(2).strip(),
                "level": match.group(3),
                "message": match.group(4)
            }
        else:
            return {"raw": line.strip()}
    
    def filter_by_level(self, entries: List[Dict], levels: List[str]) -> List[Dict]:
        """Filter log entries by level"""
        return [entry for entry in entries if entry.get("level") in levels]
    
    def filter_by_logger(self, entries: List[Dict], loggers: List[str]) -> List[Dict]:
        """Filter log entries by logger name"""
        return [entry for entry in entries if any(logger in entry.get("logger", "") for logger in loggers)]
    
    def filter_by_keyword(self, entries: List[Dict], keywords: List[str]) -> List[Dict]:
        """Filter log entries by keywords in message"""
        filtered = []
        for entry in entries:
            message = entry.get("message", entry.get("raw", "")).lower()
            if any(keyword.lower() in message for keyword in keywords):
                filtered.append(entry)
        return filtered
    
    def find_errors(self, log_file: Path) -> List[Dict]:
        """Find all error entries in a log file"""
        entries = []
        
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                entry = self.parse_log_entry(line)
                if entry.get("level") in ["ERROR", "CRITICAL"]:
                    entries.append(entry)
                    
        return entries
    
    def find_database_errors(self, hours_back: int = 24) -> List[Dict]:
        """Find database-related errors"""
        all_entries = []
        
        for log_file in self.find_log_files(hours_back):
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    entry = self.parse_log_entry(line)
                    if any(keyword in entry.get("message", "").lower() 
                          for keyword in ["database", "db", "sql", "sqlite"]):
                        all_entries.append({**entry, "file": log_file.name})
                        
        return all_entries
    
    def summarize_activity(self, hours_back: int = 24) -> Dict[str, Any]:
        """Generate activity summary"""
        summary = {
            "timeframe": f"Last {hours_back} hours",
            "log_files": [],
            "levels": {"ERROR": 0, "WARNING": 0, "INFO": 0, "DEBUG": 0},
            "loggers": {},
            "keywords": {"note": 0, "tag": 0, "database": 0, "api": 0}
        }
        
        for log_file in self.find_log_files(hours_back):
            file_info = {"name": log_file.name, "size_kb": log_file.stat().st_size // 1024}
            
            with open(log_file, 'r', encoding='utf-8') as f:
                line_count = 0
                for line in f:
                    line_count += 1
                    entry = self.parse_log_entry(line)
                    
                    # Count by level
                    level = entry.get("level")
                    if level in summary["levels"]:
                        summary["levels"][level] += 1
                    
                    # Count by logger
                    logger = entry.get("logger", "unknown")
                    summary["loggers"][logger] = summary["loggers"].get(logger, 0) + 1
                    
                    # Count keywords
                    message = entry.get("message", "").lower()
                    for keyword in summary["keywords"]:
                        if keyword in message:
                            summary["keywords"][keyword] += 1
                            
                file_info["lines"] = line_count
                summary["log_files"].append(file_info)
                
        return summary
    
    def tail_logs(self, lines: int = 50, follow: bool = False):
        """Show recent log entries"""
        log_files = self.find_log_files(hours_back=1)
        
        if not log_files:
            print("No recent log files found")
            return
            
        latest_file = log_files[0]
        print(f"📋 Showing last {lines} lines from {latest_file.name}")
        print("=" * 80)
        
        with open(latest_file, 'r', encoding='utf-8') as f:
            file_lines = f.readlines()
            
        for line in file_lines[-lines:]:
            entry = self.parse_log_entry(line)
            if "level" in entry:
                level_emoji = {"ERROR": "🔴", "WARNING": "🟡", "INFO": "🔵", "DEBUG": "⚪"}.get(entry["level"], "")
                print(f"{level_emoji} {entry['timestamp']} [{entry['level']}] {entry['logger']}: {entry['message']}")
            else:
                print(entry.get("raw", ""))

def main():
    parser = argparse.ArgumentParser(description="Log Analyzer Tool")
    parser.add_argument("--errors", action="store_true", help="Show recent errors")
    parser.add_argument("--db-errors", action="store_true", help="Show database errors")
    parser.add_argument("--summary", action="store_true", help="Show activity summary")
    parser.add_argument("--tail", type=int, default=50, help="Show last N lines")
    parser.add_argument("--hours", type=int, default=24, help="Look back N hours")
    parser.add_argument("--level", choices=["ERROR", "WARNING", "INFO", "DEBUG"], help="Filter by level")
    parser.add_argument("--logger", help="Filter by logger name")
    parser.add_argument("--keyword", help="Filter by keyword")
    
    args = parser.parse_args()
    
    analyzer = LogAnalyzer()
    
    if args.errors:
        print("🔍 Finding recent errors...")
        for log_file in analyzer.find_log_files(args.hours):
            errors = analyzer.find_errors(log_file)
            if errors:
                print(f"\n📁 {log_file.name}:")
                for error in errors[-10:]:  # Show last 10 errors per file
                    print(f"  🔴 {error['timestamp']} [{error['logger']}]: {error['message']}")
                    
    elif args.db_errors:
        print("🗄️ Finding database-related entries...")
        db_entries = analyzer.find_database_errors(args.hours)
        for entry in db_entries[-20:]:  # Show last 20
            level_emoji = {"ERROR": "🔴", "WARNING": "🟡", "INFO": "🔵"}.get(entry.get("level"), "")
            print(f"{level_emoji} {entry['timestamp']} [{entry.get('file')}] {entry.get('message', entry.get('raw'))}")
            
    elif args.summary:
        print("📊 Activity Summary")
        summary = analyzer.summarize_activity(args.hours)
        print(f"⏰ {summary['timeframe']}")
        print(f"📁 Log files: {len(summary['log_files'])}")
        
        print("\n📈 Log Levels:")
        for level, count in summary['levels'].items():
            if count > 0:
                emoji = {"ERROR": "🔴", "WARNING": "🟡", "INFO": "🔵", "DEBUG": "⚪"}[level]
                print(f"  {emoji} {level}: {count}")
                
        print("\n🏷️ Top Loggers:")
        top_loggers = sorted(summary['loggers'].items(), key=lambda x: x[1], reverse=True)[:5]
        for logger, count in top_loggers:
            print(f"  📝 {logger}: {count}")
            
        print("\n🔍 Keywords:")
        for keyword, count in summary['keywords'].items():
            if count > 0:
                print(f"  🔎 {keyword}: {count}")
                
    else:
        analyzer.tail_logs(args.tail)

if __name__ == "__main__":
    main() 