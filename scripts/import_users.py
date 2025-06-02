import sqlite3
from config import DB_PATH
import config

users = [
    {"id": 1, "name": "علی معمار", "balance": 100, "user_id": 97164371, "birthday": None, "username": None, "created_at": None},
    {"id": 2, "name": "مهدی حسینی", "balance": 90, "user_id": 83553051, "birthday": None, "username": None, "created_at": None},
    {"id": 3, "name": "حسین انگاشته", "balance": 100, "user_id": 1939118028, "birthday": None, "username": "SimorghSupport_Engashteh", "created_at": "2025-02-09 11:43:21.000000"},
    {"id": 4, "name": "هانی رضایی", "balance": 100, "user_id": 438311561, "birthday": None, "username": "SimorghSupport_Rezaei", "created_at": "2025-02-09 11:44:04.000000"},
    {"id": 5, "name": "یاسین ولی", "balance": 30, "user_id": 84316833, "birthday": None, "username": "Yassinvali", "created_at": "2025-02-09 11:44:26.000000"},
    {"id": 6, "name": "محمدرضا معمار", "balance": 100, "user_id": 110549011, "birthday": None, "username": None, "created_at": "2025-02-09 11:46:48.000000"},
    {"id": 7, "name": "حسین هاشمیان", "balance": 65, "user_id": 110344197, "birthday": None, "username": "hosseinhashemian", "created_at": "2025-02-09 11:47:22.000000"},
    {"id": 8, "name": "بهزاد اصفهانی", "balance": 100, "user_id": 422626662, "birthday": None, "username": "BehzadSfhn", "created_at": "2025-02-09 11:47:40.000000"},
    {"id": 9, "name": "مجید ده نمکی", "balance": 90, "user_id": 274432130, "birthday": None, "username": "D_Whitebeard", "created_at": "2025-02-09 11:48:08.000000"},
    {"id": 10, "name": "علی  اخباری", "balance": 60, "user_id": 245149665, "birthday": None, "username": "ali_akhbari", "created_at": "2025-02-09 11:48:30.000000"},
    {"id": 11, "name": "سعید امیدی", "balance": 70, "user_id": 222807547, "birthday": None, "username": "saeedomidiii", "created_at": "2025-02-09 11:48:41.000000"},
    {"id": 12, "name": "محمد تقی زاده", "balance": 50, "user_id": 150800621, "birthday": None, "username": "taghizadeh_mhmd", "created_at": "2025-02-09 11:49:25.000000"},
    {"id": 13, "name": "مصطفی حسینخانی", "balance": 70, "user_id": 126164042, "birthday": None, "username": "Perclies", "created_at": "2025-02-09 11:50:09.000000"},
    {"id": 14, "name": "امیرحسین باقرزاده", "balance": 75, "user_id": 7699849418, "birthday": None, "username": "SimorghProject_Bagherzadeh", "created_at": "2025-02-09 11:50:43.000000"},
    {"id": 15, "name": "مصطفی فتحی", "balance": 100, "user_id": 110702431, "birthday": None, "username": "mostafafathiii", "created_at": "2025-02-09 11:51:03.000000"},
    {"id": 16, "name": "حسین علی عسگری", "balance": 25, "user_id": 283552388, "birthday": None, "username": "HosseinAliAsgari", "created_at": "2025-02-09 11:52:42.000000"},
    {"id": 17, "name": "مهدی سعیدی", "balance": 80, "user_id": 516218590, "birthday": None, "username": "saeidi_dev", "created_at": "2025-02-09 11:52:54.000000"},
    {"id": 18, "name": "مرتضی پورحسین", "balance": 90, "user_id": 1423078300, "birthday": None, "username": "Simorghsupport_Pourhossein", "created_at": "2025-02-09 11:53:16.000000"},
    {"id": 19, "name": "رحمان شمسی", "balance": 100, "user_id": 6987405825, "birthday": None, "username": "RahmanShamsi2025", "created_at": "2025-02-09 11:53:29.000000"},
    {"id": 20, "name": "علی پوربهروزان", "balance": 100, "user_id": 70833892, "birthday": None, "username": "poorbehroozan", "created_at": "2025-02-09 11:53:44.000000"},
    {"id": 21, "name": "محمدرضا مهاجرنیا", "balance": 30, "user_id": 92903851, "birthday": None, "username": "mrmohajernia", "created_at": "2025-02-09 11:53:54.000000"},
    {"id": 22, "name": "آوا قاسمی", "balance": 100, "user_id": 7415375623, "birthday": None, "username": "SimorghSupport_Ghasemi", "created_at": "2025-02-09 11:54:14.000000"},
    {"id": 23, "name": "علی معماری", "balance": 100, "user_id": 121713560, "birthday": None, "username": "HR_34000", "created_at": "2025-02-09 11:56:07.000000"},
    {"id": 24, "name": " میلاد نیک آزما", "balance": 100, "user_id": 5616348466, "birthday": None, "username": "millaadams", "created_at": "2025-02-09 11:57:22.000000"},
    {"id": 26, "name": "سپهر شعبانی", "balance": 100, "user_id": 1816545723, "birthday": None, "username": "SimorghSupport_Shabani", "created_at": "2025-02-09 12:02:31.000000"},
    {"id": 27, "name": "احمد کمالی", "balance": 51, "user_id": 7091595139, "birthday": None, "username": "SimorghProject_Kamali", "created_at": "2025-02-09 12:03:35.000000"},
    {"id": 28, "name": "علی پور بهروزان", "balance": 100, "user_id": 7868874927, "birthday": None, "username": "alipoorbehroozan", "created_at": "2025-02-09 12:05:56.000000"},
    {"id": 29, "name": "مجید فاضلی", "balance": 100, "user_id": 416031526, "birthday": None, "username": "majidfazeli1", "created_at": "2025-02-09 12:07:24.000000"},
    {"id": 30, "name": "علی دهقانی", "balance": 100, "user_id": 1003089783, "birthday": None, "username": "Dehghani1404", "created_at": "2025-02-09 12:08:09.000000"},
    {"id": 31, "name": "حامد قربانی", "balance": 100, "user_id": 191620139, "birthday": None, "username": "Ghorbani_hamedd", "created_at": "2025-02-09 12:09:21.000000"},
    {"id": 33, "name": "فرزین مجد", "balance": 100, "user_id": 6010489050, "birthday": None, "username": "farzin_majd", "created_at": "2025-02-09 12:11:51.000000"},
    {"id": 34, "name": "حسین عرب", "balance": 90, "user_id": 1737639707, "birthday": None, "username": "M_Hossein_arab", "created_at": "2025-02-09 12:13:57.000000"},
    {"id": 35, "name": "فاطمه فرمان زاده", "balance": 100, "user_id": 7560974272, "birthday": None, "username": "Fatemeh_Farmanzadeh", "created_at": "2025-02-09 12:16:13.000000"},
    {"id": 36, "name": "رضا خلعتبری", "balance": 100, "user_id": 815221436, "birthday": None, "username": "Reza_khalatbari_l", "created_at": "2025-02-09 12:16:57.000000"},
    {"id": 37, "name": "مصطفی طحان نژاد ", "balance": 70, "user_id": 1453634941, "birthday": None, "username": "Mustafa_Thn", "created_at": "2025-02-09 12:18:05.000000"},
    {"id": 38, "name": "علی احمدی", "balance": 100, "user_id": 97650917, "birthday": None, "username": "SeniorAhmadi", "created_at": "2025-02-09 12:18:23.000000"},
    {"id": 39, "name": "توحید لطفی", "balance": 100, "user_id": 46059517, "birthday": None, "username": "tlotfi", "created_at": "2025-02-09 12:20:02.000000"},
    {"id": 40, "name": "محسن رجبی گلمهر", "balance": 100, "user_id": 185330596, "birthday": None, "username": "MohsenDev90", "created_at": "2025-02-09 12:21:22.000000"},
    {"id": 42, "name": "امین فاطمی", "balance": 80, "user_id": 74979638, "birthday": None, "username": "Faamin", "created_at": "2025-02-09 12:24:49.000000"},
    {"id": 43, "name": "مجتبی شاقی", "balance": 100, "user_id": 6693154859, "birthday": None, "username": "shaghi60", "created_at": "2025-02-09 12:25:48.000000"},
    {"id": 44, "name": "پویا رحیمی", "balance": 100, "user_id": 7709912372, "birthday": None, "username": "Pouya_ra94", "created_at": "2025-02-09 12:26:23.000000"},
    {"id": 45, "name": "علی خانچرلی", "balance": 60, "user_id": 315867518, "birthday": None, "username": "Ali_khancherli", "created_at": "2025-02-09 13:29:32.000000"},
    {"id": 46, "name": "زهرا هاشمیان پور", "balance": 40, "user_id": 180497899, "birthday": None, "username": "Zarhp", "created_at": "2025-02-09 13:30:45.000000"},
    {"id": 48, "name": "مجید سیفی", "balance": 75, "user_id": 5734904638, "birthday": None, "username": "majid_seifi", "created_at": "2025-02-09 13:37:58.000000"},
    {"id": 49, "name": "امین هواسی", "balance": 95, "user_id": 368739228, "birthday": None, "username": "amin_offline", "created_at": "2025-02-09 13:38:56.000000"},
    {"id": 51, "name": "فاطمه اجیلی", "balance": 71, "user_id": 106583524, "birthday": None, "username": "fatemeh_ajili", "created_at": "2025-02-09 13:41:07.000000"},
    {"id": 53, "name": "محمدجواد موسوی", "balance": 100, "user_id": 101250034, "birthday": None, "username": "smjmousavi68", "created_at": "2025-02-09 13:44:48.000000"},
    {"id": 56, "name": "محسن کهندانی", "balance": 100, "user_id": 135819842, "birthday": None, "username": None, "created_at": "2025-02-09 13:51:49.000000"},
    {"id": 57, "name": "مهدی اعتمادی", "balance": 100, "user_id": 1985282555, "birthday": None, "username": None, "created_at": "2025-02-09 13:52:06.000000"},
    {"id": 59, "name": "آرش ملک تاجی", "balance": 100, "user_id": 5124754671, "birthday": None, "username": "SimorghSupport_Malektaji", "created_at": "2025-02-16 14:56:53.000000"},
    {"id": 60, "name": "محمد بهمنیار", "balance": 100, "user_id": 6741300396, "birthday": None, "username": "bahmanyar_PmSimorgh", "created_at": "2025-02-17 06:22:09.000000"},
    {"id": 61, "name": "محمدامین چراغیان", "balance": 57, "user_id": 882730020, "birthday": None, "username": "mohamminch", "created_at": "2025-02-18 12:15:42.000000"},
    {"id": 64, "name": "حسام قدیری", "balance": 100, "user_id": 6434872716, "birthday": None, "username": "SimorghSupport_Ghadiri", "created_at": "2025-02-23 10:02:48.000000"},
    {"id": 65, "name": "مصطفی عسکری", "balance": 90, "user_id": 1132635555, "birthday": None, "username": "mostafa_askari2000", "created_at": "2025-02-23 10:07:48.000000"},
    {"id": 66, "name": "حمید شهبازی", "balance": 100, "user_id": 5914461309, "birthday": None, "username": "h_shahbbazi", "created_at": "2025-02-23 11:27:28.000000"},
    {"id": 67, "name": "نور سجادی", "balance": 80, "user_id": 7146836414, "birthday": None, "username": "noursajadi02", "created_at": "2025-03-01 05:57:38.000000"},
    {"id": 68, "name": "حسین زرگر", "balance": 100, "user_id": 192204657, "birthday": None, "username": "Hosseinam0_0", "created_at": "2025-03-01 06:02:45.000000"},
    {"id": 69, "name": "محمد لاجوردی", "balance": 100, "user_id": 6316472362, "birthday": None, "username": None, "created_at": "2025-03-03 10:40:01.000000"},
    {"id": 70, "name": "مینا میرجلیلی", "balance": 100, "user_id": 88094478, "birthday": None, "username": None, "created_at": "2025-03-08 06:01:51.000000"},
    {"id": 71, "name": "فاطمه ناصری", "balance": 20, "user_id": 5090731432, "birthday": None, "username": "avafn", "created_at": "2025-03-10 09:47:26.000000"},
    {"id": 72, "name": "فاطمه نمازیان", "balance": 35, "user_id": 5725831272, "birthday": None, "username": "DrNamazian", "created_at": "2025-03-11 11:27:08.000000"},
    {"id": 73, "name": "مهدی غلامی", "balance": 30, "user_id": 241885704, "birthday": None, "username": "MGH7071", "created_at": "2025-04-21 08:44:18.000000"},
    {"id": 74, "name": "محمدرضا جهان‌ نما", "balance": 100, "user_id": 410271064, "birthday": None, "username": "Mrj_78", "created_at": "2025-04-21 09:26:52.000000"},
    {"id": 75, "name": "سمیرا محمدزاده", "balance": 100, "user_id": 5488361676, "birthday": None, "username": "Samiramohammadzade", "created_at": "2025-04-30 09:32:55.000000"},
    {"id": 76, "name": "میثم حسنی", "balance": 50, "user_id": 95238384, "birthday": None, "username": "meisamhasani", "created_at": "2025-04-30 09:34:01.000000"}
]

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
for user in users:
    c.execute('''
        INSERT OR REPLACE INTO users (user_id, username, name, balance, birthday, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        user['user_id'],
        user.get('username'),
        user['name'],
        user['balance'],
        user.get('birthday'),
        user.get('created_at')
    ))
conn.commit()

# بررسی وجود ادمین گاد
c.execute("SELECT * FROM admins WHERE user_id=?", (config.ADMIN_USER_ID,))
if not c.fetchone():
    c.execute("INSERT INTO admins (user_id, role, permissions) VALUES (?, ?, ?)", (config.ADMIN_USER_ID, 'god', 'all'))
    print(f"ادمین گاد با user_id={config.ADMIN_USER_ID} اضافه شد.")
conn.commit()
conn.close()

print('Users imported.') 