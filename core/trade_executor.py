"""
وحدة تنفيذ الصفقات على Binance ومتابعتها
"""

import ccxt
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from decimal import Decimal

from core.config import BINANCE_CONFIG, TRADE_SETTINGS
from core.risk_manager import RiskManager, TradeRiskParams

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Trade:
    """تمثيل صفقة مفتوحة"""
    def __init__(self, trade_id: str, pair_signal: Dict, risk_params: TradeRiskParams):
        self.id = trade_id
        self.pair_signal = pair_signal
        self.risk_params = risk_params
        self.opened_at = datetime.now()
        self.status = 'OPEN'  |  OPEN, CLOSED, CANCELLED
        self.close_reason = None
        self.close_price_strong = None
        self.close_price_weak = None
        self.pnl_percent = 0.0
        self.pnl_usdt = 0.0
        
        # معلومات التنفيذ
        self.long_order_id = None
        self.short_order_id = None
        self.entry_price_strong = pair_signal['entry_prices']['strong']
        self.entry_price_weak = pair_signal['entry_prices']['weak']

class TradeExecutor:
    def __init__(self, use_testnet: bool = True):
        self.exchange = self.init_exchange(use_testnet)
        self.risk_manager = RiskManager()
        self.active_trades: Dict[str, Trade] = {}
        self.closed_trades: List[Trade] = []
        self.use_real_money = not use_testnet
        
        logger.info(f"✅ TradeExecutor initialized (Testnet: {use_testnet}, Real Money: {self.use_real_money})")
    
    def init_exchange(self, use_testnet: bool):
        """تهيئة اتصال Binance"""
        config = {
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        }
        
        # استخدام API keys الحقيقية إذا كانت متوفرة ونريد التداول الحقيقي
        if BINANCE_CONFIG.get('api_key') and not use_testnet:
            config['apiKey'] = BINANCE_CONFIG['api_key']
            config['secret'] = BINANCE_CONFIG['api_secret']
            logger.info("Using real Binance account")
        elif use_testnet:
            config.update({
                'apiKey': 'YOUR_TESTNET_API_KEY',  |  استبدل بمفاتيح Testnet
                'secret': 'YOUR_TESTNET_SECRET',
                'urls': {'api': 'https://testnet.binance.vision'}
            })
            logger.info("Using Binance Testnet")
        
        return ccxt.binance(config)
    
    async def execute_pair_trade(self, pair_signal: Dict) -> Optional[Trade]:
        """
        تنفيذ صفقة زوجية كاملة:
        1. فتح LONG على العملة القوية
        2. فتح SHORT على العملة الضعيفة
        """
        
        logger.info(f"🚀 Starting trade execution for pair: {pair_signal['pair']}")
        
        # 1. حساب معالم المخاطرة
        strong_price = pair_signal['entry_prices']['strong']
        weak_price = pair_signal['entry_prices']['weak']
        
        risk_params = self.risk_manager.calculate_trade_parameters(
            pair_signal, strong_price, weak_price
        )
        
        # 2. فحص جدوى الصفقة
        is_viable, reason = self.risk_manager.check_trade_viability(
            len(self.active_trades),
            pair_signal['pair_score'],
            risk_params
        )
        
        if not is_viable:
            logger.warning(f"❌ Trade not viable: {reason}")
            return None
        
        # 3. إنشاء كائن الصفقة
        trade_id = f"pair_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        trade = Trade(trade_id, pair_signal, risk_params)
        
        try:
            # 4. تنفيذ أمر LONG على العملة القوية
            strong_symbol = pair_signal['strong_coin'].symbol
            long_result = await self.place_order(
                symbol=strong_symbol,
                side='buy',
                quantity=risk_params.quantity_strong,
                trade_type='LONG'
            )
            
            if not long_result:
                logger.error("Failed to execute LONG order")
                return None
            
            trade.long_order_id = long_result.get('order_id', 'SIM_LONG')
            
            # 5. تنفيذ أمر SHORT على العملة الضعيفة
            weak_symbol = pair_signal['weak_coin'].symbol
            short_result = await self.place_order(
                symbol=weak_symbol,
                side='sell',
                quantity=risk_params.quantity_weak,
                trade_type='SHORT'
            )
            
            if not short_result:
                # إغلاق الصفقة الطويلة إذا فشلت القصيرة
                await self.cancel_order(strong_symbol, trade.long_order_id)
                logger.error("Failed to execute SHORT order")
                return None
            
            trade.short_order_id = short_result.get('order_id', 'SIM_SHORT')
            
            # 6. حفظ الصفقة النشطة
            self.active_trades[trade_id] = trade
            
            logger.info(f"✅ Trade {trade_id} executed successfully")
            logger.info(f"   Pair: {pair_signal['pair']}")
            logger.info(f"   Long: {risk_params.quantity_strong:.4f} {strong_symbol} @ ${strong_price:.2f}")
            logger.info(f"   Short: {risk_params.quantity_weak:.4f} {weak_symbol} @ ${weak_price:.2f}")
            logger.info(f"   Stop Loss: {risk_params.stop_loss:.1f}%")
            logger.info(f"   Take Profit: {risk_params.take_profit:.1f}%")
            
            return trade
            
        except Exception as e:
            logger.error(f"❌ Trade execution failed: {e}")
            return None
    
    async def place_order(self, symbol: str, side: str, quantity: float, 
                         trade_type: str) -> Optional[Dict]:
        """تنفيذ أمر شراء/بيع"""
        
        try:
            if self.use_real_money:
                # تنفيذ حقيقي على Binance
                order = await asyncio.to_thread(
                    self.exchange.create_order,
                    symbol=symbol,
                    type='market',
                    side=side,
                    amount=quantity
                )
                
                logger.info(f"📊 Real order placed: {side} {quantity:.4f} {symbol}")
                return {
                    'order_id': order['id'],
                    'symbol': symbol,
                    'side': side,
                    'quantity': quantity,
                    'price': order['price'] if 'price' in order else 0,
                    'status': order['status']
                }
            else:
                # محاكاة التنفيذ (للتجربة)
                ticker = await asyncio.to_thread(self.exchange.fetch_ticker, symbol)
                price = ticker['last']
                
                logger.info(f"📊 SIMULATED order: {side} {quantity:.4f} {symbol} @ ${price:.2f}")
                
                return {
                    'order_id': f"SIM_{side}_{datetime.now().strftime('%H%M%S')}",
                    'symbol': symbol,
                    'side': side,
                    'quantity': quantity,
                    'price': price,
                    'status': 'filled'
                }
                
        except Exception as e:
            logger.error(f"Order placement failed for {symbol}: {e}")
            return None
    
    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """إلغاء أمر"""
        try:
            if self.use_real_money and not order_id.startswith('SIM_'):
                await asyncio.to_thread(self.exchange.cancel_order, order_id, symbol)
            
            logger.info(f"Order {order_id} cancelled")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    async def monitor_active_trades(self):
        """مراقبة الصفقات النشطة والتحقق من شروط الإغلاق"""
        
        if not self.active_trades:
            return []
        
        closed_trades = []
        
        for trade_id, trade in list(self.active_trades.items()):
            if trade.status != 'OPEN':
                continue
            
            # 1. الحصول على الأسعار الحالية
            current_prices = await self.get_current_prices(trade)
            if not current_prices:
                continue
            
            # 2. حساب الربح/الخسارة
            pnl = self.calculate_pnl(trade, current_prices)
            trade.pnl_percent = pnl['pair_pnl_percent']
            trade.pnl_usdt = pnl['total_usdt']
            
            # 3. التحقق من شروط الإغلاق
            should_close, close_reason = self.check_close_conditions(trade, pnl)
            
            if should_close:
                # 4. إغلاق الصفقة
                closed_trade = await self.close_trade(trade, close_reason, current_prices)
                if closed_trade:
                    closed_trades.append(closed_trade)
        
        return closed_trades
    
    async def get_current_prices(self, trade: Trade) -> Optional[Dict]:
        """الحصول على الأسعار الحالية للعملتين"""
        try:
            strong_symbol = trade.pair_signal['strong_coin'].symbol
            weak_symbol = trade.pair_signal['weak_coin'].symbol
            
            strong_ticker = await asyncio.to_thread(self.exchange.fetch_ticker, strong_symbol)
            weak_ticker = await asyncio.to_thread(self.exchange.fetch_ticker, weak_symbol)
            
            return {
                'strong': strong_ticker['last'],
                'weak': weak_ticker['last']
            }
        except Exception as e:
            logger.error(f"Failed to get current prices: {e}")
            return None
    
    def calculate_pnl(self, trade: Trade, current_prices: Dict) -> Dict:
        """حساب الربح/الخسارة للصفقة"""
        
        long_pnl_percent = ((current_prices['strong'] - trade.entry_price_strong) / 
                           trade.entry_price_strong) * 100
        short_pnl_percent = ((trade.entry_price_weak - current_prices['weak']) / 
                            trade.entry_price_weak) * 100
        
        # الربح الإجمالي للزوج (المتوسط)
        pair_pnl_percent = (long_pnl_percent + short_pnl_percent) / 2
        
        # الربح بالدولار
        long_usdt = trade.risk_params.position_size_strong * (long_pnl_percent / 100)
        short_usdt = trade.risk_params.position_size_weak * (short_pnl_percent / 100)
        total_usdt = long_usdt + short_usdt
        
        return {
            'long_pnl_percent': long_pnl_percent,
            'short_pnl_percent': short_pnl_percent,
            'pair_pnl_percent': pair_pnl_percent,
            'long_usdt': long_usdt,
            'short_usdt': short_usdt,
            'total_usdt': total_usdt
        }
    
    def check_close_conditions(self, trade: Trade, pnl: Dict) -> Tuple[bool, str]:
        """التحقق من شروط إغلاق الصفقة"""
        
        # 1. تحقيق هدف الربح
        if pnl['pair_pnl_percent'] >= trade.risk_params.take_profit:
            return True, f"🎯 وصل للربح المستهدف: {pnl['pair_pnl_percent']:.2f}%"
        
        # 2. تجاوز وقف الخسارة
        if pnl['pair_pnl_percent'] <= -trade.risk_params.stop_loss:
            return True, f"🛑 وصل لوقف الخسارة: {pnl['pair_pnl_percent']:.2f}%"
        
        # 3. انتهاء وقت الصفقة (24 ساعة)
        trade_age = datetime.now() - trade.opened_at
        if trade_age.total_seconds() > 86400:  |  24 ساعة
            return True, f"⏰ انتهى وقت الصفقة (24 ساعة) - الربح: {pnl['pair_pnl_percent']:.2f}%"
        
        # 4. انعكاس الإشارة (يمكن إضافة منطق أكثر تعقيداً هنا)
        if abs(pnl['pair_pnl_percent']) > 10 and (
            (pnl['long_pnl_percent'] < -5 and pnl['short_pnl_percent'] < -5) or
            (pnl['long_pnl_percent'] > 5 and pnl['short_pnl_percent'] > 5)
        ):
            return True, f"🔄 انعكاس في العلاقة - الربح: {pnl['pair_pnl_percent']:.2f}%"
        
        return False, ""
    
    async def close_trade(self, trade: Trade, close_reason: str, 
                         current_prices: Dict) -> Optional[Trade]:
        """إغلاق الصفقة بالكامل"""
        
        logger.info(f"🔒 Closing trade {trade.id}: {close_reason}")
        
        try:
            # 1. إغلاق المركز الطويل (بيع)
            if trade.long_order_id:
                strong_symbol = trade.pair_signal['strong_coin'].symbol
                await self.place_order(
                    symbol=strong_symbol,
                    side='sell',
                    quantity=trade.risk_params.quantity_strong,
                    trade_type='CLOSE_LONG'
                )
            
            # 2. إغلاق المركز القصير (شراء)
            if trade.short_order_id:
                weak_symbol = trade.pair_signal['weak_coin'].symbol
                await self.place_order(
                    symbol=weak_symbol,
                    side='buy',
                    quantity=trade.risk_params.quantity_weak,
                    trade_type='CLOSE_SHORT'
                )
            
            # 3. تحديث حالة الصفقة
            trade.status = 'CLOSED'
            trade.close_reason = close_reason
            trade.close_price_strong = current_prices['strong']
            trade.close_price_weak = current_prices['weak']
            
            # 4. نقل من النشطة إلى المغلقة
            self.active_trades.pop(trade.id, None)
            self.closed_trades.append(trade)
            
            logger.info(f"✅ Trade {trade.id} closed. PnL: {trade.pnl_percent:.2f}% (${trade.pnl_usdt:.2f})")
            
            return trade
            
        except Exception as e:
            logger.error(f"Failed to close trade {trade.id}: {e}")
            return None
    
    async def close_all_trades(self):
        """إغلاق جميع الصفقات النشطة"""
        closed = []
        
        for trade_id, trade in list(self.active_trades.items()):
            current_prices = await self.get_current_prices(trade)
            if current_prices:
                closed_trade = await self.close_trade(
                    trade, 
                    "إغلاق يدوي لجميع الصفقات", 
                    current_prices
                )
                if closed_trade:
                    closed.append(closed_trade)
        
        return closed
    
    def get_trade_summary(self) -> Dict:
        """الحصول على ملخص الصفقات"""
        total_pnl_usdt = sum(t.pnl_usdt for t in self.closed_trades)
        total_pnl_percent = (total_pnl_usdt / TRADE_SETTINGS['total_capital_usdt']) * 100
        
        winning_trades = [t for t in self.closed_trades if t.pnl_usdt > 0]
        losing_trades = [t for t in self.closed_trades if t.pnl_usdt <= 0]
        
        return {
            'total_trades': len(self.closed_trades),
            'active_trades': len(self.active_trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': len(winning_trades) / len(self.closed_trades) * 100 if self.closed_trades else 0,
            'total_pnl_usdt': total_pnl_usdt,
            'total_pnl_percent': total_pnl_percent,
            'avg_pnl_per_trade': total_pnl_usdt / len(self.closed_trades) if self.closed_trades else 0
        }
