"""
توابع مرتبط با عملیات فصل‌ها
"""
import logging
from ..database.db_utils import get_db_connection

logger = logging.getLogger(__name__)

def get_season_scoreboard(season_id):
    """دریافت تابلوی امتیازات یک فصل خاص"""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT touser, SUM(amount) as total, u.name 
            FROM transactions t 
            LEFT JOIN users u ON t.touser = u.user_id 
            WHERE t.season_id=?
            GROUP BY touser 
            ORDER BY total DESC LIMIT 10
        """, (season_id,))
        return c.fetchall()
    except Exception as e:
        logger.error(f"خطا در دریافت تابلوی امتیازات: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_user_season_stats(user_id, season_id):
    """دریافت آمار کاربر در یک فصل خاص"""
    stats = {
        'received_count': 0,
        'received_amount': 0,
        'given_count': 0,
        'given_amount': 0,
        'top_votes': [],
        'rank': 0,
        'total_users': 0
    }
    
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # دریافت آمار تراکنش‌های دریافتی
        c.execute("""
            SELECT COUNT(*), SUM(amount)
            FROM transactions
            WHERE touser=? AND season_id=?
        """, (user_id, season_id))
        result = c.fetchone()
        if result:
            stats['received_count'] = result[0] or 0
            stats['received_amount'] = result[1] or 0
        
        # دریافت آمار تراکنش‌های داده شده
        c.execute("""
            SELECT COUNT(*), SUM(amount)
            FROM transactions
            WHERE user_id=? AND season_id=?
        """, (user_id, season_id))
        result = c.fetchone()
        if result:
            stats['given_count'] = result[0] or 0
            stats['given_amount'] = result[1] or 0
        
        # دریافت رتبه کاربر در فصل
        c.execute("""
            WITH UserRanks AS (
                SELECT 
                    touser, 
                    SUM(amount) as total,
                    RANK() OVER (ORDER BY SUM(amount) DESC) as rank
                FROM transactions 
                WHERE season_id=?
                GROUP BY touser
            )
            SELECT rank, (SELECT COUNT(DISTINCT touser) FROM transactions WHERE season_id=?)
            FROM UserRanks 
            WHERE touser=?
        """, (season_id, season_id, user_id))
        rank_result = c.fetchone()
        if rank_result:
            stats['rank'] = rank_result[0]
            stats['total_users'] = rank_result[1]
        
        # دریافت آمار ترین‌های کاربر
        c.execute("""
            SELECT q.text, COUNT(v.vote_id) as vote_count, GROUP_CONCAT(u.name, ', ') as voters
            FROM top_votes v
            JOIN top_questions q ON v.question_id = q.question_id
            JOIN users u ON v.user_id = u.user_id
            WHERE v.voted_for_user_id=? AND v.season_id=?
            GROUP BY q.question_id
        """, (user_id, season_id))
        top_votes = c.fetchall()
        if top_votes:
            stats['top_votes'] = [(row[0], row[1], row[2]) for row in top_votes]
        
        return stats
    except Exception as e:
        logger.error(f"خطا در دریافت آمار کاربر: {e}")
        return stats
    finally:
        if conn:
            conn.close() 