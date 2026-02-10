"""
واجهة API الرئيسية للبوت باستخدام FastAPI
"""
"""
واجهة API الرئيسية للبوت باستخدام FastAPI
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta
import asyncio
import logging
import os

from core.pair_finder import SmartPairFinder
from core.trade_executor import FuturesTradeExecutor  # ⭐ تغيير هنا
from core.config import TRADE_SETTINGS, NTFY_CONFIG

# إعداد التطبيق
app = FastAPI(
    title="Smart Crypto Pair Trading Bot (Futures)",
    description="بوت ذكي لتداول أزواج العملات الرقمية على Binance Futures",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# إعداد CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# تهيئة المكونات
pair_finder = SmartPairFinder(use_testnet=True)
trade_executor = FuturesTradeExecutor(use_testnet=True)  # ⭐ تغيير هنا
monitoring_task = None
auto_scan_task = None

# نماذج البيانات
class TradeRequest(BaseModel):
    amount_usdt: float = TRADE_SETTINGS['total_capital_usdt']
    auto_execute: bool = True

class NotificationRequest(BaseModel):
    title: str
    message: str
    priority: str = "default"
    tags: list = []

# حالة النظام
system_status = {
    "started": False,
    "start_time": None,
    "total_scans": 0,
    "total_trades": 0,
    "last_scan": None,
    "last_trade": None,
    "errors": []
}

# وظائف المساعدة
async def send_ntfy_notification(title: str, message: str, 
                                priority: str = "default", tags: list = None):
    """إرسال إشعار إلى NTFY"""
    import requests
    
    url = f"{NTFY_CONFIG['server_url']}/{NTFY_CONFIG['topic']}"
    
    headers = {
        "Title": title.encode('utf-8'),
        "Priority": priority,
        "Tags": ",".join(tags) if tags else ""
    }
    
    try:
        # إضافة وقت سورية
        syria_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_message = f"{message}\n\n🕒 الوقت: {syria_time}"
        
        response = requests.post(url, data=full_message.encode('utf-8'), headers=headers)
        
        if response.status_code == 200:
            logging.info(f"Notification sent: {title}")
            return True
        else:
            logging.error(f"Failed to send notification: {response.status_code}")
            return False
            
    except Exception as e:
        logging.error(f"Error sending notification: {e}")
        return False

async def monitor_trades_background():
    """مراقبة الصفقات في الخلفية"""
    while True:
        try:
            # مراقبة الصفقات النشطة
            closed_trades = await trade_executor.monitor_active_trades()
            
            # إرسال إشعارات للصفقات المغلقة
            for trade in closed_trades:
                emoji = "✅" if trade.pnl_usdt > 0 else "❌"
                pnl_sign = "+" if trade.pnl_usdt > 0 else ""
                
                await send_ntfy_notification(
                    title=f"{emoji} صفقة مغلقة",
                    message=f"الزوج: {trade.pair_signal['pair']}\n"
                           f"السبب: {trade.close_reason}\n"
                           f"الربح: {pnl_sign}{trade.pnl_percent:.2f}% (${pnl_sign}{trade.pnl_usdt:.2f})",
                    priority="high" if trade.pnl_usdt > 0 else "default",
                    tags=["check_mark_button" if trade.pnl_usdt > 0 else "cross_mark", "moneybag"]
                )
            
            # تحديث حالة النظام
            system_status['total_trades'] = len(trade_executor.closed_trades)
            
        except Exception as e:
            logging.error(f"Error in trade monitoring: {e}")
            system_status['errors'].append(str(e))
        
        # الانتظار للدورة القادمة
        await asyncio.sleep(TRADE_SETTINGS['check_interval_minutes'] * 60)

async def auto_scan_background():
    """مسح تلقائي للأسواق في الخلفية"""
    while True:
        try:
            # البحث عن أفضل زوج
            best_pair = await pair_finder.find_best_trading_pair()
            
            # ⭐⭐ **تصحيح السطر 135:** ⭐⭐
            if best_pair and best_pair['pair_score'] >= 80:  # إشارة قوية جداً
                # إرسال إشعار
                await send_ntfy_notification(
                    title="🎯 إشارة تلقائية قوية",
                    message=f"الزوج: {best_pair['pair']}\n"
                           f"الدرجة: {best_pair['pair_score']:.1f}\n"
                           f"التوصية: {best_pair['recommendation']}",
                    priority="high",
                    tags=["rocket", "chart_increasing"]
                )
                
                # تنفيذ تلقائي إذا كان ممكناً
                if len(trade_executor.active_trades) < TRADE_SETTINGS['max_open_trades']:
                    trade = await trade_executor.execute_pair_trade(best_pair)
                    if trade:
                        await send_ntfy_notification(
                            title="🚀 صفقة تلقائية مفتوحة",
                            message=f"الزوج: {best_pair['pair']}\n"
                                   f"تم فتح صفقة تلقائياً",
                            priority="urgent",
                            tags=["automobile", "rocket"]
                        )
            
            # تحديث حالة النظام
            system_status['last_scan'] = datetime.now().isoformat()
            system_status['total_scans'] += 1
            
        except Exception as e:
            logging.error(f"Error in auto scan: {e}")
            system_status['errors'].append(str(e))
        
        # الانتظار للدورة القادمة
        await asyncio.sleep(TRADE_SETTINGS['scan_interval_hours'] * 3600)

# نقاط النهاية
@app.on_event("startup")
async def startup_event():
    """بدء النظام عند التشغيل"""
    logging.info("🚀 Starting Smart Crypto Pair Trading Bot (FUTURES)...")
    logging.info(f"   Leverage: {TRADE_SETTINGS['leverage']}x")
    logging.info(f"   Position size: ${TRADE_SETTINGS['position_size_usdt']} per coin")
    
    system_status['started'] = True
    system_status['start_time'] = datetime.now().isoformat()
    
    # بدء مهام الخلفية
    global monitoring_task, auto_scan_task
    monitoring_task = asyncio.create_task(monitor_trades_background())
    auto_scan_task = asyncio.create_task(auto_scan_background())
    
    # إرسال إشعار بدء التشغيل
    await send_ntfy_notification(
        title="🚀 بدء تشغيل البوت (Futures)",
        message=f"تم بدء تشغيل بوت التداول الزوجي على العقود الآجلة\n"
               f"الرافعة: {TRADE_SETTINGS['leverage']}x\n"
               f"حجم الصفقة: ${TRADE_SETTINGS['position_size_usdt']} لكل عملة",
        tags=["white_check_mark", "rocket"]
    )
    
    logging.info("✅ Bot started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """إيقاف النظام عند الإغلاق"""
    if monitoring_task:
        monitoring_task.cancel()
    if auto_scan_task:
        auto_scan_task.cancel()
    
    await send_ntfy_notification(
        title="🛑 إيقاف البوت",
        message="تم إيقاف بوت التداول الزوجي",
        tags=["stop_sign", "warning"]
    )
    
    logging.info("🛑 Bot stopped")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """الصفحة الرئيسية (لوحة التحكم)"""
    try:
        with open("static/dashboard.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>لوحة التحكم غير متوفرة</h1>")

@app.get("/api/health")
async def health_check():
    """فحص صحة النظام"""
    uptime = "0:00:00"
    if system_status.get("start_time"):
        uptime = str(datetime.now() - datetime.fromisoformat(system_status["start_time"]))
    
    return {
        "status": "healthy" if system_status["started"] else "starting",
        "uptime": uptime,
        "active_trades": len(trade_executor.active_trades),
        "total_scans": system_status["total_scans"],
        "total_trades": system_status["total_trades"],
        "bot_type": "futures",
        "leverage": TRADE_SETTINGS['leverage']
    }

@app.get("/api/find-best-pair")
async def find_best_pair():
    """البحث عن أفضل زوج تداول"""
    try:
        pair = await pair_finder.find_best_trading_pair()
        
        if not pair:
            return {"error": "لا توجد أزواج مناسبة في الوقت الحالي"}
        
        # إرسال إشعار
        await send_ntfy_notification(
            title="🔍 تم العثور على زوج",
            message=f"الزوج: {pair['pair']}\n"
                   f"الدرجة: {pair['pair_score']:.1f}\n"
                   f"الرافعة: {TRADE_SETTINGS['leverage']}x",
            priority="high" if pair['pair_score'] > 75 else "default",
            tags=["magnifying_glass", "chart_increasing"]
        )
        
        return pair
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/execute-trade")
async def execute_trade(request: TradeRequest, background_tasks: BackgroundTasks):
    """تنفيذ صفقة بناءً على أفضل إشارة"""
    try:
        # البحث عن أفضل زوج
        pair = await pair_finder.find_best_trading_pair()
        if not pair:
            return {"error": "لا توجد إشارات تداول مناسبة"}
        
        # تنفيذ الصفقة
        trade = await trade_executor.execute_pair_trade(pair)
        
        if not trade:
            return {"error": "فشل تنفيذ الصفقة"}
        
        # إرسال إشعار
        await send_ntfy_notification(
            title="💰 صفقة جديدة (Futures)",
            message=f"الزوج: {pair['pair']}\n"
                   f"المبلغ: ${request.amount_usdt:.2f}\n"
                   f"الرافعة: {TRADE_SETTINGS['leverage']}x\n"
                   f"التوصية: {pair['recommendation']}",
            priority="urgent",
            tags=["money_with_wings", "rocket"]
        )
        
        # تحديث حالة النظام
        system_status['last_trade'] = datetime.now().isoformat()
        system_status['total_trades'] = len(trade_executor.closed_trades) + len(trade_executor.active_trades)
        
        return {
            "success": True,
            "trade_id": trade.id,
            "pair": pair['pair'],
            "status": "EXECUTED",
            "futures_details": {
                "leverage": trade.leverage,
                "position_size_per_coin": f"${TRADE_SETTINGS['position_size_usdt']}",
                "long_quantity": trade.risk_params.quantity_strong,
                "short_quantity": trade.risk_params.quantity_weak,
                "stop_loss": f"{trade.risk_params.stop_loss:.1f}%",
                "take_profit": f"{trade.risk_params.take_profit:.1f}%"
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/active-trades")
async def get_active_trades():
    """الحصول على الصفقات النشطة"""
    trades = []
    
    for trade_id, trade in trade_executor.active_trades.items():
        trades.append({
            "id": trade.id,
            "pair": trade.pair_signal['pair'],
            "opened_at": trade.opened_at.isoformat(),
            "pnl_percent": trade.pnl_percent,
            "pnl_usdt": trade.pnl_usdt,
            "status": trade.status,
            "leverage": trade.leverage,
            "entry_prices": trade.pair_signal['entry_prices'],
            "stop_loss": trade.risk_params.stop_loss,
            "take_profit": trade.risk_params.take_profit,
            "funding_paid": trade.funding_paid
        })
    
    return {
        "total": len(trades),
        "trades": trades
    }

@app.get("/api/closed-trades")
async def get_closed_trades(limit: int = 20):
    """الحصول على الصفقات المغلقة"""
    trades = []
    
    # الحصول على آخر limit صفقة
    recent_trades = trade_executor.closed_trades[-limit:] if trade_executor.closed_trades else []
    
    for trade in recent_trades:
        trades.append({
            "id": trade.id,
            "pair": trade.pair_signal['pair'],
            "opened_at": trade.opened_at.isoformat(),
            "closed_at": trade.close_reason,
            "pnl_percent": trade.pnl_percent,
            "pnl_usdt": trade.pnl_usdt,
            "close_reason": trade.close_reason,
            "leverage": trade.leverage,
            "entry_prices": trade.pair_signal['entry_prices'],
            "close_prices": {
                "strong": trade.close_price_strong,
                "weak": trade.close_price_weak
            },
            "funding_paid": trade.funding_paid,
            "net_pnl": trade.pnl_usdt - trade.funding_paid
        })
    
    return {
        "total": len(trade_executor.closed_trades),
        "trades": trades
    }

@app.post("/api/close-all-trades")
async def close_all_trades():
    """إغلاق جميع الصفقات النشطة"""
    try:
        closed = await trade_executor.close_all_trades()
        
        await send_ntfy_notification(
            title="🔒 إغلاق جميع الصفقات",
            message=f"تم إغلاق {len(closed)} صفقة نشطة",
            priority="high",
            tags=["lock", "warning"]
        )
        
        return {
            "success": True,
            "closed_count": len(closed),
            "trades": [t.id for t in closed]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/trade-summary")
async def get_trade_summary():
    """الحصول على ملخص الصفقات"""
    summary = trade_executor.get_futures_trade_summary()
    
    return {
        **summary,
        "total_capital": TRADE_SETTINGS['total_capital_usdt'],
        "risk_per_trade": TRADE_SETTINGS['risk_per_trade'],
        "settings": TRADE_SETTINGS
    }

@app.get("/api/account-balance")
async def get_account_balance():
    """الحصول على رصيد الحساب"""
    try:
        balance = await trade_executor.get_account_balance()
        if balance:
            return balance
        else:
            return {"error": "فشل جلب رصيد الحساب"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/open-positions")
async def get_open_positions():
    """الحصول على المراكز المفتوحة"""
    try:
        positions = await trade_executor.get_open_positions()
        return {
            "total_positions": len(positions),
            "positions": positions
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/send-notification")
async def send_notification(request: NotificationRequest):
    """إرسال إشعار اختياري"""
    success = await send_ntfy_notification(
        title=request.title,
        message=request.message,
        priority=request.priority,
        tags=request.tags
    )
    
    return {"success": success}

@app.get("/api/system-status")
async def get_system_status():
    """الحصول على حالة النظام"""
    return {
        **system_status,
        "active_trades_count": len(trade_executor.active_trades),
        "closed_trades_count": len(trade_executor.closed_trades),
        "settings": TRADE_SETTINGS,
        "bot_info": {
            "type": "futures",
            "leverage": f"{TRADE_SETTINGS['leverage']}x",
            "position_size": f"${TRADE_SETTINGS['position_size_usdt']} per coin"
        }
    }

# تشغيل التطبيق
if __name__ == "__main__":
    import uvicorn
    
    # إنشاء المجلدات اللازمة
    os.makedirs("static", exist_ok=True)
    os.makedirs("data", exist_ok=True)
    
    # تشغيل الخادم
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta
import asyncio
import logging
import os

from core.pair_finder import SmartPairFinder
from core.trade_executor import TradeExecutor
from core.config import TRADE_SETTINGS, NTFY_CONFIG

# إعداد التطبيق
app = FastAPI(
    title="Smart Crypto Pair Trading Bot",
    description="بوت ذكي لتداول أزواج العملات الرقمية على Binance",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# إعداد CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# تهيئة المكونات
pair_finder = SmartPairFinder(use_testnet=True)
trade_executor = TradeExecutor(use_testnet=True)
monitoring_task = None

# نماذج البيانات
class TradeRequest(BaseModel):
    amount_usdt: float = TRADE_SETTINGS['total_capital_usdt']
    auto_execute: bool = True

class NotificationRequest(BaseModel):
    title: str
    message: str
    priority: str = "default"
    tags: list = []

# حالة النظام
system_status = {
    "started": False,
    "start_time": None,
    "total_scans": 0,
    "total_trades": 0,
    "last_scan": None,
    "last_trade": None,
    "errors": []
}

# وظائف المساعدة
async def send_ntfy_notification(title: str, message: str, 
                                priority: str = "default", tags: list = None):
    """إرسال إشعار إلى NTFY"""
    import requests
    
    url = f"{NTFY_CONFIG['server_url']}/{NTFY_CONFIG['topic']}"
    
    headers = {
        "Title": title.encode('utf-8'),
        "Priority": priority,
        "Tags": ",".join(tags) if tags else ""
    }
    
    try:
        # إضافة وقت سورية
        from datetime import datetime
        syria_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_message = f"{message}\n\n🕒 الوقت: {syria_time}"
        
        response = requests.post(url, data=full_message.encode('utf-8'), headers=headers)
        
        if response.status_code == 200:
            logging.info(f"Notification sent: {title}")
            return True
        else:
            logging.error(f"Failed to send notification: {response.status_code}")
            return False
            
    except Exception as e:
        logging.error(f"Error sending notification: {e}")
        return False

async def monitor_trades_background():
    """مراقبة الصفقات في الخلفية"""
    while True:
        try:
            # مراقبة الصفقات النشطة
            closed_trades = await trade_executor.monitor_active_trades()
            
            # إرسال إشعارات للصفقات المغلقة
            for trade in closed_trades:
                emoji = "✅" if trade.pnl_usdt > 0 else "❌"
                pnl_sign = "+" if trade.pnl_usdt > 0 else ""
                
                await send_ntfy_notification(
                    title=f"{emoji} صفقة مغلقة",
                    message=f"الزوج: {trade.pair_signal['pair']}\n"
                           f"السبب: {trade.close_reason}\n"
                           f"الربح: {pnl_sign}{trade.pnl_percent:.2f}% (${pnl_sign}{trade.pnl_usdt:.2f})",
                    priority="high" if trade.pnl_usdt > 0 else "default",
                    tags=["check_mark_button" if trade.pnl_usdt > 0 else "cross_mark", "moneybag"]
                )
            
            # تحديث حالة النظام
            system_status['total_trades'] = len(trade_executor.closed_trades)
            
        except Exception as e:
            logging.error(f"Error in trade monitoring: {e}")
            system_status['errors'].append(str(e))
        
        # الانتظار للدورة القادمة
        await asyncio.sleep(TRADE_SETTINGS['check_interval_minutes'] * 60)

async def auto_scan_background():
    """مسح تلقائي للأسواق في الخلفية"""
    while True:
        try:
            # البحث عن أفضل زوج
            best_pair = await pair_finder.find_best_trading_pair()
            
            if best_pair and best_pair['pair_score'] >= 80:  # إشارة قوية جداً
                # إرسال إشعار
                await send_ntfy_notification(
                    title="🎯 إشارة تلقائية قوية",
                    message=f"الزوج: {best_pair['pair']}\n"
                           f"الدرجة: {best_pair['pair_score']:.1f}\n"
                           f"التوصية: {best_pair['recommendation']}",
                    priority="high",
                    tags=["rocket", "chart_increasing"]
                )
                
                # تنفيذ تلقائي إذا كان ممكناً
                if len(trade_executor.active_trades) < TRADE_SETTINGS['max_open_trades']:
                    trade = await trade_executor.execute_pair_trade(best_pair)
                    if trade:
                        await send_ntfy_notification(
                            title="🚀 صفقة تلقائية مفتوحة",
                            message=f"الزوج: {best_pair['pair']}\n"
                                   f"تم فتح صفقة تلقائياً",
                            priority="urgent",
                            tags=["automobile", "rocket"]
                        )
            
            # تحديث حالة النظام
            system_status['last_scan'] = datetime.now().isoformat()
            system_status['total_scans'] += 1
            
        except Exception as e:
            logging.error(f"Error in auto scan: {e}")
            system_status['errors'].append(str(e))
        
        # الانتظار للدورة القادمة
        await asyncio.sleep(TRADE_SETTINGS['scan_interval_hours'] * 3600)

# نقاط النهاية
@app.on_event("startup")
async def startup_event():
    """بدء النظام عند التشغيل"""
    logging.info("🚀 Starting Smart Crypto Pair Trading Bot (FUTURES)...")
    logging.info(f"   Leverage: {TRADE_SETTINGS['leverage']}x")
    logging.info(f"   Position size: ${TRADE_SETTINGS['position_size_usdt']} per coin")
    
    system_status['started'] = True
    system_status['start_time'] = datetime.now().isoformat()
    
    # بدء مهام الخلفية
    global monitoring_task, auto_scan_task
    monitoring_task = asyncio.create_task(monitor_trades_background())
    auto_scan_task = asyncio.create_task(auto_scan_background())
    
    # إرسال إشعار بدء التشغيل
    await send_ntfy_notification(
        title="🚀 بدء تشغيل البوت",
        message="تم بدء تشغيل بوت التداول الزوجي بنجاح",
        tags=["white_check_mark", "rocket"]
    )
    
    logging.info("✅ Bot started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """إيقاف النظام عند الإغلاق"""
    if monitoring_task:
        monitoring_task.cancel()
    if auto_scan_task:
        auto_scan_task.cancel()
    
    await send_ntfy_notification(
        title="🛑 إيقاف البوت",
        message="تم إيقاف بوت التداول الزوجي",
        tags=["stop_sign", "warning"]
    )
    
    logging.info("🛑 Bot stopped")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """الصفحة الرئيسية (لوحة التحكم)"""
    try:
        with open("static/dashboard.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>لوحة التحكم غير متوفرة</h1>")

@app.get("/api/health")
async def health_check():
    """فحص صحة النظام"""
    return {
        "status": "healthy" if system_status["started"] else "starting",
        "uptime": str(datetime.now() - datetime.fromisoformat(system_status["start_time"])) 
        if system_status.get("start_time") else "0:00:00",
        "active_trades": len(trade_executor.active_trades),
        "total_scans": system_status["total_scans"],
        "total_trades": system_status["total_trades"]
    }

@app.get("/api/find-best-pair")
async def find_best_pair():
    """البحث عن أفضل زوج تداول"""
    try:
        pair = await pair_finder.find_best_trading_pair()
        
        if not pair:
            return {"error": "لا توجد أزواج مناسبة في الوقت الحالي"}
        
        # إرسال إشعار
        await send_ntfy_notification(
            title="🔍 تم العثور على زوج",
            message=f"الزوج: {pair['pair']}\n"
                   f"الدرجة: {pair['pair_score']:.1f}",
            priority="high" if pair['pair_score'] > 75 else "default",
            tags=["magnifying_glass", "chart_increasing"]
        )
        
        return pair
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/execute-trade")
async def execute_trade(request: TradeRequest, background_tasks: BackgroundTasks):
    """تنفيذ صفقة بناءً على أفضل إشارة"""
    try:
        # البحث عن أفضل زوج
        pair = await pair_finder.find_best_trading_pair()
        if not pair:
            return {"error": "لا توجد إشارات تداول مناسبة"}
        
        # تنفيذ الصفقة
        trade = await trade_executor.execute_pair_trade(pair)
        
        if not trade:
            return {"error": "فشل تنفيذ الصفقة"}
        
        # إرسال إشعار
        await send_ntfy_notification(
            title="💰 صفقة جديدة",
            message=f"الزوج: {pair['pair']}\n"
                   f"المبلغ: ${request.amount_usdt:.2f}\n"
                   f"التوصية: {pair['recommendation']}",
            priority="urgent",
            tags=["money_with_wings", "rocket"]
        )
        
        # تحديث حالة النظام
        system_status['last_trade'] = datetime.now().isoformat()
        system_status['total_trades'] = len(trade_executor.closed_trades) + len(trade_executor.active_trades)
        
        return {
            "success": True,
            "trade_id": trade.id,
            "pair": pair['pair'],
            "status": "EXECUTED",
            "details": {
                "long": trade.risk_params.position_size_strong,
                "short": trade.risk_params.position_size_weak,
                "stop_loss": trade.risk_params.stop_loss,
                "take_profit": trade.risk_params.take_profit
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/active-trades")
async def get_active_trades():
    """الحصول على الصفقات النشطة"""
    trades = []
    
    for trade_id, trade in trade_executor.active_trades.items():
        trades.append({
            "id": trade.id,
            "pair": trade.pair_signal['pair'],
            "opened_at": trade.opened_at.isoformat(),
            "pnl_percent": trade.pnl_percent,
            "pnl_usdt": trade.pnl_usdt,
            "status": trade.status,
            "entry_prices": trade.pair_signal['entry_prices'],
            "stop_loss": trade.risk_params.stop_loss,
            "take_profit": trade.risk_params.take_profit
        })
    
    return {
        "total": len(trades),
        "trades": trades
    }

@app.get("/api/closed-trades")
async def get_closed_trades(limit: int = 20):
    """الحصول على الصفقات المغلقة"""
    trades = []
    
    for trade in trade_executor.closed_trades[-limit:]:
        trades.append({
            "id": trade.id,
            "pair": trade.pair_signal['pair'],
            "opened_at": trade.opened_at.isoformat(),
            "closed_at": trade.close_reason,
            "pnl_percent": trade.pnl_percent,
            "pnl_usdt": trade.pnl_usdt,
            "close_reason": trade.close_reason,
            "entry_prices": trade.pair_signal['entry_prices'],
            "close_prices": {
                "strong": trade.close_price_strong,
                "weak": trade.close_price_weak
            }
        })
    
    return {
        "total": len(trade_executor.closed_trades),
        "trades": trades
    }

@app.post("/api/close-all-trades")
async def close_all_trades():
    """إغلاق جميع الصفقات النشطة"""
    try:
        closed = await trade_executor.close_all_trades()
        
        await send_ntfy_notification(
            title="🔒 إغلاق جميع الصفقات",
            message=f"تم إغلاق {len(closed)} صفقة نشطة",
            priority="high",
            tags=["lock", "warning"]
        )
        
        return {
            "success": True,
            "closed_count": len(closed),
            "trades": [t.id for t in closed]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/trade-summary")
async def get_trade_summary():
    """الحصول على ملخص الصفقات"""
    summary = trade_executor.get_trade_summary()
    
    return {
        **summary,
        "total_capital": TRADE_SETTINGS['total_capital_usdt'],
        "risk_per_trade": TRADE_SETTINGS['risk_per_trade'],
        "settings": TRADE_SETTINGS
    }

@app.post("/api/send-notification")
async def send_notification(request: NotificationRequest):
    """إرسال إشعار اختياري"""
    success = await send_ntfy_notification(
        title=request.title,
        message=request.message,
        priority=request.priority,
        tags=request.tags
    )
    
    return {"success": success}

@app.get("/api/system-status")
async def get_system_status():
    """الحصول على حالة النظام"""
    return {
        **system_status,
        "active_trades_count": len(trade_executor.active_trades),
        "closed_trades_count": len(trade_executor.closed_trades),
        "settings": TRADE_SETTINGS
    }

# تشغيل التطبيق
if __name__ == "__main__":
    import uvicorn
    
    # إنشاء المجلدات اللازمة
    os.makedirs("static", exist_ok=True)
    os.makedirs("data", exist_ok=True)
    
    # تشغيل الخادم
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
