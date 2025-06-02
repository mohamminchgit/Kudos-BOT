@echo off
cd /d D:\V2.0.2-Final-KUDOS-BOT\Kudos-BOT
:loop
python bot.py
timeout /t 5
goto loop
