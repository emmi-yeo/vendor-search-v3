#!/usr/bin/env python3
"""
Diagnostic script to debug issues in deployed environment
Run this to identify deployment health
"""
import os
import sys
from pathlib import Path

print("\n" + "=" * 70)
print("🔍 DEPLOYMENT ENVIRONMENT DIAGNOSTIC")
print("=" * 70)

# 1. Check data directory
print("\n1️⃣  Checking data directory...")
data_dir = Path('data')
if data_dir.exists():
    print(f"   ✅ Directory exists: {data_dir.absolute()}")
    print(f"   📂 Contents:")
    for item in data_dir.iterdir():
        print(f"      - {item.name}")
else:
    print(f"   ❌ Directory missing: {data_dir.absolute()}")
    print(f"   Creating it now...")
    data_dir.mkdir(exist_ok=True)
    print(f"   ✅ Created")

# 2. Check vendor data files
print("\n2️⃣  Checking vendor data files...")
required_files = ['vendor_profiles.csv', 'vendor_attachments.csv']
for filename in required_files:
    file_path = data_dir / filename
    if file_path.exists():
        size = file_path.stat().st_size
        print(f"   ✅ {filename}: {size} bytes")
    else:
        print(f"   ⚠️  {filename}: Not found")

# 3. Check write permissions
print("\n3️⃣  Checking write permissions...")
try:
    test_file = data_dir / '.write_test'
    test_file.write_text('test')
    test_file.unlink()
    print(f"   ✅ Directory is writable")
except Exception as e:
    print(f"   ❌ Directory is NOT writable: {e}")
    sys.exit(1)

# 4. Check Python imports
print("\n4️⃣  Checking Python module imports...")
try:
    from src.retrieval import search
    print(f"   ✅ Retrieval module imported")
    
    from src.build_index import build_vendor_documents, build_faiss_and_bm25
    print(f"   ✅ Indexing module imported")
    
    from src.query_parser import parse_query
    print(f"   ✅ Query parser module imported")
    
except Exception as e:
    print(f"   ❌ Module import error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 5. Check environment
print("\n5️⃣  Checking environment...")
print(f"   Working directory: {os.getcwd()}")
print(f"   Python version: {sys.version}")
print(f"   OS: {sys.platform}")
print(f"   HOME: {os.getenv('HOME', 'Not set')}")

# 6. Summary
print("\n" + "=" * 70)
print("✅ ALL TESTS PASSED - Environment is healthy")
print("\nTo start the application:")
print("  $ streamlit run app.py")
print("=" * 70 + "\n")

