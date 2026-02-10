"""
وحدة تنفيذ الصفقات على Binance Futures ومتابعتها
مع دعم الرافعة المالية وحجم صفقة ثابت
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
    """تمثيل صفقة مفتوحة على العقود الآجلة"""
    def __init__(self, trade_id: str, pair_signal: Dict, risk_params: TradeRiskParams):
        self.id = trade_id
        self.pair_signal = pair_signal
        self.risk_params = risk_params
        self.opened_at = datetime.now()
        self.status = 'OPEN'  # OPEN, CLOSED, CANCELLED
        self.close_reason = None
        self.close_price_strong = None
        self.close_price_weak = None
        self.pnl_percent = 0.0
        self.pnl_usdt = 0.0
        self.funding_paid = 0.0  # رسوم التمويل المدفوعة
        
        # معلومات التنفيذ
        self.long_order_id = None
        self.short_order_id = None
        self.entry_price_strong = pair_signal['entry_prices']['strong']
        self.entry_price_weak = pair_signal['entry_prices']['weak']
        
        # معلومات العقود الآجلة
        self.leverage = risk_params.leverage
        self.position_side_strong = 'LONG'
        self.position_side_weak = 'SHORT'
        
        # تتبع الزمن
        self.last_funding_time = self.opened_at
        self.max_duration_hours = 24  # الحد الأقصى للصفقة

class FuturesTradeExecutor:
    def __init__(self, use_testnet: bool = True):
        self.exchange = self.init_futures_exchange(use_testnet)
        self.risk_manager = RiskManager()
        self.active_trades: Dict[str, Trade] = {}
        self.closed_trades: List[Trade] = []
        self.use_real_money = not use_testnet
        self.total_funding_paid = 0.0
        
        # إعدادات العقود الآجلة
        self.leverage = TRADE_SETTINGS['leverage']
        self.position_size = TRADE_SETTINGS['position_size_usdt']
        self.margin_mode = TRADE_SETTINGS.get('margin_mode', 'cross')
        
        logger.info(f"✅ FuturesTradeExecutor initialized")
        logger.info(f"   Testnet: {use_testnet}")
        logger.info(f"   Real Money: {self.use_real_money}")
        logger.info(f"   Leverage: {self.leverage}x")
        logger.info(f"   Position Size: ${self.position_size} per coin")
        logger.info(f"   Margin Mode: {self.margin_mode}")
    
    def init_futures_exchange(self, use_testnet: bool):
        """تهيئة اتصال Binance Futures"""
        from core.config import BINANCE_CONFIG
        
        config = {
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
                'adjustForTimeDifference': True,
                'defaultMarginMode': self.margin_mode,  # 'cross' or 'isolated'
            }
        }
        
        # استخدام API keys الحقيقية إذا كانت متوفرة ونريد التداول الحقيقي
        if BINANCE_CONFIG.get('api_key') and not use_testnet:
            config['apiKey'] = BINANCE_CONFIG['api_key']
            config['secret'] = BINANCE_CONFIG['api_secret']
            config['urls'] = {
                'api': {
                    'public': 'https://fapi.binance.com/fapi/v1',
                    'private': 'https://fapi.binance.com/fapi/v1',
                }
            }
            logger.info("Using real Binance Futures account")
            
        elif use_testnet:
            config.update({
                'apiKey': 'YOUR_TESTNET_API_KEY',  # استبدل بمفاتيح Testnet
                'secret': 'YOUR_TESTNET_SECRET',
                'urls': {
                    'api': {
                        'public': 'https://testnet.binancefuture.com/fapi/v1',
                        'private': 'https://testnet.binancefuture.com/fapi/v1',
                    }
                }
            })
            logger.info("Using Binance Futures Testnet")
        else:
            # بدون مفاتيح (للقراءة فقط)
            logger.info("Using Binance Futures in read-only mode")
        
        return ccxt.binance(config)
    
    async def set_leverage_for_symbol(self, symbol: str, leverage: int = 50):
        """تعيين الرافعة المالية للرمز"""
        try:
            # إزالة :USDT إذا كانت موجودة
            clean_symbol = symbol.replace(':USDT', '')
            
            # تعيين الرافعة
            response = await asyncio.to_thread(
                self.exchange.set_leverage,
                leverage,
                clean_symbol
            )
            
            logger.info(f"✅ Leverage set to {leverage}x for {clean_symbol}")
            return True
            
        except ccxt.ExchangeError as e:
            # تجاهل الخطأ إذا كانت الرافعة محددة بالفعل
            if 'leverage not modified' in str(e).lower():
                logger.info(f"Leverage already set to {leverage}x for {symbol}")
                return True
            else:
                logger.warning(f"Could not set leverage for {symbol}: {e}")
                return False
        except Exception as e:
            logger.warning(f"Error setting leverage for {symbol}: {e}")
            return False
    
    async def set_margin_mode(self, symbol: str, margin_mode: str = 'cross'):
        """تعيين وضع الهامش (cross أو isolated)"""
        try:
            clean_symbol = symbol.replace(':USDT', '')
            
            response = await asyncio.to_thread(
                self.exchange.set_margin_mode,
                margin_mode,
                clean_symbol
            )
            
            logger.info(f"✅ Margin mode set to {margin_mode} for {clean_symbol}")
            return True
            
        except ccxt.ExchangeError as e:
            if 'margin mode not modified' in str(e).lower():
                logger.info(f"Margin mode already set to {margin_mode} for {symbol}")
                return True
            else:
                logger.warning(f"Could not set margin mode for {symbol}: {e}")
                return False
        except Exception as e:
            logger.warning(f"Error setting margin mode for {symbol}: {e}")
            return False
    
    async def calculate_futures_quantity(self, symbol: str, usdt_amount: float, 
                                        leverage: int = 50) -> float:
        """
        حساب الكمية المناسبة للعقد الآجل
        الكمية = (المبلغ بالدولار × الرافعة) ÷ السعر
        """
        try:
            # جلب السعر الحالي
            ticker = await asyncio.to_thread(self.exchange.fetch_ticker, symbol)
            current_price = ticker['last']
            
            if current_price <= 0:
                logger.error(f"Invalid price for {symbol}: {current_price}")
                return 0.0
            
            # حساب الكمية الأساسية
            quantity = (usdt_amount * leverage) / current_price
            
            # جلب معلومات الرمز لمعرفة الحد الأدنى للكمية
            markets = self.exchange.load_markets()
            market = markets.get(symbol, {})
            
            # التحقق من الحد الأدنى للكمية
            limits = market.get('limits', {})
            amount_min = limits.get('amount', {}).get('min', 0.001)
            
            if quantity < amount_min:
                logger.warning(f"Quantity {quantity} below minimum {amount_min} for {symbol}")
                quantity = amount_min
            
            # التقريب حسب precision
            precision = market.get('precision', {}).get('amount', 0.001)
            quantity = round(quantity / precision) * precision
            
            logger.info(f"Calculated quantity for {symbol}: {quantity:.6f} (${usdt_amount} × {leverage}x @ ${current_price:.2f})")
            
            return quantity
            
        except Exception as e:
            logger.error(f"Error calculating futures quantity for {symbol}: {e}")
            return 0.0
    
    async def execute_pair_trade(self, pair_signal: Dict) -> Optional[Trade]:
        """
        تنفيذ صفقة زوجية كاملة على العقود الآجلة:
        1. تعيين الرافعة ووضع الهامش
        2. فتح LONG على العملة القوية
        3. فتح SHORT على العملة الضعيفة
        """
        
        logger.info(f"🚀 Starting FUTURES pair trade execution for: {pair_signal['pair']}")
        
        # 1. الحصول على الأسعار الحالية
        strong_symbol = pair_signal['strong_coin'].symbol.replace(':USDT', '')
        weak_symbol = pair_signal['weak_coin'].symbol.replace(':USDT', '')
        
        strong_price = pair_signal['entry_prices']['strong']
        weak_price = pair_signal['entry_prices']['weak']
        
        # 2. حساب معالم المخاطرة مع الرافعة
        risk_params = self.risk_manager.calculate_trade_parameters(
            pair_signal, strong_price, weak_price
        )
        
        # 3. فحص جدوى الصفقة
        is_viable, reason = self.risk_manager.check_trade_viability(
            len(self.active_trades),
            pair_signal['pair_score'],
            risk_params
        )
        
        if not is_viable:
            logger.warning(f"❌ Trade not viable: {reason}")
            return None
        
        # 4. إنشاء كائن الصفقة
        trade_id = f"futures_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        trade = Trade(trade_id, pair_signal, risk_params)
        
        try:
            # 5. تعيين الرافعة ووضع الهامش
            leverage_set = await self.set_leverage_for_symbol(strong_symbol, self.leverage)
            leverage_set &= await self.set_leverage_for_symbol(weak_symbol, self.leverage)
            
            if not leverage_set:
                logger.warning("Could not set leverage, but continuing...")
            
            # 6. حساب الكميات مع الرافعة
            quantity_strong = await self.calculate_futures_quantity(
                strong_symbol, self.position_size, self.leverage
            )
            
            quantity_weak = await self.calculate_futures_quantity(
                weak_symbol, self.position_size, self.leverage
            )
            
            if quantity_strong <= 0 or quantity_weak <= 0:
                logger.error("Invalid quantities calculated")
                return None
            
            # تحديث risk_params بالكميات المحسوبة
            risk_params.quantity_strong = quantity_strong
            risk_params.quantity_weak = quantity_weak
            
            # 7. تنفيذ أمر LONG على العملة القوية
            long_result = await self.place_futures_order(
                symbol=strong_symbol,
                side='buy',
                quantity=quantity_strong,
                position_side='LONG',
                leverage=self.leverage
            )
            
            if not long_result or long_result.get('status') != 'filled':
                logger.error("Failed to execute LONG futures order")
                return None
            
            trade.long_order_id = long_result.get('order_id')
            trade.entry_price_strong = long_result.get('price', strong_price)
            
            # 8. تنفيذ أمر SHORT على العملة الضعيفة
            short_result = await self.place_futures_order(
                symbol=weak_symbol,
                side='sell',
                quantity=quantity_weak,
                position_side='SHORT',
                leverage=self.leverage
            )
            
            if not short_result or short_result.get('status') != 'filled':
                # إغلاق المركز الطويل إذا فشلت القصيرة
                await self.close_position(strong_symbol, quantity_strong, 'sell')
                logger.error("Failed to execute SHORT futures order")
                return None
            
            trade.short_order_id = short_result.get('order_id')
            trade.entry_price_weak = short_result.get('price', weak_price)
            
            # 9. حفظ الصفقة النشطة
            self.active_trades[trade_id] = trade
            
            logger.info(f"✅ Futures trade {trade_id} executed successfully")
            logger.info(f"   Pair: {pair_signal['pair']}")
            logger.info(f"   Leverage: {self.leverage}x")
            logger.info(f"   Position size: ${self.position_size} per coin")
            logger.info(f"   Long: {quantity_strong:.6f} {strong_symbol} @ ${trade.entry_price_strong:.4f}")
            logger.info(f"   Short: {quantity_weak:.6f} {weak_symbol} @ ${trade.entry_price_weak:.4f}")
            logger.info(f"   Stop Loss: {risk_params.stop_loss:.1f}%")
            logger.info(f"   Take Profit: {risk_params.take_profit:.1f}%")
            logger.info(f"   Max Loss: ${risk_params.max_loss_usdt:.2f}")
            
            return trade
            
        except Exception as e:
            logger.error(f"❌ Futures trade execution failed: {e}")
            
            # محاولة تنظيف أي مراكز مفتوحة في حالة الخطأ
            try:
                if 'long_result' in locals() and long_result:
                    await self.close_position(strong_symbol, quantity_strong, 'sell')
                if 'short_result' in locals() and short_result:
                    await self.close_position(weak_symbol, quantity_weak, 'buy')
            except Exception as cleanup_error:
                logger.error(f"Cleanup also failed: {cleanup_error}")
            
            return None
    
    async def place_futures_order(self, symbol: str, side: str, quantity: float,
                                 position_side: str = 'BOTH', leverage: int = 50) -> Optional[Dict]:
        """تنفيذ أمر شراء/بيع على العقود الآجلة"""
        
        try:
            if self.use_real_money:
                # تنفيذ حقيقي على Binance Futures
                params = {
                    'positionSide': position_side,
                    'leverage': leverage,
                }
                
                # استخدام أمر السوق للسرعة
                order = await asyncio.to_thread(
                    self.exchange.create_order,
                    symbol=symbol,
                    type='market',
                    side=side,
                    amount=quantity,
                    params=params
                )
                
                # جلب تفاصيل التنفيذ
                if order.get('status') == 'closed' or order.get('filled') > 0:
                    avg_price = order.get('average') or order.get('price')
                    filled_qty = order.get('filled') or quantity
                    
                    logger.info(f"📊 Real futures order executed: {side} {filled_qty:.6f} {symbol} @ ${avg_price:.4f}")
                    
                    return {
                        'order_id': order['id'],
                        'symbol': symbol,
                        'side': side,
                        'quantity': filled_qty,
                        'price': avg_price,
                        'status': 'filled',
                        'leverage': leverage,
                        'position_side': position_side
                    }
                else:
                    logger.warning(f"Order not filled: {order}")
                    return None
            else:
                # محاكاة التنفيذ (للتجربة)
                ticker = await asyncio.to_thread(self.exchange.fetch_ticker, symbol)
                price = ticker['last']
                
                logger.info(f"📊 SIMULATED futures order: {side} {quantity:.6f} {symbol} @ ${price:.4f} with {leverage}x")
                
                return {
                    'order_id': f"SIM_{side}_{datetime.now().strftime('%H%M%S')}",
                    'symbol': symbol,
                    'side': side,
                    'quantity': quantity,
                    'price': price,
                    'status': 'filled',
                    'leverage': leverage,
                    'position_side': position_side
                }
                
        except Exception as e:
            logger.error(f"Futures order placement failed for {symbol}: {e}")
            return None
    
    async def close_position(self, symbol: str, quantity: float, side: str) -> bool:
        """إغلاق مركز في العقود الآجلة"""
        try:
            if self.use_real_money:
                # الأمر المعاكس للإغلاق
                close_side = 'sell' if side == 'buy' else 'buy'
                
                order = await asyncio.to_thread(
                    self.exchange.create_order,
                    symbol=symbol,
                    type='market',
                    side=close_side,
                    amount=quantity,
                    params={'reduceOnly': True}  # ⭐ مهم: فقط للإغلاق
                )
                
                logger.info(f"🔒 Position closed: {close_side} {quantity:.6f} {symbol}")
                return True
            else:
                logger.info(f"🔒 SIMULATED position close: {side} {quantity:.6f} {symbol}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to close position for {symbol}: {e}")
            return False
    
    async def check_funding_fees(self, trade: Trade) -> float:
        """التحقق من رسوم التمويل وخصمها من الربح"""
        try:
            # رسوم التمويل تحدث كل 8 ساعات في Binance
            time_since_last_funding = datetime.now() - trade.last_funding_time
            
            if time_since_last_funding.total_seconds() >= 28800:  # 8 ساعات
                # تقدير رسوم التمويل (عادة ±0.01% إلى ±0.06%)
                funding_rate = 0.0003  # 0.03% تقديري
                
                # حساب رسوم التمويل
                strong_funding = trade.risk_params.position_size_strong * funding_rate
                weak_funding = trade.risk_params.position_size_weak * funding_rate
                total_funding = strong_funding + weak_funding
                
                trade.funding_paid += total_funding
                trade.last_funding_time = datetime.now()
                
                logger.info(f"💸 Funding fee applied to trade {trade.id}: ${total_funding:.4f}")
                return total_funding
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error checking funding fees: {e}")
            return 0.0
    
    async def monitor_active_trades(self):
        """مراقبة الصفقات النشطة والتحقق من شروط الإغلاق"""
        
        if not self.active_trades:
            return []
        
        closed_trades = []
        
        for trade_id, trade in list(self.active_trades.items()):
            if trade.status != 'OPEN':
                continue
            
            try:
                # 1. التحقق من رسوم التمويل
                funding_fee = await self.check_funding_fees(trade)
                if funding_fee > 0:
                    self.total_funding_paid += funding_fee
                
                # 2. الحصول على الأسعار الحالية
                current_prices = await self.get_current_prices(trade)
                if not current_prices:
                    continue
                
                # 3. حساب الربح/الخسارة مع الرافعة
                pnl = self.calculate_futures_pnl(trade, current_prices)
                trade.pnl_percent = pnl['pair_pnl_percent']
                trade.pnl_usdt = pnl['total_usdt']
                
                # 4. خصم رسوم التمويل من الربح
                if funding_fee > 0:
                    trade.pnl_usdt -= funding_fee
                
                # 5. التحقق من شروط الإغلاق
                should_close, close_reason = self.check_futures_close_conditions(trade, pnl)
                
                if should_close:
                    # 6. إغلاق الصفقة
                    closed_trade = await self.close_futures_trade(trade, close_reason, current_prices)
                    if closed_trade:
                        closed_trades.append(closed_trade)
                
            except Exception as e:
                logger.error(f"Error monitoring trade {trade_id}: {e}")
                # في حالة الخطأ، نغلق الصفقة كإجراء وقائي
                try:
                    current_prices = await self.get_current_prices(trade)
                    if current_prices:
                        emergency_close = await self.close_futures_trade(
                            trade, "إغلاق طارئ بسبب خطأ", current_prices
                        )
                        if emergency_close:
                            closed_trades.append(emergency_close)
                except Exception as close_error:
                    logger.error(f"Emergency close also failed: {close_error}")
        
        return closed_trades
    
    async def get_current_prices(self, trade: Trade) -> Optional[Dict]:
        """الحصول على الأسعار الحالية للعملتين"""
        try:
            strong_symbol = trade.pair_signal['strong_coin'].symbol.replace(':USDT', '')
            weak_symbol = trade.pair_signal['weak_coin'].symbol.replace(':USDT', '')
            
            strong_ticker = await asyncio.to_thread(self.exchange.fetch_ticker, strong_symbol)
            weak_ticker = await asyncio.to_thread(self.exchange.fetch_ticker, weak_symbol)
            
            return {
                'strong': strong_ticker['last'],
                'weak': weak_ticker['last']
            }
        except Exception as e:
            logger.error(f"Failed to get current prices: {e}")
            return None
    
    def calculate_futures_pnl(self, trade: Trade, current_prices: Dict) -> Dict:
        """حساب الربح/الخسارة للصفقة مع الرافعة"""
        
        # حساب التغير بالنسبة المئوية
        long_pnl_percent = ((current_prices['strong'] - trade.entry_price_strong) / 
                           trade.entry_price_strong) * 100
        short_pnl_percent = ((trade.entry_price_weak - current_prices['weak']) / 
                            trade.entry_price_weak) * 100
        
        # الربح الإجمالي للزوج (المتوسط)
        pair_pnl_percent = (long_pnl_percent + short_pnl_percent) / 2
        
        # ⭐⭐ **حساب الربح بالدولار مع الرافعة**
        # الصيغة: (التغير % ÷ 100) × حجم المركز × الرافعة
        long_usdt = (long_pnl_percent / 100) * trade.risk_params.position_size_strong * trade.leverage
        short_usdt = (short_pnl_percent / 100) * trade.risk_params.position_size_weak * trade.leverage
        total_usdt = long_usdt + short_usdt
        
        return {
            'long_pnl_percent': long_pnl_percent,
            'short_pnl_percent': short_pnl_percent,
            'pair_pnl_percent': pair_pnl_percent,
            'long_usdt': long_usdt,
            'short_usdt': short_usdt,
            'total_usdt': total_usdt,
            'leverage': trade.leverage
        }
    
    def check_futures_close_conditions(self, trade: Trade, pnl: Dict) -> Tuple[bool, str]:
        """التحقق من شروط إغلاق الصفقة في العقود الآجلة"""
        
        # 1. تحقيق هدف الربح
        if pnl['pair_pnl_percent'] >= trade.risk_params.take_profit:
            return True, f"🎯 وصل للربح المستهدف: {pnl['pair_pnl_percent']:.2f}% (${pnl['total_usdt']:.2f})"
        
        # 2. تجاوز وقف الخسارة
        if pnl['pair_pnl_percent'] <= -trade.risk_params.stop_loss:
            return True, f"🛑 وصل لوقف الخسارة: {pnl['pair_pnl_percent']:.2f}% (${pnl['total_usdt']:.2f})"
        
        # 3. انتهاء وقت الصفقة (24 ساعة كحد أقصى)
        trade_age = datetime.now() - trade.opened_at
        if trade_age.total_seconds() > trade.max_duration_hours * 3600:
            return True, f"⏰ انتهى وقت الصفقة ({trade.max_duration_hours} ساعة) - الربح: {pnl['pair_pnl_percent']:.2f}%"
        
        # 4. خطر التصفية (Liquidation Risk)
        # في الرافعة 50x، التصفية تحدث عند خسارة ~98%
        # نحن نستخدم وقف خسارة صارم، لكن نتحقق أيضاً
        if pnl['pair_pnl_percent'] <= -80:  # إذا خسرنا أكثر من 80%
            return True, f"⚠️ خطر التصفية مرتفع: {pnl['pair_pnl_percent']:.2f}%"
        
        # 5. انعكاس الإشارة (إذا تحولت العلاقة)
        if abs(pnl['pair_pnl_percent']) > 10:
            # إذا أصبحت كلتا الصفقتين مربحة أو خاسرة (يعني انعكاس العلاقة)
            if (pnl['long_pnl_percent'] > 5 and pnl['short_pnl_percent'] > 5) or \
               (pnl['long_pnl_percent'] < -5 and pnl['short_pnl_percent'] < -5):
                return True, f"🔄 انعكاس في العلاقة: {pnl['pair_pnl_percent']:.2f}%"
        
        return False, ""
    
    async def close_futures_trade(self, trade: Trade, close_reason: str, 
                                 current_prices: Dict) -> Optional[Trade]:
        """إغلاق صفقة العقود الآجلة بالكامل"""
        
        logger.info(f"🔒 Closing futures trade {trade.id}: {close_reason}")
        
        try:
            # 1. إغلاق المركز الطويل (بيع)
            strong_symbol = trade.pair_signal['strong_coin'].symbol.replace(':USDT', '')
            long_closed = await self.close_position(
                strong_symbol, 
                trade.risk_params.quantity_strong, 
                'buy'  # نبيع لإغلاق المركز الطويل
            )
            
            # 2. إغلاق المركز القصير (شراء)
            weak_symbol = trade.pair_signal['weak_coin'].symbol.replace(':USDT', '')
            short_closed = await self.close_position(
                weak_symbol, 
                trade.risk_params.quantity_weak, 
                'sell'  # نشتري لإغلاق المركز القصير
            )
            
            if not long_closed or not short_closed:
                logger.error(f"Failed to fully close trade {trade.id}")
                # حاول مرة أخرى
                if not long_closed:
                    await self.close_position(strong_symbol, trade.risk_params.quantity_strong, 'buy')
                if not short_closed:
                    await self.close_position(weak_symbol, trade.risk_params.quantity_weak, 'sell')
            
            # 3. تحديث حالة الصفقة
            trade.status = 'CLOSED'
            trade.close_reason = close_reason
            trade.close_price_strong = current_prices['strong']
            trade.close_price_weak = current_prices['weak']
            
            # 4. نقل من النشطة إلى المغلقة
            self.active_trades.pop(trade.id, None)
            self.closed_trades.append(trade)
            
            # 5. تسجيل النتائج
            total_funding = trade.funding_paid
            net_pnl = trade.pnl_usdt - total_funding
            
            logger.info(f"✅ Futures trade {trade.id} closed.")
            logger.info(f"   PnL: {trade.pnl_percent:.2f}% (${trade.pnl_usdt:.2f})")
            logger.info(f"   Funding fees: ${total_funding:.4f}")
            logger.info(f"   Net PnL: ${net_pnl:.2f}")
            logger.info(f"   Reason: {close_reason}")
            
            return trade
            
        except Exception as e:
            logger.error(f"Failed to close futures trade {trade.id}: {e}")
            
            # وضع الصفقة في حالة خطأ
            trade.status = 'ERROR'
            trade.close_reason = f"Error during close: {str(e)}"
            
            return None
    
    async def close_all_trades(self, reason: str = "إغلاق يدوي"):
        """إغلاق جميع الصفقات النشطة"""
        closed = []
        
        logger.info(f"🛑 Closing all active futures trades: {reason}")
        
        for trade_id, trade in list(self.active_trades.items()):
            current_prices = await self.get_current_prices(trade)
            if current_prices:
                closed_trade = await self.close_futures_trade(
                    trade, 
                    reason, 
                    current_prices
                )
                if closed_trade:
                    closed.append(closed_trade)
            else:
                # إذا لم نستطع الحصول على الأسعار، نغلق بأمر السوق بدون معرفة السعر
                try:
                    strong_symbol = trade.pair_signal['strong_coin'].symbol.replace(':USDT', '')
                    weak_symbol = trade.pair_signal['weak_coin'].symbol.replace(':USDT', '')
                    
                    await self.close_position(strong_symbol, trade.risk_params.quantity_strong, 'buy')
                    await self.close_position(weak_symbol, trade.risk_params.quantity_weak, 'sell')
                    
                    trade.status = 'CLOSED'
                    trade.close_reason = f"{reason} (emergency)"
                    self.active_trades.pop(trade_id, None)
                    self.closed_trades.append(trade)
                    closed.append(trade)
                    
                except Exception as e:
                    logger.error(f"Emergency close failed for {trade_id}: {e}")
        
        logger.info(f"✅ Closed {len(closed)} futures trades")
        return closed
    
    def get_futures_trade_summary(self) -> Dict:
        """الحصول على ملخص صفقات العقود الآجلة"""
        
        # حساب إجمالي الصفقات المغلقة
        if not self.closed_trades:
            return {
                'total_trades': 0,
                'active_trades': len(self.active_trades),
                'total_pnl_usdt': 0.0,
                'total_funding_paid': self.total_funding_paid,
                'net_pnl_usdt': -self.total_funding_paid,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'avg_leverage': self.leverage,
                'total_position_size': len(self.active_trades) * self.position_size * 2
            }
        
        # حساب الإحصائيات
        total_pnl_usdt = sum(t.pnl_usdt for t in self.closed_trades)
        net_pnl_usdt = total_pnl_usdt - self.total_funding_paid
        
        winning_trades = [t for t in self.closed_trades if t.pnl_usdt > 0]
        losing_trades = [t for t in self.closed_trades if t.pnl_usdt <= 0]
        
        avg_pnl_per_trade = total_pnl_usdt / len(self.closed_trades) if self.closed_trades else 0
        
        # حساب متوسط مدة الصفقات
        if self.closed_trades:
            avg_duration = sum(
                (t.closed_at - t.opened_at).total_seconds() 
                for t in self.closed_trades 
                if hasattr(t, 'closed_at')
            ) / len(self.closed_trades)
            avg_duration_hours = avg_duration / 3600
        else:
            avg_duration_hours = 0
        
        return {
            'total_trades': len(self.closed_trades),
            'active_trades': len(self.active_trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': len(winning_trades) / len(self.closed_trades) * 100 if self.closed_trades else 0,
            'total_pnl_usdt': total_pnl_usdt,
            'total_funding_paid': self.total_funding_paid,
            'net_pnl_usdt': net_pnl_usdt,
            'avg_pnl_per_trade': avg_pnl_per_trade,
            'avg_trade_duration_hours': avg_duration_hours,
            'avg_leverage': self.leverage,
            'position_size_per_coin': self.position_size,
            'total_position_size': (len(self.active_trades) * self.position_size * 2) + 
                                  (len(self.closed_trades) * self.position_size * 2),
            'settings': {
                'leverage': self.leverage,
                'margin_mode': self.margin_mode,
                'position_size': self.position_size
            }
        }
    
    async def get_account_balance(self) -> Optional[Dict]:
        """الحصول على رصيد حساب العقود الآجلة"""
        try:
            if self.use_real_money:
                balance = await asyncio.to_thread(self.exchange.fetch_balance)
                
                # رصيد USDT في حساب العقود الآجلة
                usdt_balance = balance.get('USDT', {})
                
                return {
                    'total': usdt_balance.get('total', 0),
                    'free': usdt_balance.get('free', 0),
                    'used': usdt_balance.get('used', 0),
                    'timestamp': datetime.now().isoformat()
                }
            else:
                # للمحاكاة، نعيد رصيد وهمي
                return {
                    'total': 1000.0,
                    'free': 800.0,
                    'used': 200.0,
                    'timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Failed to get account balance: {e}")
            return None
    
    async def get_open_positions(self) -> List[Dict]:
        """الحصول على المراكز المفتوحة الحالية"""
        try:
            if self.use_real_money:
                positions = await asyncio.to_thread(self.exchange.fetch_positions)
                
                open_positions = []
                for pos in positions:
                    if float(pos.get('contracts', 0)) > 0:
                        open_positions.append({
                            'symbol': pos['symbol'],
                            'side': pos['side'],
                            'size': float(pos['contracts']),
                            'entry_price': float(pos['entryPrice']),
                            'mark_price': float(pos['markPrice']),
                            'pnl': float(pos['unrealizedPnl']),
                            'leverage': int(pos.get('leverage', self.leverage))
                        })
                
                return open_positions
            else:
                # للمحاكاة، نعيد مراكز من الصفقات النشطة
                positions = []
                for trade in self.active_trades.values():
                    positions.extend([
                        {
                            'symbol': trade.pair_signal['strong_coin'].symbol.replace(':USDT', ''),
                            'side': 'long',
                            'size': trade.risk_params.quantity_strong,
                            'entry_price': trade.entry_price_strong,
                            'leverage': trade.leverage
                        },
                        {
                            'symbol': trade.pair_signal['weak_coin'].symbol.replace(':USDT', ''),
                            'side': 'short',
                            'size': trade.risk_params.quantity_weak,
                            'entry_price': trade.entry_price_weak,
                            'leverage': trade.leverage
                        }
                    ])
                
                return positions
                
        except Exception as e:
            logger.error(f"Failed to get open positions: {e}")
            return []

# Singleton instance
trade_executor = FuturesTradeExecutor(use_testnet=True)
