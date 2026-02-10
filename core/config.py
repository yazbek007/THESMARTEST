"""
إعدادات البوت الرئيسية - يمكن تعديلها حسب الحاجة
"""

# إعدادات التداول
TRADE_SETTINGS = {
    'total_capital_usdt': 500,          # إجمالي رأس المال بالدولار
    'risk_per_trade': 2.0,              # نسبة المخاطرة لكل صفقة (2%)
    'min_pair_score': 70,               # أقل درجة لقبول الزوج
    'max_open_trades': 3,               # الحد الأقصى للصفقات المفتوحة
    'take_profit_ratio': 2.0,           | نسبة الربح/المخاطرة (1:2)
    'stop_loss_ratio': 1.0,             | نسبة وقف الخسارة
    'check_interval_minutes': 5,        | فحص الصفقات كل 5 دقائق
    'scan_interval_hours': 1,           | مسح السوق كل ساعة
}

# إعدادات Binance
BINANCE_CONFIG = {
    'enable_rate_limit': True,
    'options': {'defaultType': 'spot'},
    # أضف مفتاح API وسري هنا أو في ملف .env
    'api_key': '',  # سيتم تعبئته من .env
    'api_secret': '',  # سيتم تعبئته من .env
}

# العملات التي يتم مراقبتها
COINS_TO_MONITOR = [
    "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT",
    "ADA/USDT", "DOGE/USDT", "DOT/USDT", "AVAX/USDT",
    "MATIC/USDT", "LINK/USDT", "ATOM/USDT", "UNI/USDT",
    "LTC/USDT", "TRX/USDT", "XLM/USDT"
]

# إعدادات NTFY
NTFY_CONFIG = {
    'server_url': 'https://ntfy.sh',
    'topic': 'crypto_pair_bot',  # استبدل بموضوعك الخاص
    'priority_high': 'high',
    'priority_normal': 'default'
}

# إعدادات قاعدة البيانات
DATABASE_CONFIG = {
    'path': 'data/trading_bot.db',
    'cleanup_days': 30  | تنظيف البيانات الأقدم من 30 يوم
}
