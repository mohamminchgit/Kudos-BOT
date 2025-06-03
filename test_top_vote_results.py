#!/usr/bin/env python3
"""
تست عملکرد نتایج رای‌گیری ترین‌ها
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

import config
from src.handlers.top_vote_handlers import _get_top_results_for_question, _get_active_top_questions
from src.services.ai import get_top_vote_results

def test_top_vote_results():
    """تست نتایج رای‌گیری"""
    print("🔍 تست نتایج رای‌گیری ترین‌ها...")
    
    # دریافت سوالات فعال
    print("\n1. دریافت سوالات فعال:")
    questions = _get_active_top_questions()
    print(f"  تعداد سوالات فعال: {len(questions)}")
    
    if questions:
        for q_id, q_text in questions[:3]:  # نشان دادن 3 سوال اول
            print(f"  - سوال {q_id}: {q_text}")
            
            # تست نتایج برای هر سوال
            print(f"\n2. تست نتایج برای سوال {q_id}:")
            try:
                results = _get_top_results_for_question(q_id)
                print(f"  تعداد نتایج: {len(results)}")
                
                if results:
                    for i, (voted_for, count, name) in enumerate(results[:3]):
                        print(f"    {i+1}. {name}: {count} رای")
                else:
                    print("  هیچ رایی ثبت نشده")
                    
            except Exception as e:
                print(f"  ❌ خطا در دریافت نتایج: {e}")
            
            print("-" * 40)
    
    # تست تابع عمومی نتایج
    print("\n3. تست تابع عمومی نتایج:")
    try:
        general_results = get_top_vote_results(season_id=config.SEASON_ID)
        print(f"  تعداد نتایج کلی: {len(general_results)}")
        
        if general_results:
            for i, (voted_for, count, name) in enumerate(general_results[:5]):
                print(f"    {i+1}. {name}: {count} رای")
    except Exception as e:
        print(f"  ❌ خطا در دریافت نتایج کلی: {e}")

if __name__ == "__main__":
    test_top_vote_results()
