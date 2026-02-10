"""
إعدادات البوت الرئيسية للعقود الآجلة على Binance
Crypto Pair Trading Bot - Futures Configuration
"""

import os
from datetime import datetime

# ============================================
# 🔧 إعدادات النظام الأساسية
# ============================================
APP_NAME = "Smart Crypto Pair Trading Bot"
APP_VERSION = "2.0.0"
APP_DESCRIPTION = "بوت ذكي لتداول أزواج العملات الرقمية على Binance Futures"
TIMEZONE = "Asia/Damascus"  # توقيت سورية

# ============================================
# 💰 إعدادات التداول للعقود الآجلة
# ============================================
TRADE_SETTINGS = {
    # إعدادات رأس المال والمخاطرة
    'total_capital_usdt': 5,           # إجمالي رأس المال بالدولار
    'risk_per_trade': 20,               # نسبة المخاطرة لكل صفقة (2%)
    'max_daily_loss_percent': 5.0,       # الحد الأقصى للخسارة اليومية (5%)
    
    # إعدادات اكتشاف الأزواج
    'min_pair_score': 70,                # أقل درجة لقبول الزوج
    'min_score_difference': 20,          # أقل فرق في القوة بين العملتين
    'min_performance_difference': 3.0,   # أقل فرق في الأداء مقابل BTC
    
    # إعدادات إدارة الصفقات
    'max_open_trades': 3,                # الحد الأقصى للصفقات المفتوحة
    'max_consecutive_losses': 3,         # الحد الأقصى للخسائر المتتالية
    'take_profit_ratio': 2.0,            # نسبة الربح/المخاطرة (1:2)
    'stop_loss_ratio': 1.0,              # نسبة وقف الخسارة الأساسية
    
    # إعدادات التوقيت
    'check_interval_minutes': 5,         # فحص الصفقات كل 5 دقائق
    'scan_interval_hours': 1,            # مسح السوق كل ساعة
    'max_trade_duration_hours': 24,      # الحد الأقصى لمدة الصفقة (24 ساعة)
    
    # ⭐⭐ إعدادات العقود الآجلة ⭐⭐
    'leverage': 50,                      # الرافعة المالية 50x
    'position_size_usdt': 50,            # حجم المركز لكل عملة (50 دولار)
    'contract_type': 'future',           # نوع العقود (future للعقود الآجلة)
    'margin_mode': 'cross',              # وضع الهامش (cross أو isolated)
    'symbol_suffix': ':USDT',            # لاحقة رموز العقود الآجلة
    
    # إعدادات التحكم
    'auto_trading': True,                # التداول التلقائي
    'use_stop_loss': True,               # استخدام وقف الخسارة
    'use_take_profit': True,             # استخدام جني الأرباح
    'enable_notifications': True,        # تمكين الإشعارات
}

# ============================================
# 🔐 إعدادات Binance API
# ============================================
def get_binance_config():
    """الحصول على إعدادات Binance مع مفاتيح API"""
    
    # ⭐⭐ الحصول على المفاتيح من متغيرات البيئة ⭐⭐
    api_key = os.getenv('BINANCE_API_KEY', '')
    api_secret = os.getenv('BINANCE_API_SECRET', '')
    
    # ⭐⭐ التحقق من وجود المفاتيح ⭐⭐
    keys_status = "✅ مضبوط" if api_key and api_secret else "❌ غير مضبوط"
    
    # تحديد وضع التشغيل (Testnet أو Production)
    use_testnet = os.getenv('USE_TESTNET', 'true').lower() == 'true'
    
    if use_testnet:
        print("🔧 وضع التشغيل: Binance Futures Testnet")
        if not api_key or not api_secret:
            # مفاتيح Testnet افتراضية (للتجربة فقط)
            api_key = os.getenv('BINANCE_TESTNET_API_KEY', 'testnet_api_key')
            api_secret = os.getenv('BINANCE_TESTNET_SECRET', 'testnet_secret')
    else:
        print("🚀 وضع التشغيل: Binance Futures Production")
        if not api_key or not api_secret:
            print("⚠️  تحذير: لم يتم تعيين مفاتيح Binance API الحقيقية!")
            print("   أضفها في Render Dashboard → Environment Variables")
            print("   أو أنشئ ملف .env في المجلد الرئيسي")
    
    config = {
        'enable_rate_limit': True,
        'options': {
            'defaultType': 'future',
            'adjustForTimeDifference': True,
            'defaultMarginMode': TRADE_SETTINGS['margin_mode'],
        },
        'api_key': api_key,
        'api_secret': api_secret,
        
        # ⭐⭐ إعدادات Testnet ⭐⭐
        'testnet': use_testnet,
        'testnet_urls': {
            'public': 'https://testnet.binancefuture.com/fapi/v1',
            'private': 'https://testnet.binancefuture.com/fapi/v1',
        },
        
        # ⭐⭐ إعدادات Production ⭐⭐
        'production_urls': {
            'public': 'https://fapi.binance.com/fapi/v1',
            'private': 'https://fapi.binance.com/fapi/v1',
        }
    }
    
    return config, keys_status, use_testnet

