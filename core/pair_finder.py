"""
وحدة اكتشاف أفضل أزواج التداول بناءً على القوة النسبية مقابل BTC
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import asyncio
import logging
from dataclasses import dataclass, field

from core.config import COINS_TO_MONITOR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _is_valid_df(df: Optional[pd.DataFrame]) -> bool:
    """التحقق مما إذا كان DataFrame صالحاً وغير فارغ"""
    return df is not None and isinstance(df, pd.DataFrame) and not df.empty


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
    signals: List[str] = field(default_factory=list)
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None


class SmartPairFinder:
    def __init__(self, use_testnet: bool = False):
        self.exchange = self.init_exchange(use_testnet)
        self.btc_symbol = "BTC/USDT"
        self.cache = {}

    def init_exchange(self, use_testnet: bool):
        """تهيئة اتصال Binance"""
        from core.config import BINANCE_CONFIG

        # إذا كانت المفاتيح حقيقية، نتجاهل use_testnet ونجبر Production
        if BINANCE_CONFIG and BINANCE_CONFIG.get('api_key') and BINANCE_CONFIG.get('api_secret'):
            if BINANCE_CONFIG['api_key'] != 'testnet_api_key':
                logger.info("🚀 اكتشاف مفاتيح Production - استخدام Binance الحقيقي")
                use_testnet = False

        config = {
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        }

        # إضافة مفاتيح API إن وجدت
        if BINANCE_CONFIG and BINANCE_CONFIG.get('api_key'):
            config['apiKey'] = BINANCE_CONFIG['api_key']
            config['secret'] = BINANCE_CONFIG['api_secret']

        if use_testnet:
            logger.info("🔧 استخدام Testnet للتجربة")
            config.update({
                'apiKey': 'testnet_api_key',
                'secret': 'testnet_secret',
                'urls': {
                    'api': {
                        'public': 'https://testnet.binancefuture.com/fapi/v1',
                        'private': 'https://testnet.binancefuture.com/fapi/v1'
                    }
                }
            })
        else:
            logger.info("🚀 استخدام Binance Production الحقيقي")
            if not config.get('apiKey') or config['apiKey'] == 'testnet_api_key':
                raise Exception("❌ مفاتيح API غير صالحة للإنتاج – أضف المفاتيح الصحيحة في متغيرات البيئة")
            config['urls'] = {
                'api': {
                    'public': 'https://fapi.binance.com/fapi/v1',
                    'private': 'https://fapi.binance.com/fapi/v1'
                }
            }

        try:
            exchange = ccxt.binance(config)
            # اختبار الاتصال
            exchange.fetch_time()
            logger.info("✅ تم الاتصال بـ Binance بنجاح")
            return exchange
        except Exception as e:
            logger.error(f"❌ فشل الاتصال بـ Binance: {e}")
            raise

    async def find_best_trading_pair(self) -> Optional[Dict]:
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
            if btc_data is None:  # ✅ التصحيح الجوهري: لا تستخدم if not btc_data
                logger.error("❌ فشل جلب بيانات BTC")
                return None

            # تحليل جميع العملات
            coins_analysis = []
            for symbol in COINS_TO_MONITOR:
                coin_analysis = await self.analyze_coin(symbol, btc_data)
                if coin_analysis and coin_analysis.score > 0:
                    coins_analysis.append(coin_analysis)

            if len(coins_analysis) < 2:
                logger.warning("⚠️ لا توجد عملات كافية للتحليل")
                return None

            # فرز العملات حسب القوة
            coins_analysis.sort(key=lambda x: x.score, reverse=True)

            # اختيار أفضل زوج
            best_pair = self.select_optimal_pair(coins_analysis)

            if best_pair:
                logger.info(f"✅ تم العثور على زوج: {best_pair['pair']} بدرجة {best_pair['pair_score']:.1f}")

            return best_pair

        except Exception as e:
            logger.error(f"❌ خطأ في البحث عن الزوج: {e}")
            return None

    async def get_btc_analysis(self) -> Optional[pd.DataFrame]:
        """جلب وتحليل بيانات BTC"""
        try:
            ohlcv = await asyncio.to_thread(
                self.exchange.fetch_ohlcv,
                self.btc_symbol,
                timeframe='1h',
                limit=100
            )

            if not ohlcv or len(ohlcv) < 20:
                logger.error("❌ لم يتم استلام بيانات كافية لـ BTC")
                return None

            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            if df.empty:
                logger.error("❌ DataFrame فارغ")
                return None

            logger.info(f"✅ تم جلب {len(df)} شمعة لـ BTC")
            return df

        except Exception as e:
            logger.error(f"❌ خطأ في جلب بيانات BTC: {e}")
            return None

    async def analyze_coin(self, symbol: str, btc_data: Optional[pd.DataFrame]) -> Optional[CoinAnalysis]:
        """تحليل شامل لعملة معينة"""
        try:
            # تنظيف الرمز
            clean_symbol = symbol.replace(':USDT', '').replace('/USDT', '')

            # جلب بيانات OHLCV
            ohlcv = await asyncio.to_thread(
                self.exchange.fetch_ohlcv,
                clean_symbol,
                timeframe='1h',
                limit=100,
                params={'price': 'mark'}
            )

            if not ohlcv or len(ohlcv) < 50:
                logger.warning(f"⚠️ بيانات غير كافية لـ {symbol}")
                return None

            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            # جلب بيانات التيكر
            ticker = await asyncio.to_thread(self.exchange.fetch_ticker, clean_symbol)

            # حساب سعر العملة مقابل BTC
            if _is_valid_df(btc_data):
                try:
                    symbol_btc = f"{clean_symbol}/BTC"
                    ticker_btc = await asyncio.to_thread(self.exchange.fetch_ticker, symbol_btc)
                    price_btc = ticker_btc['last']
                except Exception:
                    price_btc = ticker['last'] / btc_data['close'].iloc[-1]
            else:
                price_btc = 0.0
                logger.warning(f"⚠️ بيانات BTC غير متوفرة، تعيين price_btc=0 لـ {symbol}")

            # حساب الأداء مقابل BTC
            coin_returns = self.calculate_returns(df)
            btc_returns = self.calculate_returns(btc_data) if _is_valid_df(btc_data) else {'1h': 0, '4h': 0, '1d': 0}

            vs_btc_1h = coin_returns.get('1h', 0) - btc_returns.get('1h', 0)
            vs_btc_4h = coin_returns.get('4h', 0) - btc_returns.get('4h', 0)
            vs_btc_1d = coin_returns.get('1d', 0) - btc_returns.get('1d', 0)

            # المؤشرات الفنية
            rsi = self.calculate_rsi(df['close'])
            atr = self.calculate_atr(df)
            atr_percent = (atr / ticker['last'] * 100) if atr and ticker['last'] > 0 else 0

            # مستويات الدعم والمقاومة
            support, resistance = self.calculate_support_resistance(df)

            # النتيجة النهائية
            score = self.calculate_coin_score({
                'vs_btc_1h': vs_btc_1h,
                'vs_btc_4h': vs_btc_4h,
                'vs_btc_1d': vs_btc_1d,
                'rsi': rsi,
                'atr_percent': atr_percent,
                'volume': ticker.get('quoteVolume', 0),
                'price': ticker['last']
            })

            # الإشارات
            signals = self.detect_signals(df, vs_btc_4h, rsi, support, resistance, ticker['last'])

            return CoinAnalysis(
                symbol=symbol,
                price=ticker['last'],
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
            return None

    def calculate_returns(self, df: Optional[pd.DataFrame]) -> Dict[str, float]:
        """حساب العوائد على أطر زمنية مختلفة"""
        # التحقق من صحة المدخل
        if not _is_valid_df(df) or len(df) < 24:
            return {'1h': 0, '4h': 0, '1d': 0}

        close = df['close']
        returns = {}

        # 1 ساعة (قارن مع الشمعة السابقة)
        if len(close) >= 2:
            returns['1h'] = ((close.iloc[-1] / close.iloc[-2]) - 1) * 100
        else:
            returns['1h'] = 0

        # 4 ساعات
        if len(close) >= 4:
            returns['4h'] = ((close.iloc[-1] / close.iloc[-4]) - 1) * 100
        else:
            returns['4h'] = 0

        # 1 يوم (24 ساعة)
        if len(close) >= 24:
            returns['1d'] = ((close.iloc[-1] / close.iloc[-24]) - 1) * 100
        else:
            returns['1d'] = 0

        return returns

    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """حساب مؤشر RSI"""
        if len(prices) < period + 1:
            return 50.0

        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        avg_loss = loss.iloc[-1]
        if avg_loss == 0:
            return 100.0  # لا خسائر = ذروة شراء

        rs = gain.iloc[-1] / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """حساب Average True Range"""
        if not _is_valid_df(df) or len(df) < period:
            return 0.0

        high = df['high']
        low = df['low']
        close = df['close']

        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr.iloc[-1]

    def calculate_support_resistance(self, df: pd.DataFrame) -> Tuple[float, float]:
        """حساب مستويات الدعم والمقاومة"""
        if not _is_valid_df(df) or len(df) < 20:
            return 0.0, 0.0

        recent = df.tail(20)
        support = recent['low'].min()
        resistance = recent['high'].max()
        return float(support), float(resistance)

    def calculate_coin_score(self, metrics: Dict) -> float:
        """حساب النتيجة النهائية للعملة (0-100)"""
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
        if volume > 10_000_000:
            volume_score = 20
        elif volume > 1_000_000:
            volume_score = 15
        elif volume > 100_000:
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

    def detect_signals(self, df: pd.DataFrame, vs_btc: float, rsi: float,
                       support: float, resistance: float, current_price: float) -> List[str]:
        """اكتشاف الإشارات الفنية"""
        signals = []

        # القوة النسبية
        if vs_btc > 5:
            signals.append("STRONG_VS_BTC")
        elif vs_btc > 2:
            signals.append("POSITIVE_VS_BTC")
        elif vs_btc < -5:
            signals.append("WEAK_VS_BTC")
        elif vs_btc < -2:
            signals.append("NEGATIVE_VS_BTC")

        # RSI
        if rsi < 30:
            signals.append("RSI_OVERSOLD")
        elif rsi > 70:
            signals.append("RSI_OVERBOUGHT")

        # الدعم والمقاومة
        if support > 0 and current_price <= support * 1.02:
            signals.append("NEAR_SUPPORT")
        if resistance > 0 and current_price >= resistance * 0.98:
            signals.append("NEAR_RESISTANCE")

        # الحجم
        if _is_valid_df(df) and len(df) > 10:
            avg_volume = df['volume'].tail(10).mean()
            current_volume = df['volume'].iloc[-1]
            if current_volume > avg_volume * 1.5:
                signals.append("HIGH_VOLUME")

        return signals

    def select_optimal_pair(self, coins: List[CoinAnalysis]) -> Optional[Dict]:
        """اختيار أفضل زوج للتداول"""
        from core.config import TRADE_SETTINGS

        if len(coins) < 2:
            return None

        best_pair = None
        best_score = -999

        strong_candidates = coins[:3]
        weak_candidates = coins[-3:]

        for strong in strong_candidates:
            for weak in weak_candidates:
                if strong.symbol == weak.symbol:
                    continue

                pair_score = self.calculate_pair_score(strong, weak)

                # شروط القبول
                conditions = {
                    'min_score_diff': abs(strong.score - weak.score) >= 20,
                    'min_perf_diff': abs(strong.vs_btc_4h - weak.vs_btc_4h) >= 3,
                    'good_liquidity': min(strong.volume_usd, weak.volume_usd) > 1_000_000,  # ✅ تم التصحيح
                    'min_pair_score': pair_score >= TRADE_SETTINGS['min_pair_score']
                }

                if all(conditions.values()) and pair_score > best_score:
                    best_score = pair_score
                    best_pair = {
                        'pair': f"{strong.symbol.replace('/USDT', '').replace(':USDT', '')}/"
                                f"{weak.symbol.replace('/USDT', '').replace(':USDT', '')}",
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
                        'timestamp': datetime.now().isoformat()
                    }

        return best_pair

    def calculate_pair_score(self, strong: CoinAnalysis, weak: CoinAnalysis) -> float:
        """حساب درجة الزوج (0-100)"""
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

        if "RSI_OVERSOLD" in weak_signals and "RSI_OVERBOUGHT" not in strong_signals:
            signal_score += 5
        if "RSI_OVERBOUGHT" in strong_signals and "RSI_OVERSOLD" not in weak_signals:
            signal_score += 5

        score += signal_score

        # السيولة المشتركة (10%)
        avg_volume = (strong.volume_usd + weak.volume_usd) / 2
        if avg_volume > 5_000_000:
            score += 10
        elif avg_volume > 1_000_000:
            score += 7
        elif avg_volume > 500_000:
            score += 4

        return min(score, 100)

    def generate_recommendation(self, strong: CoinAnalysis, weak: CoinAnalysis) -> str:
        """توليد توصية التداول"""
        strong_symbol = strong.symbol.replace('/USDT', '').replace(':USDT', '')
        weak_symbol = weak.symbol.replace('/USDT', '').replace(':USDT', '')
        return f"LONG_{strong_symbol}_SHORT_{weak_symbol}"
