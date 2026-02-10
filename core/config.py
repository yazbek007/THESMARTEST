"""
إعدادات البوت الرئيسية - يمكن تعديلها حسب الحاجة
"""

# إعدادات التداول للعقود الآجلة
TRADE_SETTINGS = {
    'total_capital_usdt': 5,          # إجمالي رأس المال بالدولار
    'risk_per_trade': 20,              # نسبة المخاطرة لكل صفقة (20%)
    'min_pair_score': 70,               # أقل درجة لقبول الزوج
    'max_open_trades': 3,               # الحد الأقصى للصفقات المفتوحة
    'take_profit_ratio': 2.0,           # نسبة الربح/المخاطرة (1:2)
    'stop_loss_ratio': 1.0,             # نسبة وقف الخسارة
    'check_interval_minutes': 5,        # فحص الصفقات كل 5 دقائق
    'scan_interval_hours': 1,           # مسح السوق كل ساعة
    'leverage': 50,                     # ⭐ الرافعة المالية 50x
    'position_size_usdt': 50,           # ⭐ حجم المركز لكل عملة (50 دولار)
    'contract_type': 'future',          # ⭐ نوع العقود (future للعقود الآجلة)
    'margin_mode': 'cross',             # ⭐ وضع الهامش (cross أو isolated)
    'use_testnet': True,                # ⭐ استخدام Testnet للتجربة
    'symbol_suffix': ':USDT',           # ⭐ لاحقة رموز العقود الآجلة
}

# إعدادات Binance Futures
BINANCE_CONFIG = {
    'enable_rate_limit': True,
    'options': {
        'defaultType': 'future',        # ⭐ تغيير من 'spot' إلى 'future'
        'adjustForTimeDifference': True,
    },
    # أضف مفتاح API وسري هنا أو في ملف .env
    'api_key': '',  # سيتم تعبئته من .env
    'api_secret': '',  # سيتم تعبئته من .env
    
    # إعدادات Testnet (افتراضية)
    'testnet': {
        'api_key': 'YOUR_TESTNET_API_KEY',  # استبدل بمفاتيح Testnet
        'api_secret': 'YOUR_TESTNET_SECRET',
        'urls': {
            'public': 'https://testnet.binancefuture.com/fapi/v1',
            'private': 'https://testnet.binancefuture.com/fapi/v1'
        }
    },
    
    # إعدادات الإنتاج
    'production': {
        'urls': {
            'public': 'https://fapi.binance.com/fapi/v1',
            'private': 'https://fapi.binance.com/fapi/v1'
        }
    }
}

# العملات التي يتم مراقبتها (العقود الآجلة)
COINS_TO_MONITOR = [
    "ETH/USDT:USDT",    # ⭐ إضافة :USDT للعقود الآجلة
    "BNB/USDT:USDT",
    "SOL/USDT:USDT",
    "XRP/USDT:USDT",
    "ADA/USDT:USDT",
    "DOGE/USDT:USDT",
    "DOT/USDT:USDT",
    "AVAX/USDT:USDT",
    "MATIC/USDT:USDT",
    "LINK/USDT:USDT",
    "ATOM/USDT:USDT",
    "UNI/USDT:USDT",
    "LTC/USDT:USDT",
    "TRX/USDT:USDT",
    "XLM/USDT:USDT",
    "BTC/USDT:USDT",    # إضافة BTC أيضاً للمقارنة
]

# ⭐⭐⭐ **إضافة NTFY_CONFIG المفقود** ⭐⭐⭐
NTFY_CONFIG = {
    'server_url': 'https://ntfy.sh',
    'topic': 'crypto_pair_bot',  # استبدل بموضوعك الخاص على ntfy.sh
    'priority_high': 'high',
    'priority_normal': 'default',
    'priority_urgent': 'urgent',
    'tags': {
        'success': ['white_check_mark', 'rocket'],
        'error': ['warning', 'x'],
        'trade': ['moneybag', 'chart_increasing'],
        'signal': ['rocket', 'chart_increasing'],
        'alert': ['bell', 'exclamation']
    }
}

# إعدادات قاعدة البيانات
DATABASE_CONFIG = {
    'path': 'data/trading_bot.db',
    'cleanup_days': 30,  # تنظيف البيانات الأقدم من 30 يوم
    'tables': {
        'trades': 'futures_trades',
        'signals': 'pair_signals',
        'settings': 'system_settings'
    }
}

# إعدادات التسجيل (Logging)
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file': 'logs/crypto_bot.log',
    'max_size_mb': 10,
    'backup_count': 5
}

