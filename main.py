"""
نقطة الدخول الرئيسية للتطبيق
"""

import uvicorn
import os
from api.fastapi_app import app

def create_directories():
    """إنشاء المجلدات اللازمة"""
    directories = ['static', 'data', 'logs']
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✅ Created directory: {directory}")

def check_dependencies():
    """التحقق من تثبيت المكتبات المطلوبة"""
    try:
        import fastapi
        import ccxt
        import pandas
        import numpy
        print("✅ All dependencies are installed")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Please install requirements: pip install -r requirements.txt")
        return False

if __name__ == "__main__":
    print("""
    🤖 Smart Crypto Pair Trading Bot
    =================================
    
    Features:
    • البحث عن أفضل أزواج التداول بناءً على القوة مقابل BTC
    • تنفيذ صفقات LONG على العملات القوية و SHORT على الضعيفة
    • مراقبة تلقائية وإغلاق عند تحقيق الأهداف
    • إشعارات فورية عبر NTFY
    • واجهة ويب للتحكم والمراقبة
    
    🚀 Starting server...
    """)
    
    # التحقق من التبعيات
    if not check_dependencies():
        exit(1)
    
    # إنشاء المجلدات
    create_directories()
    
    # تشغيل الخادم
    uvicorn.run(
        "api.fastapi_app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
