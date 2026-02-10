"""
وحدة إدارة المخاطر وتحديد أحجام الصفقات وأوامر الإغلاق
"""

import numpy as np
from typing import Dict, Tuple, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from core.config import TRADE_SETTINGS

@dataclass
class TradeRiskParams:
    """معلمات المخاطرة للصفقة"""
    position_size_strong: float  |  حجم المركز على العملة القوية (بالدولار)
    position_size_weak: float    |  حجم المركز على العملة الضعيفة (بالدولار)
    quantity_strong: float       |  الكمية على العملة القوية
    quantity_weak: float         |  الكمية على العملة الضعيفة
    stop_loss: float             |  وقف الخسارة بالنسبة المئوية
    take_profit: float           |  جني الأرباح بالنسبة المئوية
    max_loss_usdt: float         |  الحد الأقصى للخسارة بالدولار
    risk_reward_ratio: float     |  نسبة المخاطرة/العائد

class RiskManager:
    def __init__(self):
        self.total_capital = TRADE_SETTINGS['total_capital_usdt']
        self.risk_per_trade = TRADE_SETTINGS['risk_per_trade']
        self.take_profit_ratio = TRADE_SETTINGS['take_profit_ratio']
        self.max_open_trades = TRADE_SETTINGS['max_open_trades']
        
    def calculate_trade_parameters(self, pair_signal: Dict, strong_price: float, 
                                  weak_price: float) -> TradeRiskParams:
        """
        حساب معلمات الصفقة:
        1. توزيع رأس المال بناءً على القوة
        2. تحديد حجم المركز لكل عملة
        3. حساب وقف الخسارة وجني الأرباح
        """
        
        # 1. توزيع رأس المال حسب القوة النسبية
        strong_score = pair_signal['strong_score']
        weak_score = pair_signal['weak_score']
        total_score = strong_score + weak_score
        
        # نسبة التخصيص للعملة القوية (أكبر من 50% إذا كانت أقوى بكثير)
        strong_allocation = 0.5 + (strong_score - weak_score) / 200
        
        # تحديد مبلغ كل صفقة
        max_trade_amount = self.total_capital * (self.risk_per_trade / 100) * 50  |  رافعة 50x للتداول الزوجي
        strong_amount = max_trade_amount * strong_allocation
        weak_amount = max_trade_amount * (1 - strong_allocation)
        
        # 2. حساب الكميات
        quantity_strong = strong_amount / strong_price
        quantity_weak = weak_amount / weak_price
        
        # 3. تحديد وقف الخسارة (بناءً على الدعم/المقاومة أو نسبة 1:2)
        stop_loss, stop_loss_type = self.calculate_stop_loss(
            pair_signal, strong_price, weak_price
        )
        
        # 4. تحديد جني الأرباح (أيهما أبعد: نسبة 1:2 أو الدعم/المقاومة)
        take_profit = self.calculate_take_profit(stop_loss, pair_signal)
        
        # 5. حساب الحد الأقصى للخسارة
        max_loss_usdt = max_trade_amount * (stop_loss / 100)
        
        return TradeRiskParams(
            position_size_strong=strong_amount,
            position_size_weak=weak_amount,
            quantity_strong=quantity_strong,
            quantity_weak=quantity_weak,
            stop_loss=stop_loss,
            take_profit=take_profit,
            max_loss_usdt=max_loss_usdt,
            risk_reward_ratio=take_profit / stop_loss if stop_loss > 0 else 0
        )
    
    def calculate_stop_loss(self, pair_signal: Dict, strong_price: float, 
                           weak_price: float) -> Tuple[float, str]:
        """حساب وقف الخسارة (أيهما أقرب: الدعم أو نسبة 1%)"""
        
        # وقف الخسارة بناءً على الدعم/المقاومة
        sl_from_support = self.calculate_sl_from_support_resistance(pair_signal, strong_price, weak_price)
        
        # وقف الخسارة الثابت (نسبة من السعر)
        sl_fixed = 1.0  |  1% وقف خسارة افتراضي
        
        # اختيار الأقرب (الأكثر تحفظاً)
        if sl_from_support > 0:
            stop_loss = min(sl_from_support, sl_fixed)
            sl_type = "support_resistance" if sl_from_support < sl_fixed else "fixed_percentage"
        else:
            stop_loss = sl_fixed
            sl_type = "fixed_percentage"
        
        # تأكد أن وقف الخسارة ليس صغيراً جداً
        stop_loss = max(stop_loss, 0.5)  |  لا يقل عن 0.5%
        
        return stop_loss, sl_type
    
    def calculate_sl_from_support_resistance(self, pair_signal: Dict, 
                                            strong_price: float, weak_price: float) -> float:
        """حساب وقف الخسارة بناءً على مستويات الدعم والمقاومة"""
        
        sr_data = pair_signal['support_resistance']
        
        # للصفقة الطويلة على العملة القوية
        strong_support = sr_data['strong_support']
        strong_resistance = sr_data['strong_resistance']
        
        # للصفقة القصيرة على العملة الضعيفة
        weak_support = sr_data['weak_support']
        weak_resistance = sr_data['weak_resistance']
        
        if strong_support and weak_resistance:
            # حساب المسافة من السعر الحالي إلى أقرب مستوى
            sl_strong = abs((strong_price - strong_support) / strong_price * 100)
            sl_weak = abs((weak_resistance - weak_price) / weak_price * 100)
            
            # استخدام المتوسط أو الأكبر (لأننا نريد الأكثر أماناً)
            return max(sl_strong, sl_weak)
        
        return 0.0
    
    def calculate_take_profit(self, stop_loss: float, pair_signal: Dict) -> float:
        """حساب جني الأرباح (أيهما أبعد: نسبة 1:2 أو المقاومة)"""
        
        # جني الأرباح بنسبة 1:2
        tp_from_ratio = stop_loss * self.take_profit_ratio
        
        # جني الأرباح من المقاومة (إذا كانت متوفرة)
        sr_data = pair_signal['support_resistance']
        strong_price = pair_signal['entry_prices']['strong']
        weak_price = pair_signal['entry_prices']['weak']
        
        tp_from_resistance = self.calculate_tp_from_resistance(
            sr_data, strong_price, weak_price
        )
        
        # اختيار الأبعد (لتحقيق ربح أكبر)
        if tp_from_resistance > 0:
            take_profit = max(tp_from_ratio, tp_from_resistance)
        else:
            take_profit = tp_from_ratio
        
        # تأكد أن جني الأرباح ليس صغيراً جداً
        take_profit = max(take_profit, stop_loss * 1.5)  |  لا يقل عن 1.5x وقف الخسارة
        
        return take_profit
    
    def calculate_tp_from_resistance(self, sr_data: Dict, strong_price: float, 
                                    weak_price: float) -> float:
        """حساب جني الأرباح بناءً على مستويات المقاومة"""
        
        strong_resistance = sr_data['strong_resistance']
        weak_support = sr_data['weak_support']
        
        if strong_resistance and weak_support:
            # حساب المسافة إلى المقاومة للعملة القوية
            tp_strong = abs((strong_resistance - strong_price) / strong_price * 100)
            
            # حساب المسافة إلى الدعم للعملة الضعيفة (نريدها تنخفض)
            tp_weak = abs((weak_price - weak_support) / weak_price * 100)
            
            # استخدام المتوسط
            return (tp_strong + tp_weak) / 2
        
        return 0.0
    
    def check_trade_viability(self, open_trades_count: int, pair_score: float, 
                             risk_params: TradeRiskParams) -> Tuple[bool, str]:
        """فحص جدوى الصفقة"""
        
        reasons = []
        
        # 1. الحد الأقصى للصفقات المفتوحة
        if open_trades_count >= self.max_open_trades:
            reasons.append(f"تجاوز الحد الأقصى للصفقات ({self.max_open_trades})")
        
        # 2. درجة الزوج
        if pair_score < TRADE_SETTINGS['min_pair_score']:
            reasons.append(f"درجة الزوج منخفضة ({pair_score:.1f})")
        
        # 3. نسبة المخاطرة/العائد
        if risk_params.risk_reward_ratio < 1.5:
            reasons.append(f"نسبة المخاطرة/العائد ضعيفة ({risk_params.risk_reward_ratio:.1f})")
        
        # 4. الحد الأقصى للخسارة
        if risk_params.max_loss_usdt > self.total_capital * 0.02:  |  2% من رأس المال
            reasons.append(f"الخسارة المحتملة كبيرة ({risk_params.max_loss_usdt:.2f} USDT)")
        
        if reasons:
            return False, " | ".join(reasons)
        
        return True, "الصفقة مقبولة"
    
    def calculate_position_sizing(self, current_pnl: float, 
                                 total_trades_today: int) -> float:
        """حساب حجم الصفقة الديناميكي بناءً على الأداء"""
        
        base_size = self.total_capital * (self.risk_per_trade / 100)
        
        # تقليل الحجم إذا كانت الخسائر اليومية عالية
        if current_pnl < -5:  |  خسارة أكثر من 5%
            size_multiplier = 0.5
        elif current_pnl < -2:  |  خسارة أكثر من 2%
            size_multiplier = 0.75
        elif current_pnl > 5:  |  ربح أكثر من 5%
            size_multiplier = 1.25
        elif current_pnl > 2:  |  ربح أكثر من 2%
            size_multiplier = 1.1
        else:
            size_multiplier = 1.0
        
        # تقليل الحجم إذا كان عدد الصفقات اليومية عالياً
        if total_trades_today > 10:
            size_multiplier *= 0.8
        elif total_trades_today > 5:
            size_multiplier *= 0.9
        
        return base_size * size_multiplier
