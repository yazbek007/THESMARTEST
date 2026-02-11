"""
وحدة اكتشاف أفضل أزواج التداول بناءً على القوة النسبية مقابل BTC
للعقود الآجلة على Binance Futures
"""

import ccxt
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import asyncio
import logging
from dataclasses import dataclass, field

from core.config import COINS_TO_MONITOR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _is_valid_df(df: Optional[pd.DataFrame]) -> bool:
    """التحقق من صحة DataFrame وعدم فراغه"""
    return df is not None and isinstance(df, pd.DataFrame) and not df.empty


@dataclass
class CoinAnalysis:
    """تحليل شامل لعملة ما"""
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
    """الباحث الذكي عن أفضل أزواج التداول"""

    def __init__(self, use_testnet: bool = False):
        self.exchange = self._init_exchange(use_testnet)
        self.btc_symbol = "BTC/USDT:USDT"  # رمز BTC على العقود الآجلة
        self.cache = {}

    def _init_exchange(self, use_testnet: bool):
        """تهيئة اتصال Binance Futures"""
        from core.config import BINANCE_CONFIG

        # التكوين الأساسي
        config = {
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',        # عقود آجلة
                'adjustForTimeDifference': True,
            }
        }

        # إضافة مفاتيح API إن وجدت
        if BINANCE_CONFIG and BINANCE_CONFIG.get('api_key'):
            config['apiKey'] = BINANCE_CONFIG['api_key']
            config['secret'] = BINANCE_CONFIG['api_secret']

            # إذا كانت المفاتيح حقيقية (ليست testnet الافتراضية)، نجبر use_testnet=False
            if BINANCE_CONFIG['api_key'] != 'testnet_api_key':
                use_testnet = False
                logger.info("🚀 استخدام Binance Production (حقيقي)")
            else:
                logger.warning("⚠️ مفاتيح Testnet الافتراضية – قد لا تعمل")

        if use_testnet:
            logger.info("🔧 وضع الاختبار: Binance Futures Testnet")
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
            # Production – تأكد من وجود مفاتيح صالحة
            if not config.get('apiKey') or config['apiKey'] == 'testnet_api_key':
                raise ValueError(
                    "❌ لا يمكن استخدام Production بدون مفاتيح API صالحة. "
                    "قم بتعيين BINANCE_API_KEY و BINANCE_API_SECRET في البيئة."
                )
            config['urls'] = {
                'api': {
                    'public': 'https://fapi.binance.com/fapi/v1',
                    'private': 'https://fapi.binance.com/fapi/v1'
                }
            }

        # إنشاء كائن التبادل
        exchange = ccxt.binance(config)

        # اختبار الاتصال
        try:
            exchange.fetch_time()
            logger.info("✅ تم الاتصال بـ Binance Futures بنجاح")
        except Exception as e:
            logger.error(f"❌ فشل الاتصال: {e}")
            raise

        return exchange

    async def find_best_trading_pair(self) -> Optional[Dict]:
        """
        البحث عن أفضل زوج تداول بناءً على:
        - القوة النسبية مقابل BTC
        - مستويات الدعم والمقاومة
        - السيولة
        - الإشارات الفنية
        """
        logger.info("🔍 بدء البحث عن أفضل زوج تداول...")

        try:
            # 1. جلب بيانات BTC
            btc_data = await self._get_btc_analysis()
            if btc_data is None:
                logger.error("❌ فشل جلب بيانات BTC – إيقاف البحث")
                return None

            # 2. تحليل جميع العملات
            coins_analysis = []
            for symbol in COINS_TO_MONITOR:
                coin = await self._analyze_coin(symbol, btc_data)
                if coin and coin.score > 0:
                    coins_analysis.append(coin)
                    logger.debug(f"📊 {symbol}: score={coin.score:.1f}")

            if len(coins_analysis) < 2:
                logger.warning("⚠️ لا توجد عملات كافية للتحليل (أقل من 2)")
                return None

            # 3. ترتيب تنازلي حسب القوة
            coins_analysis.sort(key=lambda x: x.score, reverse=True)

            # 4. اختيار أفضل زوج
            best_pair = self._select_optimal_pair(coins_analysis)

            if best_pair:
                logger.info(
                    f"✅ أفضل زوج: {best_pair['pair']} | "
                    f"الدرجة: {best_pair['pair_score']:.1f} | "
                    f"التوصية: {best_pair['recommendation']}"
                )
            else:
                logger.info("❌ لم يتم العثور على زوج يستوفي الشروط")

            return best_pair

        except Exception as e:
            logger.error(f"❌ خطأ في البحث عن الزوج: {e}")
            return None

    async def _get_btc_analysis(self) -> Optional[pd.DataFrame]:
        """جلب آخر 100 شمعة لـ BTC/USDT:USDT"""
        try:
            ohlcv = await asyncio.to_thread(
                self.exchange.fetch_ohlcv,
                self.btc_symbol,
                timeframe='1h',
                limit=100
            )

            if not ohlcv or len(ohlcv) < 20:
                logger.error("❌ بيانات BTC غير كافية")
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
            logger.error(f"❌ خطأ في جلب BTC: {e}")
            return None

    async def _analyze_coin(self, symbol: str, btc_data: pd.DataFrame) -> Optional[CoinAnalysis]:
        """
        تحليل عملة واحدة:
        - لا نقوم بتنظيف الرمز – نستخدمه كما هو (مثل BTC/USDT:USDT)
        - نعتمد على btc_data للحصول على سعر BTC
        """
        try:
            # 1. جلب OHLCV للعملة
            ohlcv = await asyncio.to_thread(
                self.exchange.fetch_ohlcv,
                symbol,                     # استخدم الرمز الأصلي
                timeframe='1h',
                limit=100,
                params={'price': 'mark'}    # سعر العلامة للعقود الآجلة
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

            # 2. جلب السعر الحالي (ticker)
            ticker = await asyncio.to_thread(self.exchange.fetch_ticker, symbol)
            current_price = ticker['last']
            volume_usd = ticker.get('quoteVolume', 0)

            # 3. حساب سعر العملة مقابل BTC باستخدام آخر سعر لـ BTC
            btc_price = btc_data['close'].iloc[-1]   # سعر BTC الحالي
            price_btc = current_price / btc_price if btc_price > 0 else 0.0

            # 4. حساب العوائد
            coin_returns = self._calculate_returns(df)
            btc_returns = self._calculate_returns(btc_data)

            vs_btc_1h = coin_returns.get('1h', 0) - btc_returns.get('1h', 0)
            vs_btc_4h = coin_returns.get('4h', 0) - btc_returns.get('4h', 0)
            vs_btc_1d = coin_returns.get('1d', 0) - btc_returns.get('1d', 0)

            # 5. المؤشرات الفنية
            rsi = self._calculate_rsi(df['close'])
            atr = self._calculate_atr(df)
            atr_percent = (atr / current_price * 100) if atr and current_price > 0 else 0.0

            # 6. الدعم والمقاومة
            support, resistance = self._calculate_support_resistance(df)

            # 7. درجة القوة
            score = self._calculate_coin_score({
                'vs_btc_4h': vs_btc_4h,
                'vs_btc_1d': vs_btc_1d,
                'rsi': rsi,
                'atr_percent': atr_percent,
                'volume': volume_usd,
                'price': current_price
            })

            # 8. الإشارات
            signals = self._detect_signals(
                df, vs_btc_4h, rsi, support, resistance, current_price
            )

            logger.debug(f"✅ {symbol}: score={score:.1f}, RSI={rsi:.1f}, ATR%={atr_percent:.2f}")

            return CoinAnalysis(
                symbol=symbol,
                price=current_price,
                price_btc=price_btc,
                vs_btc_1h=vs_btc_1h,
                vs_btc_4h=vs_btc_4h,
                vs_btc_1d=vs_btc_1d,
                rsi=rsi,
                atr_percent=atr_percent,
                volume_usd=volume_usd,
                score=score,
                signals=signals,
                support_level=support,
                resistance_level=resistance
            )

        except ccxt.BadSymbol as e:
            logger.error(f"❌ رمز غير صالح {symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ خطأ في تحليل {symbol}: {e}")
            return None

    @staticmethod
    def _calculate_returns(df: pd.DataFrame) -> Dict[str, float]:
        """حساب العوائد خلال 1h, 4h, 1d"""
        if not _is_valid_df(df) or len(df) < 24:
            return {'1h': 0.0, '4h': 0.0, '1d': 0.0}

        close = df['close']
        returns = {}

        # 1 ساعة (شمعة مقابل سابقتها)
        returns['1h'] = ((close.iloc[-1] / close.iloc[-2]) - 1) * 100 if len(close) >= 2 else 0.0
        # 4 ساعات
        returns['4h'] = ((close.iloc[-1] / close.iloc[-4]) - 1) * 100 if len(close) >= 4 else 0.0
        # 24 ساعة
        returns['1d'] = ((close.iloc[-1] / close.iloc[-24]) - 1) * 100 if len(close) >= 24 else 0.0

        return returns

    @staticmethod
    def _calculate_rsi(prices: pd.Series, period: int = 14) -> float:
        """مؤشر القوة النسبية RSI"""
        if len(prices) < period + 1:
            return 50.0

        delta = prices.diff()
        gain = delta.where(delta > 0, 0.0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()

        avg_loss = loss.iloc[-1]
        if avg_loss == 0:
            return 100.0

        rs = gain.iloc[-1] / avg_loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
        """متوسط المدى الحقيقي ATR"""
        if not _is_valid_df(df) or len(df) < period:
            return 0.0

        high, low, close = df['high'], df['low'], df['close']
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr.iloc[-1]

    @staticmethod
    def _calculate_support_resistance(df: pd.DataFrame, window: int = 20) -> Tuple[float, float]:
        """مستويات الدعم (أدنى سعر) والمقاومة (أعلى سعر) لآخر window شمعة"""
        if not _is_valid_df(df) or len(df) < window:
            return 0.0, 0.0

        recent = df.tail(window)
        support = recent['low'].min()
        resistance = recent['high'].max()
        return float(support), float(resistance)

    @staticmethod
    def _calculate_coin_score(metrics: Dict) -> float:
        """
        حساب درجة العملة (0-100) بناءً على:
        - الأداء مقابل BTC (40%)
        - RSI (25%)
        - السيولة (20%)
        - التقلب (15%)
        """
        score = 0.0

        # 1. الأداء مقابل BTC (40%)
        perf = metrics.get('vs_btc_4h', 0) * 0.6 + metrics.get('vs_btc_1d', 0) * 0.4
        perf = max(min(perf, 10), -10)  # حصر بين -10 و +10
        score += ((perf + 10) / 20) * 40

        # 2. RSI (25%)
        rsi = metrics.get('rsi', 50)
        if 40 <= rsi <= 60:
            score += 25
        elif 30 <= rsi < 40 or 60 < rsi <= 70:
            score += 15
        else:
            score += 5

        # 3. السيولة (20%)
        volume = metrics.get('volume', 0)
        if volume > 10_000_000:
            score += 20
        elif volume > 1_000_000:
            score += 15
        elif volume > 100_000:
            score += 10
        else:
            score += 5

        # 4. التقلب (15%)
        atr = metrics.get('atr_percent', 0)
        if 1.0 <= atr <= 3.0:
            score += 15
        elif 0.5 <= atr < 1.0 or 3.0 < atr <= 5.0:
            score += 10
        else:
            score += 5

        return max(0, min(score, 100))

    @staticmethod
    def _detect_signals(df: pd.DataFrame, vs_btc: float, rsi: float,
                        support: float, resistance: float, price: float) -> List[str]:
        """اكتشاف الإشارات الفنية"""
        signals = []

        # إشارات القوة مقابل BTC
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

        # إشارات الدعم/المقاومة
        if support > 0 and price <= support * 1.02:
            signals.append("NEAR_SUPPORT")
        if resistance > 0 and price >= resistance * 0.98:
            signals.append("NEAR_RESISTANCE")

        # إشارة حجم مرتفع
        if _is_valid_df(df) and len(df) > 10:
            avg_vol = df['volume'].tail(10).mean()
            curr_vol = df['volume'].iloc[-1]
            if curr_vol > avg_vol * 1.5:
                signals.append("HIGH_VOLUME")

        return signals

    def _select_optimal_pair(self, coins: List[CoinAnalysis]) -> Optional[Dict]:
        """اختيار أفضل زوج من قائمة العملات المحللة"""
        from core.config import TRADE_SETTINGS

        if len(coins) < 2:
            return None

        best_pair = None
        best_score = -999

        # أفضل 3 عملات قوية وأسوأ 3 عملات ضعيفة
        strong_candidates = coins[:3]
        weak_candidates = coins[-3:]

        for strong in strong_candidates:
            for weak in weak_candidates:
                if strong.symbol == weak.symbol:
                    continue

                pair_score = self._calculate_pair_score(strong, weak)

                # شروط القبول
                conditions = {
                    'min_score_diff': abs(strong.score - weak.score) >= 20,
                    'min_perf_diff': abs(strong.vs_btc_4h - weak.vs_btc_4h) >= 3,
                    'min_liquidity': min(strong.volume_usd, weak.volume_usd) > 1_000_000,
                    'min_pair_score': pair_score >= TRADE_SETTINGS['min_pair_score']
                }

                if all(conditions.values()) and pair_score > best_score:
                    best_score = pair_score
                    best_pair = self._build_pair_dict(strong, weak, pair_score)

        return best_pair

    @staticmethod
    def _calculate_pair_score(strong: CoinAnalysis, weak: CoinAnalysis) -> float:
        """درجة الزوج (0-100)"""
        score = 0.0

        # 1. اختلاف القوة (40%)
        score += min(abs(strong.score - weak.score), 40)

        # 2. اختلاف الأداء مقابل BTC (30%)
        perf_diff = abs(strong.vs_btc_4h - weak.vs_btc_4h)
        score += min(perf_diff * 3, 30)

        # 3. جودة الإشارات (20%)
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

        # 4. السيولة المشتركة (10%)
        avg_volume = (strong.volume_usd + weak.volume_usd) / 2
        if avg_volume > 5_000_000:
            score += 10
        elif avg_volume > 1_000_000:
            score += 7
        elif avg_volume > 500_000:
            score += 4

        return min(score, 100)

    @staticmethod
    def _build_pair_dict(strong: CoinAnalysis, weak: CoinAnalysis, pair_score: float) -> Dict:
        """بناء قاموس الزوج المرشح"""
        # استخراج أسماء العملات بدون اللواحق للعرض
        strong_name = strong.symbol.split('/')[0].replace(':USDT', '')
        weak_name = weak.symbol.split('/')[0].replace(':USDT', '')

        return {
            'pair': f"{strong_name}/{weak_name}",
            'strong_coin': strong,
            'weak_coin': weak,
            'strong_score': strong.score,
            'weak_score': weak.score,
            'score_difference': strong.score - weak.score,
            'performance_diff_4h': strong.vs_btc_4h - weak.vs_btc_4h,
            'pair_score': pair_score,
            'recommendation': f"LONG_{strong_name}_SHORT_{weak_name}",
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