# إنشاء إعدادات Binance
BINANCE_CONFIG, API_KEYS_STATUS, USE_TESTNET = get_binance_config()
TRADE_SETTINGS['use_testnet'] = USE_TESTNET

# ============================================
# 📊 قائمة العملات المراقبة (العقود الآجلة)
# ============================================
COINS_TO_MONITOR = [
    # العملات الرئيسية
    "BTC/USDT:USDT",    # Bitcoin
    "ETH/USDT:USDT",    # Ethereum
    "BNB/USDT:USDT",    # Binance Coin
    "SOL/USDT:USDT",    # Solana
    "XRP/USDT:USDT",    # Ripple
    
    # العملات المتوسطة
    "ADA/USDT:USDT",    # Cardano
    "DOGE/USDT:USDT",   # Dogecoin
    "DOT/USDT:USDT",    # Polkadot
    "AVAX/USDT:USDT",   # Avalanche
    "MATIC/USDT:USDT",  # Polygon
    
    # العملات الصغيرة
    "LINK/USDT:USDT",   # Chainlink
    "ATOM/USDT:USDT",   # Cosmos
    "UNI/USDT:USDT",    # Uniswap
    "LTC/USDT:USDT",    # Litecoin
    "TRX/USDT:USDT",    # Tron
    
    # إضافات
    "XLM/USDT:USDT",    # Stellar
    "ETC/USDT:USDT",    # Ethereum Classic
    "FIL/USDT:USDT",    # Filecoin
    "ALGO/USDT:USDT",   # Algorand
    "NEAR/USDT:USDT",   # Near Protocol
]

