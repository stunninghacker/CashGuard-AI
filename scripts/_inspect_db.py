import sys
sys.path.insert(0, '.')
from sqlalchemy import create_engine, text
from backend.config import DATABASE_URL

e = create_engine(DATABASE_URL)
with e.connect() as c:
    q = c.execute(text('SELECT COUNT(*), MIN(filing_timestamp), MAX(filing_timestamp) FROM complaints')).fetchone()
    print('complaints count/min/max:', q)
    q = c.execute(text('SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM withdrawals')).fetchone()
    print('withdrawals count/min/max:', q)
    q = c.execute(text('SELECT COUNT(*) FROM atms')).fetchone()
    print('atms count:', q)
    qt = c.execute(text('SELECT complaint_type, COUNT(*) FROM complaints GROUP BY complaint_type')).fetchall()
    print('complaint types:', qt)
    qh = c.execute(text("SELECT COUNT(DISTINCT strftime('%Y-%m-%d %H', timestamp)) FROM withdrawals")).fetchone()
    print('distinct hour-buckets in withdrawals:', qh)
    qh2 = c.execute(text("SELECT COUNT(DISTINCT strftime('%Y-%m-%d', filing_timestamp)) FROM complaints")).fetchone()
    print('distinct day-buckets in complaints:', qh2)
    # check whether victim_pin and atm pin are populated
    qp = c.execute(text('SELECT COUNT(victim_pin), COUNT(DISTINCT victim_pin) FROM complaints')).fetchone()
    print('victim_pin populated count/distinct:', qp)
    qap = c.execute(text('SELECT COUNT(pin), COUNT(DISTINCT pin) FROM atms')).fetchone()
    print('atm pin count/distinct:', qap)
    # sample banks
    qb = c.execute(text('SELECT DISTINCT bank_name FROM atms')).fetchall()
    print('banks:', [r[0] for r in qb])
    # channels
    qch = c.execute(text('SELECT DISTINCT channel FROM withdrawals LIMIT 20')).fetchall()
    print('channels:', [r[0] for r in qch])
