# إعدادات التداول (تعديل)
TRADE_SETTINGS = {
    'total_capital_usdt': 5,          # إجمالي رأس المال بالدولار
    'risk_per_trade': 20,              # نسبة المخاطرة لكل صفقة (2%)
    'min_pair_score': 70,
    'max_open_trades': 1,
    'take_profit_ratio': 2.0,
    'stop_loss_ratio': 1.0,
    'check_interval_minutes': 5,
    'scan_interval_hours': 1,
    'leverage': 50,                     # ⭐ إضافة: الرافعة المالية
    'position_size_usdt': 50,           # ⭐ إضافة: حجم المركز لكل عملة
    'contract_type': 'future',          # ⭐ إضافة: نوع العقود
    'margin_mode': 'cross'              # ⭐ إضافة: وضع الهامش (cross أو isolated)
}

# إعدادات Binance Futures (جديد كلياً)
BINANCE_CONFIG = {
    'enable_rate_limit': True,
    'options': {
        'defaultType': 'future',        # ⭐ تغيير من 'spot' إلى 'future'
        'adjustForTimeDifference': True,
    },
    'api_key': '',
    'api_secret': '',
}

# رموز العقود الآجلة (تعديل)
COINS_TO_MONITOR = [
    #"ETH/USDT:USDT",    # ⭐ إضافة :USDT للعقود الآجلة
    #"BNB/USDT:USDT",
    #"SOL/USDT:USDT",
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
    "XLM/USDT:USDT"
]