# ============================================
# 🔔 إعدادات NTFY للإشعارات
# ============================================
def get_ntfy_config():
    """الحصول على إعدادات NTFY"""
    
    topic = os.getenv('NTFY_TOPIC', 'crypto_pair_bot')
    server_url = os.getenv('NTFY_SERVER', 'https://ntfy.sh')
    
    return {
        'server_url': server_url,
        'topic': topic,
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

NTFY_CONFIG = get_ntfy_config()

# ============================================
# 🗄️ إعدادات قاعدة البيانات
# ============================================
DATABASE_CONFIG = {
    'path': 'data/trading_bot.db',
    'cleanup_days': 30,                    # تنظيف البيانات الأقدم من 30 يوم
    'backup_days': 7,                      # احتفظ بنسخ احتياطية لـ 7 أيام
    
    'tables': {
        'trades': 'futures_trades',
        'signals': 'pair_signals',
        'settings': 'system_settings',
        'notifications': 'notifications_log',
        'performance': 'performance_history',
    },
    
    'retention': {
        'trades': 90,                      # احتفظ بالصفقات لـ 90 يوم
        'signals': 30,                     # احتفظ بالإشارات لـ 30 يوم
        'logs': 7,                         # احتفظ بالسجلات لـ 7 أيام
    }
}

# ============================================
# 📝 إعدادات التسجيل (Logging)
# ============================================
LOGGING_CONFIG = {
    'level': 'INFO',                       # INFO, DEBUG, WARNING, ERROR
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'date_format': '%Y-%m-%d %H:%M:%S',
    'file': 'logs/crypto_bot.log',
    'max_size_mb': 10,                     # الحد الأقصى لحجم الملف
    'backup_count': 5,                     # عدد ملفات النسخ الاحتياطية
    'handlers': ['file', 'console'],       # file, console, or both
}

# ============================================
# ⚠️ إعدادات نظام التحذيرات
# ============================================
ALERT_CONFIG = {
    'enable_ntfy': True,
    'enable_email': False,
    'enable_telegram': False,
    
    'thresholds': {
        'min_score_alert': 80,             # إرسال إشعار عند درجة 80+
        'min_pnl_alert': 5.0,              # إرسال إشعار عند ربح/خسارة 5%+
        'market_crash_threshold': -10.0,   # عتبة انهيار السوق
        'high_volatility_threshold': 8.0,  # عتبة التقلب العالي
    },
    
    'schedules': {
        'daily_summary': '08:00',          # إرسال ملخص يومي الساعة 8 صباحاً
        'weekly_report': 'monday 09:00',   # تقرير أسبوعي يوم الإثنين
        'monthly_analysis': '1 10:00',     # تحليل شهري أول كل شهر
    }
}

# ============================================
# 🧠 إعدادات الاستراتيجية
# ============================================
STRATEGY_CONFIG = {
    'pair_trading': {
        'method': 'relative_strength',     # relative_strength, correlation, cointegration
        'min_correlation': 0.7,            # الحد الأدنى للارتباط
        'max_correlation': 0.95,           # الحد الأقصى للارتباط
        'cointegration_pvalue': 0.05,      # قيمة p للتقارب
        'zscore_entry': 2.0,               # نقطة الدخول عند Z-Score
        'zscore_exit': 0.5,                # نقطة الخروج عند Z-Score
    },
    
    'indicators': {
        'use_rsi': True,
        'use_atr': True,
        'use_macd': False,
        'use_bollinger': False,
        'rsi_period': 14,
        'atr_period': 14,
        'bollinger_period': 20,
        'bollinger_std': 2,
    },
    
    'risk_management': {
        'position_sizing_method': 'fixed',  # fixed, kelly, optimal_f
        'dynamic_sizing': False,
        'portfolio_risk': 0.02,             # مخاطرة المحفظة الإجمالية
        'max_drawdown': 0.20,               # الحد الأقصى للتراجع
    }
}

# ============================================
# 🎯 أوزان تقييم العملات (0-100)
# ============================================
SCORE_WEIGHTS = {
    'performance_vs_btc': 40,              # الأداء مقابل BTC
    'momentum': 25,                        # الزخم (RSI)
    'volatility_score': 15,                # درجة التقلب
    'liquidity_score': 10,                 # درجة السيولة
    'volume_trend': 10,                    # اتجاه الحجم
}

# ============================================
# ⚖️ عتبات التحليل الفني
# ============================================
TECHNICAL_THRESHOLDS = {
    'rsi_oversold': 30,                    # RSI ذروة بيع
    'rsi_overbought': 70,                  # RSI ذروة شراء
    'atr_high': 5.0,                       # ATR مرتفع
    'atr_low': 1.0,                        # ATR منخفض
    'volume_spike': 2.0,                   # ارتفاع مفاجئ في الحجم
    'min_liquidity_usd': 1000000,          # أقل سيولة مقبولة (1 مليون دولار)
}

# ============================================
# 🔧 وظائف المساعدة
# ============================================
def print_config_summary():
    """طباعة ملخص الإعدادات"""
    
    print("\n" + "="*60)
    print("🤖 Smart Crypto Pair Trading Bot - Configuration")
    print("="*60)
    
    print(f"\n📊 معلومات النظام:")
    print(f"  التطبيق: {APP_NAME} v{APP_VERSION}")
    print(f"  الوصف: {APP_DESCRIPTION}")
    print(f"  المنطقة الزمنية: {TIMEZONE}")
    print(f"  الوقت الحالي: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    print(f"\n💰 إعدادات التداول:")
    print(f"  وضع التشغيل: {'TESTNET ⚠️' if USE_TESTNET else 'PRODUCTION 🚀'}")
    print(f"  الرافعة: {TRADE_SETTINGS['leverage']}x")
    print(f"  حجم الصفقة: ${TRADE_SETTINGS['position_size_usdt']} لكل عملة")
    print(f"  رأس المال: ${TRADE_SETTINGS['total_capital_usdt']}")
    print(f"  المخاطرة/صفقة: {TRADE_SETTINGS['risk_per_trade']}%")
    
    print(f"\n🔐 إعدادات API:")
    print(f"  Binance API Keys: {API_KEYS_STATUS}")
    print(f"  مفاتيح مضبوطة: {'نعم' if BINANCE_CONFIG['api_key'] and BINANCE_CONFIG['api_secret'] else 'لا'}")
    
    print(f"\n📈 المراقبة:")
    print(f"  عدد العملات: {len(COINS_TO_MONITOR)} عملة")
    print(f"  فحص الصفقات: كل {TRADE_SETTINGS['check_interval_minutes']} دقيقة")
    print(f"  مسح السوق: كل {TRADE_SETTINGS['scan_interval_hours']} ساعة")
    
    print(f"\n🔔 الإشعارات:")
    print(f"  NTFY Topic: {NTFY_CONFIG['topic']}")
    print(f"  NTFY Server: {NTFY_CONFIG['server_url']}")
    print(f"  الإشعارات مفعلة: {'نعم' if TRADE_SETTINGS['enable_notifications'] else 'لا'}")
    
    print(f"\n💾 التخزين:")
    print(f"  قاعدة البيانات: {DATABASE_CONFIG['path']}")
    print(f"  حفظ السجلات: {LOGGING_CONFIG['file']}")
    
    print(f"\n🎯 الاستراتيجية:")
    print(f"  طريقة التداول: {STRATEGY_CONFIG['pair_trading']['method']}")
    print(f"  الحد الأدنى لدرجة الزوج: {TRADE_SETTINGS['min_pair_score']}")
    print(f"  الحد الأقصى للصفقات: {TRADE_SETTINGS['max_open_trades']}")
    
    print("\n" + "="*60)
    
    # ⚠️ تحذيرات مهمة
    if not USE_TESTNET:
        print("\n⚠️  تحذيرات مهمة للتداول الحقيقي:")
        print("  1. البوت سيتداول بأموال حقيقية!")
        print("  2. التداول يحمل مخاطر فقدان رأس المال!")
        print("  3. تأكد من فهمك للاستراتيجية!")
        print("  4. ابدأ بمبالغ صغيرة للاختبار!")
        print("="*60)

def validate_config():
    """التحقق من صحة الإعدادات"""
    
    errors = []
    warnings = []
    
    # التحقق من مفاتيح API
    if not BINANCE_CONFIG['api_key'] or not BINANCE_CONFIG['api_secret']:
        if USE_TESTNET:
            warnings.append("⚠️  مفاتيح Testnet غير مضبوطة، قد لا يعمل جلب البيانات")
        else:
            errors.append("❌ مفاتيح Binance API الحقيقية غير مضبوطة!")
    
    # التحقق من حجم الصفقة
    if TRADE_SETTINGS['position_size_usdt'] * TRADE_SETTINGS['leverage'] > TRADE_SETTINGS['total_capital_usdt']:
        warnings.append(f"⚠️  حجم الصفقة ({TRADE_SETTINGS['position_size_usdt']}$ × {TRADE_SETTINGS['leverage']}x) قد يتجاوز رأس المال")
    
    # التحقق من الرافعة
    if TRADE_SETTINGS['leverage'] > 100:
        warnings.append(f"⚠️  الرافعة عالية جداً ({TRADE_SETTINGS['leverage']}x) - خطر التصفية مرتفع")
    
    # التحقق من عدد العملات
    if len(COINS_TO_MONITOR) < 5:
        warnings.append(f"⚠️  عدد العملات قليل جداً ({len(COINS_TO_MONITOR)}) - قد لا يجد أزواج مناسبة")
    
    # إرجاع النتائج
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings
    }

# ============================================
# 📦 تهيئة النظام
# ============================================
if __name__ == "__main__":
    # طباعة ملخص الإعدادات
    print_config_summary()
    
    # التحقق من صحة الإعدادات
    validation = validate_config()
    
    if validation['errors']:
        print("\n❌ أخطاء في الإعدادات:")
        for error in validation['errors']:
            print(f"  {error}")
    
    if validation['warnings']:
        print("\n⚠️  تحذيرات:")
        for warning in validation['warnings']:
            print(f"  {warning}")
    
    if validation['valid']:
        print("\n✅ جميع الإعدادات صحيحة وجاهزة للتشغيل!")
    else:
        print("\n❌ يوجد أخطاء تحتاج للإصلاح قبل التشغيل!")

# ============================================
# 🎨 ألوان لوحة التحكم (اختياري)
# ============================================
UI_CONFIG = {
    'theme': 'dark',  # dark, light, auto
    'colors': {
        'primary': '#3b82f6',      # أزرق
        'success': '#10b981',      # أخضر
        'warning': '#f59e0b',      # برتقالي
        'danger': '#ef4444',       # أحمر
        'dark': '#0f172a',         # داكن
        'light': '#f8fafc',        # فاتح
    },
    'animations': True,
    'auto_refresh': True,
}
