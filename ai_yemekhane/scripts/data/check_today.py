# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from models import SessionLocal, Menu
from datetime import date

db = SessionLocal()
bugun = date.today()
menu = db.query(Menu).filter(Menu.tarih == bugun).first()
if menu:
    d = menu.to_dict()
    print(f"Tarih:     {d['tarih']} ({d['gun']})")
    print(f"Corba:     {d['corba']}")
    print(f"Ana Yemek: {d['ana_yemek']}")
    print(f"Yan Yemek: {d['yan_yemek']}")
    print(f"Tatli:     {d['tatli']}")
    print(f"Salata:    {d['salata']}")
else:
    print("Bugunun menusu bulunamadi!")
db.close()
