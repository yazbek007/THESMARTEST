"""
وحدة اكتشاف أفضل أزواج التداول بناءً على القوة النسبية مقابل BTC
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import asyncio
import logging
import time
import traceback
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class CoinAnalysis:
    """تحليل شامل للعملة"""
    symbol: str
    price: float
    price_btc: float
    vs_btc_1h: float
    vs_btc_4h: float
    vs_btc_1d: float
    rsi: float
    atr_percent: float
    volume_usd: float
    score: float = 0.0
    signals: List[str] = None
    support_level: float = None
    resistance_level: float = None
    
    def __post_init__(self):
        if self.signals is None:
            self.signals = []

class SmartPairFinder:
    def __init__(self, use_testnet: bool = False):
        self.exchange = self.init_exchange(use_testnet)
        self.btc_symbol = "BTC/USDT"
        self.cache = {}
        self.cache_timeout = 300  # 5 دقائق
        
    def init_exchange(self, use_testnet: bool):
        """تهيئة اتصال Binance"""
        config = {
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        }
        
        if use_testnet:
            config.update({
                'apiKey': 'YOUR_TESTNET_API_KEY',
                'secret': 'YOUR_TESTNET_SECRET',
                'urls': {
                    'api': {
                        'public': 'https://testnet.binancefuture.com/fapi/v1',
                        'private': 'https://testnet.binancefuture.com/fapi/v1'
                    }
                }
            })
        else:
            # يمكنك إضافة API keys هنا إذا كنت بحاجة إليها
            pass
            
        return ccxt.binance(config)
    
    def clear_cache(self):
        """مسح الكاش القديم"""
        current_time = time.time()
        self.cache = {
            k: v for k, v in self.cache.items() 
            if current_time - v['timestamp'] < self.cache_timeout
        }
    
    async def find_best_trading_pair(self, coins_to_monitor: List[str]) -> Optional[Dict[str, Any]]:
        """
        البحث عن أفضل زوج تداول مع مراعاة:
        1. القوة النسبية مقابل BTC
        2. مستويات الدعم والمقاومة
        3. السيولة
        4. الإشارات الفنية
        """
        logger.info("🔍 بدء البحث عن أفضل زوج تداول...")
        
        try:
            # جلب وتحليل بيانات BTC أولاً
            btc_data = await self.get_btc_analysis()
            
            # التحقق من صحة بيانات BTC
            if btc_data is None:
                logger.error("فشل جلب بيانات BTC - القيمة None")
                return None
            
            # التحقق إذا كان DataFrame
            if not isinstance(btc_data, pd.DataFrame):
                logger.error(f"بيانات BTC ليست DataFrame، نوعها: {type(btc_data)}")
                return None
            
            # التحقق من عدم فراغ DataFrame
            if btc_data.empty:
                logger.error("بيانات BTC فارغة")
                return None
            
            # التحقق من وجود بيانات كافية
            if len(btc_data) < 24:
                logger.error(f"بيانات BTC غير كافية، عدد الصفوف: {len(btc_data)}")
                return None
            
            logger.info(f"✅ تم جلب بيانات BTC بنجاح، عدد النقاط: {len(btc_data)}")
            
            # تحليل جميع العملات
            coins_analysis = []
            for symbol in coins_to_monitor:
                try:
                    coin_analysis = await self.analyze_coin(symbol, btc_data)
                    if coin_analysis is not None and coin_analysis.score > 0:
                        coins_analysis.append(coin_analysis)
                        logger.debug(f"تم تحليل {symbol}: درجة {coin_analysis.score:.1f}")
                except Exception as e:
                    logger.error(f"خطأ في تحليل {symbol}: {e}")
                    continue
            
            if len(coins_analysis) < 2:
                logger.warning(f"لا توجد عملات كافية للتحليل، عدد العملات: {len(coins_analysis)}")
                return None
            
            logger.info(f"✅ تم تحليل {len(coins_analysis)} عملة بنجاح")
            
            # فرز العملات حسب القوة
            coins_analysis.sort(key=lambda x: x.score, reverse=True)
            
            # طباعة أفضل 5 عملات
            logger.info("أفضل 5 عملات:")
            for i, coin in enumerate(coins_analysis[:5], 1):
                logger.info(f"{i}. {coin.symbol}: {coin.score:.1f} - {coin.vs_btc_4h:.2f}%")
            
            # اختيار أفضل زوج
            best_pair = self.select_optimal_pair(coins_analysis)
            
            if best_pair:
                logger.info(f"✅ تم العثور على زوج: {best_pair['pair']} بدرجة {best_pair['pair_score']:.1f}")
                logger.info(f"   العملة القوية: {best_pair['strong_coin'].symbol} ({best_pair['strong_score']:.1f})")
                logger.info(f"   العملة الضعيفة: {best_pair['weak_coin'].symbol} ({best_pair['weak_score']:.1f})")
                logger.info(f"   فرق الأداء: {best_pair['performance_diff_4h']:.2f}%")
            
            return best_pair
            
        except Exception as e:
            logger.error(f"❌ خطأ في البحث عن الزوج: {e}")
            logger.error(traceback.format_exc())
            return None
    
    async def get_btc_analysis(self) -> Optional[pd.DataFrame]:
        """جلب وتحليل بيانات BTC"""
        try:
            # استخدام الكاش إذا كان متاحًا
            cache_key = "btc_analysis"
            current_time = time.time()
            
            if cache_key in self.cache:
                cache_data = self.cache[cache_key]
                if current_time - cache_data['timestamp'] < 60:  # 60 ثانية
                    return cache_data['data']
            
            # جلب البيانات من API
            ohlcv = await asyncio.to_thread(
                self.exchange.fetch_ohlcv,
                self.btc_symbol,
                timeframe='1h',
                limit=100
            )
            
            if not ohlcv or len(ohlcv) == 0:
                logger.error("لا توجد بيانات لـ BTC")
                return None
            
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # حفظ في الكاش
            self.cache[cache_key] = {
                'data': df,
                'timestamp': current_time
            }
            
            logger.info(f"✅ تم جلب {len(df)} نقطة بيانات لـ BTC")
            return df
            
        except Exception as e:
            logger.error(f"❌ خطأ في جلب بيانات BTC: {e}")
            return None
    
    async def analyze_coin(self, symbol: str, btc_data: pd.DataFrame) -> Optional[CoinAnalysis]:
        """تحليل شامل لعملة معينة"""
        try:
            # تنظيف الرمز
            clean_symbol = symbol.replace(':USDT', '').replace('/USDT', '')
            if not clean_symbol.endswith('USDT'):
                clean_symbol = f"{clean_symbol}/USDT"
            
            logger.debug(f"تحليل العملة: {clean_symbol}")
            
            # جلب بيانات OHLCV
            ohlcv = await asyncio.to_thread(
                self.exchange.fetch_ohlcv,
                clean_symbol,
                timeframe='1h',
                limit=100
            )
            
            if not ohlcv or len(ohlcv) < 50:
                logger.warning(f"بيانات غير كافية لـ {clean_symbol}: {len(ohlcv) if ohlcv else 0}")
                return None
            
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # جلب بيانات التيكر
            ticker = await asyncio.to_thread(self.exchange.fetch_ticker, clean_symbol)
            
            # جلب سعر BTC للعملة
            symbol_btc = clean_symbol.replace('USDT', 'BTC')
            try:
                ticker_btc = await asyncio.to_thread(self.exchange.fetch_ticker, symbol_btc)
                price_btc = ticker_btc['last']
            except Exception as e:
                logger.debug(f"لا يمكن جلب سعر BTC لـ {clean_symbol}: {e}")
                btc_price = btc_data['close'].iloc[-1] if len(btc_data) > 0 else ticker['last'] / 50000
                price_btc = ticker['last'] / btc_price if btc_price > 0 else 0
            
            # حساب الأداء مقابل BTC
            coin_returns = self.calculate_returns(df)
            btc_returns = self.calculate_returns(btc_data)
            
            vs_btc_1h = coin_returns.get('1h', 0) - btc_returns.get('1h', 0)
            vs_btc_4h = coin_returns.get('4h', 0) - btc_returns.get('4h', 0)
            vs_btc_1d = coin_returns.get('1d', 0) - btc_returns.get('1d', 0)
            
            # حساب المؤشرات الفنية
            rsi = self.calculate_rsi(df['close'])
            atr = self.calculate_atr(df)
            current_price = ticker['last']
            atr_percent = (atr / current_price * 100) if atr and current_price > 0 else 0
            
            # حساب مستويات الدعم والمقاومة
            support, resistance = self.calculate_support_resistance(df)
            
            # حساب النتيجة النهائية
            score = self.calculate_coin_score({
                'vs_btc_1h': vs_btc_1h,
                'vs_btc_4h': vs_btc_4h,
                'vs_btc_1d': vs_btc_1d,
                'rsi': rsi,
                'atr_percent': atr_percent,
                'volume': ticker.get('quoteVolume', 0),
                'price': current_price
            })
            
            # اكتشاف الإشارات
            signals = self.detect_signals(df, vs_btc_4h, rsi, support, resistance, current_price)
            
            return CoinAnalysis(
                symbol=symbol,
                price=current_price,
                price_btc=price_btc,
                vs_btc_1h=vs_btc_1h,
                vs_btc_4h=vs_btc_4h,
                vs_btc_1d=vs_btc_1d,
                rsi=rsi,
                atr_percent=atr_percent,
                volume_usd=ticker.get('quoteVolume', 0),
                score=score,
                signals=signals,
                support_level=support,
                resistance_level=resistance
            )
            
        except Exception as e:
            logger.error(f"❌ خطأ في تحليل {symbol}: {e}")
            logger.debug(traceback.format_exc())
            return None
    
    def calculate_returns(self, df: pd.DataFrame) -> Dict[str, float]:
        """حساب العوائد على أطر زمنية مختلفة"""
        if df is None or df.empty or len(df) < 24:
            return {'1h': 0.0, '4h': 0.0, '1d': 0.0}
        
        try:
            close = df['close'].astype(float)
            
            returns = {}
            
            # 1 ساعة
            if len(close) >= 1:
                returns['1h'] = 0.0
            else:
                returns['1h'] = 0.0
            
            # 4 ساعات
            if len(close) >= 4:
                returns['4h'] = ((close.iloc[-1] / close.iloc[-4]) - 1) * 100
            else:
                returns['4h'] = 0.0
            
            # 1 يوم (24 ساعة)
            if len(close) >= 24:
                returns['1d'] = ((close.iloc[-1] / close.iloc[-24]) - 1) * 100
            else:
                returns['1d'] = 0.0
            
            return returns
            
        except Exception as e:
            logger.error(f"خطأ في حساب العوائد: {e}")
            return {'1h': 0.0, '4h': 0.0, '1d': 0.0}
    
    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """حساب مؤشر RSI"""
        if prices is None or len(prices) < period + 1:
            return 50.0
        
        try:
            delta = prices.diff().dropna()
            
            if len(delta) < period:
                return 50.0
            
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            if loss.iloc[-1] == 0:
                return 100.0 if gain.iloc[-1] > 0 else 50.0
            
            rs = gain.iloc[-1] / loss.iloc[-1]
            rsi = 100 - (100 / (1 + rs))
            
            return float(rsi)
            
        except Exception as e:
            logger.error(f"خطأ في حساب RSI: {e}")
            return 50.0
    
    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """حساب Average True Range"""
        if df is None or len(df) < period:
            return 0.0
        
        try:
            high = df['high'].astype(float)
            low = df['low'].astype(float)
            close = df['close'].astype(float)
            
            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())
            
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=period).mean()
            
            return float(atr.iloc[-1])
            
        except Exception as e:
            logger.error(f"خطأ في حساب ATR: {e}")
            return 0.0
    
    def calculate_support_resistance(self, df: pd.DataFrame) -> Tuple[float, float]:
        """حساب مستويات الدعم والمقاومة"""
        if df is None or len(df) < 20:
            return 0.0, 0.0
        
        try:
            recent = df.tail(20)
            support = float(recent['low'].min())
            resistance = float(recent['high'].max())
            
            return support, resistance
            
        except Exception as e:
            logger.error(f"خطأ في حساب الدعم/المقاومة: {e}")
            return 0.0, 0.0
    
    def calculate_coin_score(self, metrics: Dict[str, float]) -> float:
        """حساب النتيجة النهائية للعملة (0-100)"""
        try:
            score = 0.0
            
            # الأداء مقابل BTC (40%)
            perf_score = (metrics['vs_btc_4h'] * 0.6 + metrics['vs_btc_1d'] * 0.4)
            perf_score = max(min(perf_score, 10), -10)
            score += ((perf_score + 10) / 20) * 40
            
            # RSI (25%)
            rsi = metrics['rsi']
            if 40 <= rsi <= 60:
                rsi_score = 25
            elif 30 <= rsi < 40 or 60 < rsi <= 70:
                rsi_score = 15
            else:
                rsi_score = 5
            score += rsi_score
            
            # السيولة (20%)
            volume = metrics['volume']
            if volume > 10000000:
                volume_score = 20
            elif volume > 1000000:
                volume_score = 15
            elif volume > 100000:
                volume_score = 10
            else:
                volume_score = 5
            score += volume_score
            
            # التقلب (15%)
            atr = metrics['atr_percent']
            if 1.0 <= atr <= 3.0:
                volatility_score = 15
            elif 0.5 <= atr < 1.0 or 3.0 < atr <= 5.0:
                volatility_score = 10
            else:
                volatility_score = 5
            score += volatility_score
            
            return min(max(score, 0), 100)
            
        except Exception as e:
            logger.error(f"خطأ في حساب النتيجة: {e}")
            return 0.0
    
    def detect_signals(self, df: pd.DataFrame, vs_btc: float, rsi: float, 
                      support: float, resistance: float, current_price: float) -> List[str]:
        """اكتشاف الإشارات الفنية"""
        signals = []
        
        try:
            # إشارات القوة النسبية
            if vs_btc > 5:
                signals.append("STRONG_VS_BTC")
            elif vs_btc > 2:
                signals.append("POSITIVE_VS_BTC")
            elif vs_btc < -5:
                signals.append("WEAK_VS_BTC")
            elif vs_btc < -2:
                signals.append("NEGATIVE_VS_BTC")
            
            # إشارات RSI
            if rsi < 30:
                signals.append("RSI_OVERSOLD")
            elif rsi > 70:
                signals.append("RSI_OVERBOUGHT")
            
            # إشارات الدعم والمقاومة
            if support > 0 and current_price <= support * 1.02:
                signals.append("NEAR_SUPPORT")
            elif resistance > 0 and current_price >= resistance * 0.98:
                signals.append("NEAR_RESISTANCE")
            
            # إشارات الحجم
            if df is not None and not df.empty and len(df) > 10:
                avg_volume = df['volume'].tail(10).mean()
                current_volume = df['volume'].iloc[-1] if len(df) > 0 else 0
                if avg_volume > 0 and current_volume > avg_volume * 1.5:
                    signals.append("HIGH_VOLUME")
                    
        except Exception as e:
            logger.error(f"خطأ في اكتشاف الإشارات: {e}")
        
        return signals
    
    def select_optimal_pair(self, coins: List[CoinAnalysis]) -> Optional[Dict[str, Any]]:
        """اختيار أفضل زوج للتداول"""
        if len(coins) < 2:
            logger.warning("لا توجد عملات كافية لاختيار زوج")
            return None
        
        best_pair = None
        best_score = -999
        
        # اختيار أفضل 3 عملات قوية وأسوأ 3 عملات ضعيفة
        strong_candidates = coins[:min(3, len(coins))]
        weak_candidates = coins[-min(3, len(coins)):]
        
        logger.info(f"المرشحون الأقوياء: {[c.symbol for c in strong_candidates]}")
        logger.info(f"المرشحون الضعفاء: {[c.symbol for c in weak_candidates]}")
        
        for strong in strong_candidates:
            for weak in weak_candidates:
                if strong.symbol == weak.symbol:
                    continue
                
                # حساب درجة الزوج
                pair_score = self.calculate_pair_score(strong, weak)
                
                # شروط القبول
                try:
                    min_score_diff = abs(strong.score - weak.score) >= 20
                    min_perf_diff = abs(strong.vs_btc_4h - weak.vs_btc_4h) >= 3
                    good_liquidity = min(strong.volume_usd, weak.volume_usd) > 1000000
                    
                    # استخدام القيمة الافتراضية
                    min_pair_score = 50
                    
                    conditions = {
                        'min_score_diff': min_score_diff,
                        'min_perf_diff': min_perf_diff,
                        'good_liquidity': good_liquidity,
                        'min_pair_score': pair_score >= min_pair_score
                    }
                    
                    # تقييم جميع الشروط
                    all_conditions_met = all(conditions.values())
                    
                    if all_conditions_met and pair_score > best_score:
                        best_score = pair_score
                        best_pair = {
                            'pair': f"{strong.symbol.replace('/USDT', '').replace(':USDT', '')}/{weak.symbol.replace('/USDT', '').replace(':USDT', '')}",
                            'strong_coin': strong,
                            'weak_coin': weak,
                            'strong_score': strong.score,
                            'weak_score': weak.score,
                            'score_difference': strong.score - weak.score,
                            'performance_diff_4h': strong.vs_btc_4h - weak.vs_btc_4h,
                            'pair_score': pair_score,
                            'recommendation': self.generate_recommendation(strong, weak),
                            'entry_prices': {
                                'strong': strong.price,
                                'weak': weak.price
                            },
                            'support_resistance': {
                                'strong_support': strong.support_level,
                                'strong_resistance': strong.resistance_level,
                                'weak_support': weak.support_level,
                                'weak_resistance': weak.resistance_level
                            },
                            'signals': {
                                'strong': strong.signals,
                                'weak': weak.signals
                            },
                            'timestamp': datetime.now().isoformat(),
                            'conditions_met': conditions
                        }
                        
                except Exception as e:
                    logger.error(f"خطأ في تقييم الزوج {strong.symbol}/{weak.symbol}: {e}")
                    continue
        
        if best_pair:
            logger.info(f"أفضل زوج: {best_pair['pair']} بدرجة {best_score:.1f}")
        else:
            logger.warning("لم يتم العثور على زوج مناسب")
            
        return best_pair
    
    def calculate_pair_score(self, strong: CoinAnalysis, weak: CoinAnalysis) -> float:
        """حساب درجة الزوج (0-100)"""
        try:
            score = 0.0
            
            # اختلاف القوة (40%)
            strength_diff = abs(strong.score - weak.score)
            score += min(strength_diff, 40)
            
            # اختلاف الأداء مقابل BTC (30%)
            perf_diff = abs(strong.vs_btc_4h - weak.vs_btc_4h)
            score += min(perf_diff * 3, 30)
            
            # جودة الإشارات (20%)
            signal_score = 0
            strong_signals = set(strong.signals)
            weak_signals = set(weak.signals)
            
            if "STRONG_VS_BTC" in strong_signals and "WEAK_VS_BTC" in weak_signals:
                signal_score = 20
            elif "POSITIVE_VS_BTC" in strong_signals and "NEGATIVE_VS_BTC" in weak_signals:
                signal_score = 15
            
            # إضافة نقاط للإشارات الأخرى
            if "RSI_OVERSOLD" in weak_signals and "RSI_OVERBOUGHT" not in strong_signals:
                signal_score += 5
            if "RSI_OVERBOUGHT" in strong_signals and "RSI_OVERSOLD" not in weak_signals:
                signal_score += 5
                
            score += min(signal_score, 20)
            
            # السيولة المشتركة (10%)
            avg_volume = (strong.volume_usd + weak.volume_usd) / 2
            if avg_volume > 5000000:
                score += 10
            elif avg_volume > 1000000:
                score += 7
            elif avg_volume > 500000:
                score += 4
            
            return min(max(score, 0), 100)
            
        except Exception as e:
            logger.error(f"خطأ في حساب درجة الزوج: {e}")
            return 0.0
    
    def generate_recommendation(self, strong: CoinAnalysis, weak: CoinAnalysis) -> str:
        """توليد توصية التداول"""
        strong_symbol = strong.symbol.replace('/USDT', '').replace(':USDT', '')
        weak_symbol = weak.symbol.replace('/USDT', '').replace(':USDT', '')
        
        return f"LONG_{strong_symbol}_SHORT_{weak_symbol}"


# اختبار الوحدة
if __name__ == "__main__":
    async def test():
        # قائمة العملات للمراقبة
        coins_to_monitor = [
            "BTC/USDT",
            "ETH/USDT", 
            "BNB/USDT",
            "ADA/USDT",
            "DOGE/USDT",
            "XRP/USDT",
            "DOT/USDT",
            "UNI/USDT",
            "LINK/USDT",
            "MATIC/USDT"
        ]
        
        finder = SmartPairFinder(use_testnet=False)
        result = await finder.find_best_trading_pair(coins_to_monitor)
        
        if result:
            print("\n" + "="*50)
            print(f"✅ أفضل زوج: {result['pair']}")
            print(f"📊 درجة الزوج: {result['pair_score']:.1f}")
            print(f"📈 توصية: {result['recommendation']}")
            print(f"💰 الأسعار: {result['entry_prices']}")
            print(f"📈 فرق الدرجات: {result['score_difference']:.1f}")
            print(f"📊 فرق الأداء (4h): {result['performance_diff_4h']:.2f}%")
            print(f"📈 إشارات القوية: {result['signals']['strong']}")
            print(f"📉 إشارات الضعيفة: {result['signals']['weak']}")
            print("="*50)
        else:
            print("❌ لم يتم العثور على زوج مناسب")
    
    asyncio.run(test())