# إعدادات نظام التحذيرات
ALERT_CONFIG = {
    'enable_ntfy': True,
    'enable_email': False,
    'enable_telegram': False,
    'min_score_alert': 80,  # إرسال إشعار عند درجة 80+
    'min_pnl_alert': 5.0,   # إرسال إشعار عند ربح/خسارة 5%+
    'market_crash_threshold': -10.0,  # عتبة انهيار السوق
}

# إعدادات الاستراتيجية
STRATEGY_CONFIG = {
    'pair_trading': {
        'min_score_diff': 20,
        'min_perf_diff': 3.0,
        'max_trade_duration_hours': 24,
        'correlation_threshold': 0.7,
        'use_advanced_indicators': True,
        'include_sentiment': False
    },
    'risk_management': {
        'max_daily_loss_percent': 5.0,
        'max_consecutive_losses': 3,
        'position_sizing_method': 'fixed',  # fixed أو dynamic
        'dynamic_sizing_multiplier': 1.0
    }
}

# وظيفة لتحميل الإعدادات من ملف .env (اختياري)
def load_env_settings():
    """تحميل الإعدادات من ملف .env إذا كان موجوداً"""
    import os
    from dotenv import load_dotenv
    
    env_file = '.env'
    if os.path.exists(env_file):
        load_dotenv(env_file)
        
        # تحديث إعدادات Binance من .env
        if os.getenv('BINANCE_API_KEY'):
            BINANCE_CONFIG['api_key'] = os.getenv('BINANCE_API_KEY')
        if os.getenv('BINANCE_API_SECRET'):
            BINANCE_CONFIG['api_secret'] = os.getenv('BINANCE_API_SECRET')
        
        # تحديث إعدادات NTFY من .env
        if os.getenv('NTFY_TOPIC'):
            NTFY_CONFIG['topic'] = os.getenv('NTFY_TOPIC')
        if os.getenv('NTFY_SERVER'):
            NTFY_CONFIG['server_url'] = os.getenv('NTFY_SERVER')
        
        # تحديث إعدادات التداول من .env
        if os.getenv('TRADE_CAPITAL'):
            TRADE_SETTINGS['total_capital_usdt'] = float(os.getenv('TRADE_CAPITAL'))
        if os.getenv('TRADE_LEVERAGE'):
            TRADE_SETTINGS['leverage'] = int(os.getenv('TRADE_LEVERAGE'))
        if os.getenv('POSITION_SIZE'):
            TRADE_SETTINGS['position_size_usdt'] = float(os.getenv('POSITION_SIZE'))
        if os.getenv('USE_TESTNET'):
            TRADE_SETTINGS['use_testnet'] = os.getenv('USE_TESTNET').lower() == 'true'
        
        print(f"✅ تم تحميل الإعدادات من {env_file}")
    else:
        print(f"⚠️ ملف {env_file} غير موجود، استخدام الإعدادات الافتراضية")

# تحميل الإعدادات عند استيراد الملف
try:
    load_env_settings()
except ImportError:
    print("⚠️ python-dotenv غير مثبت، استخدام الإعدادات الافتراضية")
except Exception as e:
    print(f"⚠️ خطأ في تحميل الإعدادات: {e}")

# طباعة الإعدادات الحالية (للتصحيح)
def print_current_settings():
    """طباعة الإعدادات الحالية للتصحيح"""
    print("\n" + "="*50)
    print("الإعدادات الحالية للبوت:")
    print("="*50)
    
    print(f"\n🔧 إعدادات التداول:")
    for key, value in TRADE_SETTINGS.items():
        print(f"  {key}: {value}")
    
    print(f"\n💰 إعدادات Binance:")
    print(f"  API Key: {'****' if BINANCE_CONFIG.get('api_key') else 'غير مضبوط'}")
    print(f"  Testnet: {TRADE_SETTINGS.get('use_testnet', True)}")
    print(f"  Leverage: {TRADE_SETTINGS.get('leverage', 50)}x")
    
    print(f"\n🔔 إعدادات NTFY:")
    print(f"  Topic: {NTFY_CONFIG.get('topic', 'غير مضبوط')}")
    print(f"  Server: {NTFY_CONFIG.get('server_url', 'غير مضبوط')}")
    
    print(f"\n📊 العملات المراقبة: {len(COINS_TO_MONITOR)} عملة")
    print("="*50 + "\n")

# طباعة الإعدادات عند الاستيراد المباشر
if __name__ == "__main__":
    print_current_settings()
