"""
Modül 2: Yemek Fotoğrafından Tanıma + Besin Analizi
─────────────────────────────────────────────────────
Kullanıcının yüklediği fotoğraftan yemeği tanıyıp
besin değeri analizi yapan modül.

Kullanılan teknolojiler:
  - YOLOv8 Classification (ultralytics)
  - 102 sınıf Türk Yemekleri dataseti üzerinde fine-tuned model
  - SQLAlchemy — veritabanı sorgusu
  - Pillow — görüntü işleme
"""

import os
import sys
from pathlib import Path
from typing import Any
import numpy as np

# Proje kök dizinini path'e ekle
PROJE_KOK = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJE_KOK)

# ─── Sabitler ──────────────────────────────────────────────────────

# 102 Türk Yemekleri sınıf adlarından okunabilir Türkçe isimlere çeviri
# Anahtar: archive klasör adı (modelin sınıf adı), Değer: Türkçe ad
TURKISH_FOOD_MAP = {
    "adana-kebap": "Adana Kebap",
    "anne-koftesi": "Anne Köftesi",
    "armut": "Armut",
    "avokado": "Avokado",
    "ayran": "Ayran",
    "baklava": "Baklava",
    "beyaz-lahana-sarmasi": "Beyaz Lahana Sarması",
    "biber-dolma": "Biber Dolma",
    "brokoli": "Brokoli",
    "bruksel-lahanasi": "Brüksel Lahanası",
    "bulgur-pilavi": "Bulgur Pilavı",
    "cacik": "Cacık",
    "canak-enginar": "Çanak Enginar",
    "cay": "Çay",
    "cig-kofte": "Çiğ Köfte",
    "cilek": "Çilek",
    "cipura": "Çipura",
    "coban-salatasi": "Çoban Salatası",
    "domates": "Domates",
    "domates-corbasi": "Domates Çorbası",
    "dondurma": "Dondurma",
    "doner": "Döner",
    "ekmek": "Ekmek",
    "elma": "Elma",
    "erik": "Erik",
    "et-sote": "Et Sote",
    "hamsi-tava": "Hamsi Tava",
    "haslanmis-yumurta": "Haşlanmış Yumurta",
    "havuc": "Havuç",
    "hunkar-begendi": "Hünkar Beğendi",
    "icli-kofte": "İçli Köfte",
    "incir": "İncir",
    "iskender": "İskender",
    "ispanak-yemegi": "Ispanak Yemeği",
    "kabak-mucver": "Kabak Mücver",
    "kalburabasti": "Kalburabastı",
    "karnabahar": "Karnabahar",
    "karniyarik": "Karnıyarık",
    "karpuz": "Karpuz",
    "kavun": "Kavun",
    "kayisi": "Kayısı",
    "kazandibi": "Kazandibi",
    "kemal-pasa-tatlisi": "Kemal Paşa Tatlısı",
    "kiraz": "Kiraz",
    "kisir": "Kısır",
    "kivi": "Kivi",
    "kiymali-borek": "Kıymalı Börek",
    "kiymali-pide": "Kıymalı Pide",
    "kokorec": "Kokoreç",
    "lahmacun": "Lahmacun",
    "levrek": "Levrek",
    "lokma": "Lokma",
    "mango": "Mango",
    "manti": "Mantı",
    "menemen": "Menemen",
    "mercimek-corbasi": "Mercimek Çorbası",
    "mercimek-koftesi": "Mercimek Köftesi",
    "midye-dolma": "Midye Dolma",
    "midye-tava": "Midye Tava",
    "mumbar-dolmasi": "Mumbar Dolması",
    "muz": "Muz",
    "nar": "Nar",
    "omlet": "Omlet",
    "patates-kizartmasi": "Patates Kızartması",
    "patates-puresi": "Patates Püresi",
    "patates-salatasi": "Patates Salatası",
    "patlican-kebabi": "Patlıcan Kebabı",
    "peynirli-borek": "Peynirli Börek",
    "pilav": "Pilav",
    "pirasa": "Pırasa",
    "portakal": "Portakal",
    "sahlep": "Sahlep",
    "salatalik": "Salatalık",
    "salcali-makarna": "Salçalı Makarna",
    "sandvic": "Sandviç",
    "seftali": "Şeftali",
    "sehriye-corbasi": "Şehriye Çorbası",
    "siyah-zeytin": "Siyah Zeytin",
    "su-boregi": "Su Böreği",
    "sucuklu-yumurta": "Sucuklu Yumurta",
    "sulu-bamya-yemegi": "Sulu Bamya Yemeği",
    "sulu-barbunya-yemegi": "Sulu Barbunya Yemeği",
    "sulu-bezelye-yemegi": "Sulu Bezelye Yemeği",
    "sulu-kuru-fasulye-yemegi": "Sulu Kuru Fasulye Yemeği",
    "sulu-mercimek-yemegi": "Sulu Mercimek Yemeği",
    "sulu-nohut-yemegi": "Sulu Nohut Yemeği",
    "sulu-patates-yemegi": "Sulu Patates Yemeği",
    "sutlac": "Sütlaç",
    "tantuni": "Tantuni",
    "tarhana-corbasi": "Tarhana Çorbası",
    "tas-kebabi": "Tas Kebabı",
    "tavuk-sote": "Tavuk Sote",
    "tulumba-tatlisi": "Tulumba Tatlısı",
    "turk-kahvesi": "Türk Kahvesi",
    "tursu": "Turşu",
    "uzum": "Üzüm",
    "yaprak-sarma": "Yaprak Sarma",
    "yayla-corbasi": "Yayla Çorbası",
    "yesil-zeytin": "Yeşil Zeytin",
    "yogurt": "Yoğurt",
    "yogurtlu-makarna": "Yoğurtlu Makarna",
    "zeytinyagli-fasulye": "Zeytinyağlı Fasulye",
}

# Food101 sınıf adlarından okunabilir Türkçe isimlere çeviri
FOOD101_CLASS_MAP = {
    "apple_pie": "Elmalı Turta",
    "baby_back_ribs": "Kaburga",
    "baklava": "Baklava",
    "beef_carpaccio": "Karpaçyo",
    "beef_tartare": "Et Tartar",
    "beet_salad": "Pancar Salatası",
    "beignets": "Beignet (Kızartma Hamur)",
    "bibimbap": "Bibimbap",
    "bread_pudding": "Ekmek Pudingi",
    "breakfast_burrito": "Kahvaltı Burritosu",
    "bruschetta": "Bruschetta",
    "caesar_salad": "Sezar Salatası",
    "cannoli": "Cannoli",
    "caprese_salad": "Caprese Salatası",
    "carrot_cake": "Havuçlu Kek",
    "ceviche": "Ceviche",
    "cheese_plate": "Peynir Tabağı",
    "cheesecake": "Cheesecake",
    "chicken_curry": "Tavuk Köri",
    "chicken_quesadilla": "Tavuklu Quesadilla",
    "chicken_wings": "Tavuk Kanadı",
    "chocolate_cake": "Çikolatalı Kek",
    "chocolate_mousse": "Çikolatalı Mus",
    "churros": "Churros",
    "clam_chowder": "İstiridye Çorbası",
    "club_sandwich": "Kulüp Sandviç",
    "crab_cakes": "Yengeç Köftesi",
    "creme_brulee": "Krem Brüle",
    "croque_madame": "Croque Madame",
    "cup_cakes": "Cupcake",
    "deviled_eggs": "Şeytanın Yumurtası",
    "donuts": "Donut",
    "dumplings": "Mantı (Dumpling)",
    "edamame": "Edamame",
    "eggs_benedict": "Eggs Benedict",
    "escargots": "Salyangoz",
    "falafel": "Falafel",
    "filet_mignon": "Fileto",
    "fish_and_chips": "Fish & Chips",
    "foie_gras": "Kaz Ciğeri",
    "french_fries": "Patates Kızartması",
    "french_onion_soup": "Soğan Çorbası",
    "french_toast": "Fransız Tostu",
    "fried_calamari": "Kalamar Tava",
    "fried_rice": "Kızarmış Pilav",
    "frozen_yogurt": "Dondurulmuş Yoğurt",
    "garlic_bread": "Sarımsaklı Ekmek",
    "gnocchi": "Gnocchi",
    "greek_salad": "Yunan Salatası",
    "grilled_cheese_sandwich": "Izgara Peynirli Sandviç",
    "grilled_salmon": "Izgara Somon",
    "guacamole": "Guacamole",
    "gyoza": "Gyoza",
    "hamburger": "Hamburger",
    "hot_and_sour_soup": "Ekşili Acılı Çorba",
    "hot_dog": "Sosisli Sandviç",
    "huevos_rancheros": "Meksika Yumurtası",
    "hummus": "Humus",
    "ice_cream": "Dondurma",
    "lasagna": "Lazanya",
    "lobster_bisque": "Istakoz Çorbası",
    "lobster_roll_sandwich": "Istakoz Sandviç",
    "macaroni_and_cheese": "Makarna & Peynir",
    "macarons": "Makaron",
    "miso_soup": "Miso Çorbası",
    "mussels": "Midye",
    "nachos": "Nachos",
    "omelette": "Omlet",
    "onion_rings": "Soğan Halkası",
    "oysters": "İstiridye",
    "pad_thai": "Pad Thai",
    "paella": "Paella",
    "pancakes": "Pankek",
    "panna_cotta": "Panna Cotta",
    "peking_duck": "Pekin Ördeği",
    "pho": "Pho",
    "pizza": "Pizza",
    "pork_chop": "Pirzola",
    "poutine": "Poutine",
    "prime_rib": "Kaburga Et",
    "pulled_pork_sandwich": "Çekme Et Sandviç",
    "ramen": "Ramen",
    "ravioli": "Ravioli",
    "red_velvet_cake": "Red Velvet Kek",
    "risotto": "Risotto",
    "samosa": "Samosa",
    "sashimi": "Sashimi",
    "scallops": "Tarak (Deniz Tarağı)",
    "seaweed_salad": "Deniz Yosunu Salatası",
    "shrimp_and_grits": "Karidesli Mısır Lapası",
    "spaghetti_bolognese": "Bolonez Spagetti",
    "spaghetti_carbonara": "Carbonara Spagetti",
    "spring_rolls": "Sigara Böreği (Spring Roll)",
    "steak": "Biftek",
    "strawberry_shortcake": "Çilekli Pasta",
    "sushi": "Suşi",
    "tacos": "Taco",
    "takoyaki": "Takoyaki",
    "tiramisu": "Tiramisu",
    "tuna_tartare": "Ton Balığı Tartar",
    "waffles": "Waffle",
}

# Food101 besin değerleri (100g başına yaklaşık)
FOOD101_NUTRITION = {
    "apple_pie": {"kalori": 237, "protein": 2, "karbonhidrat": 34, "yag": 11},
    "baby_back_ribs": {"kalori": 250, "protein": 20, "karbonhidrat": 0, "yag": 18},
    "baklava": {"kalori": 330, "protein": 6, "karbonhidrat": 40, "yag": 18},
    "beef_carpaccio": {"kalori": 140, "protein": 20, "karbonhidrat": 1, "yag": 6},
    "beef_tartare": {"kalori": 170, "protein": 20, "karbonhidrat": 2, "yag": 9},
    "beet_salad": {"kalori": 70, "protein": 2, "karbonhidrat": 10, "yag": 3},
    "beignets": {"kalori": 330, "protein": 5, "karbonhidrat": 42, "yag": 16},
    "bibimbap": {"kalori": 150, "protein": 10, "karbonhidrat": 20, "yag": 4},
    "bread_pudding": {"kalori": 230, "protein": 5, "karbonhidrat": 35, "yag": 8},
    "breakfast_burrito": {"kalori": 200, "protein": 10, "karbonhidrat": 20, "yag": 9},
    "bruschetta": {"kalori": 170, "protein": 4, "karbonhidrat": 20, "yag": 8},
    "caesar_salad": {"kalori": 130, "protein": 6, "karbonhidrat": 8, "yag": 9},
    "cannoli": {"kalori": 310, "protein": 7, "karbonhidrat": 32, "yag": 18},
    "caprese_salad": {"kalori": 120, "protein": 7, "karbonhidrat": 4, "yag": 9},
    "carrot_cake": {"kalori": 320, "protein": 4, "karbonhidrat": 44, "yag": 15},
    "ceviche": {"kalori": 100, "protein": 15, "karbonhidrat": 6, "yag": 2},
    "cheese_plate": {"kalori": 350, "protein": 22, "karbonhidrat": 2, "yag": 28},
    "cheesecake": {"kalori": 320, "protein": 6, "karbonhidrat": 26, "yag": 22},
    "chicken_curry": {"kalori": 160, "protein": 14, "karbonhidrat": 8, "yag": 8},
    "chicken_quesadilla": {"kalori": 230, "protein": 14, "karbonhidrat": 18, "yag": 12},
    "chicken_wings": {"kalori": 290, "protein": 27, "karbonhidrat": 0, "yag": 19},
    "chocolate_cake": {"kalori": 370, "protein": 4, "karbonhidrat": 50, "yag": 18},
    "chocolate_mousse": {"kalori": 250, "protein": 4, "karbonhidrat": 26, "yag": 15},
    "churros": {"kalori": 310, "protein": 4, "karbonhidrat": 40, "yag": 15},
    "clam_chowder": {"kalori": 120, "protein": 5, "karbonhidrat": 12, "yag": 6},
    "club_sandwich": {"kalori": 240, "protein": 15, "karbonhidrat": 22, "yag": 10},
    "crab_cakes": {"kalori": 200, "protein": 12, "karbonhidrat": 10, "yag": 12},
    "creme_brulee": {"kalori": 280, "protein": 5, "karbonhidrat": 30, "yag": 16},
    "croque_madame": {"kalori": 350, "protein": 18, "karbonhidrat": 25, "yag": 20},
    "cup_cakes": {"kalori": 340, "protein": 3, "karbonhidrat": 48, "yag": 16},
    "deviled_eggs": {"kalori": 180, "protein": 10, "karbonhidrat": 2, "yag": 15},
    "donuts": {"kalori": 400, "protein": 5, "karbonhidrat": 50, "yag": 20},
    "dumplings": {"kalori": 200, "protein": 8, "karbonhidrat": 24, "yag": 8},
    "edamame": {"kalori": 120, "protein": 12, "karbonhidrat": 9, "yag": 5},
    "eggs_benedict": {"kalori": 250, "protein": 14, "karbonhidrat": 15, "yag": 16},
    "escargots": {"kalori": 170, "protein": 16, "karbonhidrat": 2, "yag": 10},
    "falafel": {"kalori": 330, "protein": 13, "karbonhidrat": 32, "yag": 18},
    "filet_mignon": {"kalori": 280, "protein": 26, "karbonhidrat": 0, "yag": 19},
    "fish_and_chips": {"kalori": 260, "protein": 14, "karbonhidrat": 24, "yag": 13},
    "foie_gras": {"kalori": 460, "protein": 11, "karbonhidrat": 4, "yag": 44},
    "french_fries": {"kalori": 310, "protein": 3, "karbonhidrat": 40, "yag": 15},
    "french_onion_soup": {"kalori": 90, "protein": 4, "karbonhidrat": 10, "yag": 4},
    "french_toast": {"kalori": 230, "protein": 7, "karbonhidrat": 28, "yag": 10},
    "fried_calamari": {"kalori": 250, "protein": 12, "karbonhidrat": 18, "yag": 14},
    "fried_rice": {"kalori": 180, "protein": 5, "karbonhidrat": 28, "yag": 5},
    "frozen_yogurt": {"kalori": 160, "protein": 4, "karbonhidrat": 28, "yag": 4},
    "garlic_bread": {"kalori": 300, "protein": 7, "karbonhidrat": 36, "yag": 14},
    "gnocchi": {"kalori": 180, "protein": 4, "karbonhidrat": 38, "yag": 1},
    "greek_salad": {"kalori": 100, "protein": 3, "karbonhidrat": 6, "yag": 8},
    "grilled_cheese_sandwich": {"kalori": 340, "protein": 13, "karbonhidrat": 28, "yag": 20},
    "grilled_salmon": {"kalori": 200, "protein": 25, "karbonhidrat": 0, "yag": 10},
    "guacamole": {"kalori": 160, "protein": 2, "karbonhidrat": 9, "yag": 15},
    "gyoza": {"kalori": 200, "protein": 8, "karbonhidrat": 22, "yag": 9},
    "hamburger": {"kalori": 260, "protein": 17, "karbonhidrat": 24, "yag": 11},
    "hot_and_sour_soup": {"kalori": 60, "protein": 4, "karbonhidrat": 6, "yag": 2},
    "hot_dog": {"kalori": 290, "protein": 10, "karbonhidrat": 24, "yag": 17},
    "huevos_rancheros": {"kalori": 180, "protein": 10, "karbonhidrat": 14, "yag": 10},
    "hummus": {"kalori": 170, "protein": 8, "karbonhidrat": 14, "yag": 10},
    "ice_cream": {"kalori": 210, "protein": 4, "karbonhidrat": 24, "yag": 11},
    "lasagna": {"kalori": 190, "protein": 11, "karbonhidrat": 18, "yag": 9},
    "lobster_bisque": {"kalori": 140, "protein": 6, "karbonhidrat": 10, "yag": 8},
    "lobster_roll_sandwich": {"kalori": 230, "protein": 16, "karbonhidrat": 20, "yag": 10},
    "macaroni_and_cheese": {"kalori": 310, "protein": 12, "karbonhidrat": 30, "yag": 16},
    "macarons": {"kalori": 400, "protein": 8, "karbonhidrat": 58, "yag": 16},
    "miso_soup": {"kalori": 40, "protein": 3, "karbonhidrat": 5, "yag": 1},
    "mussels": {"kalori": 170, "protein": 24, "karbonhidrat": 7, "yag": 4},
    "nachos": {"kalori": 340, "protein": 9, "karbonhidrat": 36, "yag": 18},
    "omelette": {"kalori": 150, "protein": 11, "karbonhidrat": 1, "yag": 12},
    "onion_rings": {"kalori": 330, "protein": 4, "karbonhidrat": 40, "yag": 17},
    "oysters": {"kalori": 80, "protein": 9, "karbonhidrat": 5, "yag": 2},
    "pad_thai": {"kalori": 180, "protein": 8, "karbonhidrat": 26, "yag": 5},
    "paella": {"kalori": 150, "protein": 10, "karbonhidrat": 20, "yag": 4},
    "pancakes": {"kalori": 230, "protein": 6, "karbonhidrat": 36, "yag": 7},
    "panna_cotta": {"kalori": 240, "protein": 3, "karbonhidrat": 22, "yag": 16},
    "peking_duck": {"kalori": 300, "protein": 18, "karbonhidrat": 8, "yag": 22},
    "pho": {"kalori": 90, "protein": 8, "karbonhidrat": 10, "yag": 2},
    "pizza": {"kalori": 266, "protein": 11, "karbonhidrat": 33, "yag": 10},
    "pork_chop": {"kalori": 250, "protein": 26, "karbonhidrat": 0, "yag": 15},
    "poutine": {"kalori": 320, "protein": 8, "karbonhidrat": 30, "yag": 19},
    "prime_rib": {"kalori": 300, "protein": 24, "karbonhidrat": 0, "yag": 22},
    "pulled_pork_sandwich": {"kalori": 240, "protein": 16, "karbonhidrat": 25, "yag": 9},
    "ramen": {"kalori": 130, "protein": 8, "karbonhidrat": 16, "yag": 4},
    "ravioli": {"kalori": 200, "protein": 8, "karbonhidrat": 28, "yag": 6},
    "red_velvet_cake": {"kalori": 350, "protein": 4, "karbonhidrat": 46, "yag": 18},
    "risotto": {"kalori": 170, "protein": 5, "karbonhidrat": 26, "yag": 5},
    "samosa": {"kalori": 260, "protein": 6, "karbonhidrat": 28, "yag": 14},
    "sashimi": {"kalori": 130, "protein": 26, "karbonhidrat": 0, "yag": 2},
    "scallops": {"kalori": 110, "protein": 20, "karbonhidrat": 3, "yag": 1},
    "seaweed_salad": {"kalori": 70, "protein": 2, "karbonhidrat": 8, "yag": 3},
    "shrimp_and_grits": {"kalori": 200, "protein": 12, "karbonhidrat": 22, "yag": 8},
    "spaghetti_bolognese": {"kalori": 180, "protein": 10, "karbonhidrat": 22, "yag": 6},
    "spaghetti_carbonara": {"kalori": 220, "protein": 10, "karbonhidrat": 25, "yag": 9},
    "spring_rolls": {"kalori": 200, "protein": 5, "karbonhidrat": 22, "yag": 10},
    "steak": {"kalori": 270, "protein": 26, "karbonhidrat": 0, "yag": 18},
    "strawberry_shortcake": {"kalori": 280, "protein": 3, "karbonhidrat": 38, "yag": 13},
    "sushi": {"kalori": 150, "protein": 6, "karbonhidrat": 22, "yag": 4},
    "tacos": {"kalori": 210, "protein": 10, "karbonhidrat": 20, "yag": 10},
    "takoyaki": {"kalori": 190, "protein": 8, "karbonhidrat": 22, "yag": 8},
    "tiramisu": {"kalori": 280, "protein": 5, "karbonhidrat": 30, "yag": 16},
    "tuna_tartare": {"kalori": 130, "protein": 22, "karbonhidrat": 2, "yag": 4},
    "waffles": {"kalori": 290, "protein": 7, "karbonhidrat": 38, "yag": 12},
}



# 102 Türk Yemekleri sınıflarının yaklaşık besin değerleri (100g başına)
# Bu değerler genel ortalamadır; DB'de bulunamazsa kullanılır
TURKISH_FOOD_NUTRITION = {
    "adana-kebap": {"kalori": 205, "protein": 17, "karbonhidrat": 2, "yag": 15},
    "anne-koftesi": {"kalori": 220, "protein": 15, "karbonhidrat": 8, "yag": 14},
    "armut": {"kalori": 57, "protein": 0.4, "karbonhidrat": 15, "yag": 0.1},
    "avokado": {"kalori": 160, "protein": 2, "karbonhidrat": 9, "yag": 15},
    "ayran": {"kalori": 36, "protein": 1.7, "karbonhidrat": 2.5, "yag": 1.8},
    "baklava": {"kalori": 330, "protein": 6, "karbonhidrat": 40, "yag": 18},
    "beyaz-lahana-sarmasi": {"kalori": 130, "protein": 8, "karbonhidrat": 10, "yag": 7},
    "biber-dolma": {"kalori": 140, "protein": 7, "karbonhidrat": 14, "yag": 6},
    "brokoli": {"kalori": 34, "protein": 2.8, "karbonhidrat": 7, "yag": 0.4},
    "bruksel-lahanasi": {"kalori": 43, "protein": 3.4, "karbonhidrat": 9, "yag": 0.3},
    "bulgur-pilavi": {"kalori": 150, "protein": 5, "karbonhidrat": 28, "yag": 3},
    "cacik": {"kalori": 60, "protein": 3, "karbonhidrat": 4, "yag": 3.5},
    "canak-enginar": {"kalori": 85, "protein": 3, "karbonhidrat": 10, "yag": 4},
    "cay": {"kalori": 1, "protein": 0, "karbonhidrat": 0.2, "yag": 0},
    "cig-kofte": {"kalori": 180, "protein": 6, "karbonhidrat": 30, "yag": 5},
    "cilek": {"kalori": 32, "protein": 0.7, "karbonhidrat": 8, "yag": 0.3},
    "cipura": {"kalori": 100, "protein": 20, "karbonhidrat": 0, "yag": 2},
    "coban-salatasi": {"kalori": 45, "protein": 1, "karbonhidrat": 6, "yag": 2},
    "domates": {"kalori": 18, "protein": 0.9, "karbonhidrat": 3.9, "yag": 0.2},
    "domates-corbasi": {"kalori": 55, "protein": 1.5, "karbonhidrat": 8, "yag": 2},
    "dondurma": {"kalori": 210, "protein": 4, "karbonhidrat": 24, "yag": 11},
    "doner": {"kalori": 220, "protein": 18, "karbonhidrat": 5, "yag": 14},
    "ekmek": {"kalori": 265, "protein": 9, "karbonhidrat": 49, "yag": 3},
    "elma": {"kalori": 52, "protein": 0.3, "karbonhidrat": 14, "yag": 0.2},
    "erik": {"kalori": 46, "protein": 0.7, "karbonhidrat": 11, "yag": 0.3},
    "et-sote": {"kalori": 180, "protein": 18, "karbonhidrat": 6, "yag": 10},
    "hamsi-tava": {"kalori": 190, "protein": 17, "karbonhidrat": 8, "yag": 10},
    "haslanmis-yumurta": {"kalori": 155, "protein": 13, "karbonhidrat": 1, "yag": 11},
    "havuc": {"kalori": 41, "protein": 0.9, "karbonhidrat": 10, "yag": 0.2},
    "hunkar-begendi": {"kalori": 170, "protein": 12, "karbonhidrat": 10, "yag": 9},
    "icli-kofte": {"kalori": 250, "protein": 10, "karbonhidrat": 28, "yag": 12},
    "incir": {"kalori": 74, "protein": 0.8, "karbonhidrat": 19, "yag": 0.3},
    "iskender": {"kalori": 230, "protein": 16, "karbonhidrat": 12, "yag": 14},
    "ispanak-yemegi": {"kalori": 90, "protein": 4, "karbonhidrat": 6, "yag": 5},
    "kabak-mucver": {"kalori": 170, "protein": 6, "karbonhidrat": 14, "yag": 10},
    "kalburabasti": {"kalori": 350, "protein": 5, "karbonhidrat": 45, "yag": 17},
    "karnabahar": {"kalori": 25, "protein": 2, "karbonhidrat": 5, "yag": 0.3},
    "karniyarik": {"kalori": 165, "protein": 8, "karbonhidrat": 10, "yag": 11},
    "karpuz": {"kalori": 30, "protein": 0.6, "karbonhidrat": 8, "yag": 0.2},
    "kavun": {"kalori": 34, "protein": 0.8, "karbonhidrat": 8, "yag": 0.2},
    "kayisi": {"kalori": 48, "protein": 1.4, "karbonhidrat": 11, "yag": 0.4},
    "kazandibi": {"kalori": 200, "protein": 5, "karbonhidrat": 30, "yag": 7},
    "kemal-pasa-tatlisi": {"kalori": 320, "protein": 6, "karbonhidrat": 42, "yag": 15},
    "kiraz": {"kalori": 50, "protein": 1, "karbonhidrat": 12, "yag": 0.3},
    "kisir": {"kalori": 160, "protein": 5, "karbonhidrat": 26, "yag": 5},
    "kivi": {"kalori": 61, "protein": 1.1, "karbonhidrat": 15, "yag": 0.5},
    "kiymali-borek": {"kalori": 280, "protein": 12, "karbonhidrat": 25, "yag": 15},
    "kiymali-pide": {"kalori": 250, "protein": 14, "karbonhidrat": 28, "yag": 10},
    "kokorec": {"kalori": 260, "protein": 18, "karbonhidrat": 8, "yag": 18},
    "lahmacun": {"kalori": 210, "protein": 10, "karbonhidrat": 28, "yag": 7},
    "levrek": {"kalori": 97, "protein": 18, "karbonhidrat": 0, "yag": 2},
    "lokma": {"kalori": 340, "protein": 4, "karbonhidrat": 48, "yag": 15},
    "mango": {"kalori": 60, "protein": 0.8, "karbonhidrat": 15, "yag": 0.4},
    "manti": {"kalori": 200, "protein": 10, "karbonhidrat": 24, "yag": 7},
    "menemen": {"kalori": 120, "protein": 7, "karbonhidrat": 6, "yag": 8},
    "mercimek-corbasi": {"kalori": 70, "protein": 4, "karbonhidrat": 12, "yag": 1},
    "mercimek-koftesi": {"kalori": 170, "protein": 7, "karbonhidrat": 28, "yag": 4},
    "midye-dolma": {"kalori": 180, "protein": 10, "karbonhidrat": 20, "yag": 7},
    "midye-tava": {"kalori": 220, "protein": 12, "karbonhidrat": 16, "yag": 12},
    "mumbar-dolmasi": {"kalori": 240, "protein": 14, "karbonhidrat": 18, "yag": 12},
    "muz": {"kalori": 89, "protein": 1.1, "karbonhidrat": 23, "yag": 0.3},
    "nar": {"kalori": 83, "protein": 1.7, "karbonhidrat": 19, "yag": 1.2},
    "omlet": {"kalori": 150, "protein": 11, "karbonhidrat": 1, "yag": 12},
    "patates-kizartmasi": {"kalori": 310, "protein": 3, "karbonhidrat": 40, "yag": 15},
    "patates-puresi": {"kalori": 115, "protein": 2, "karbonhidrat": 17, "yag": 5},
    "patates-salatasi": {"kalori": 140, "protein": 2, "karbonhidrat": 18, "yag": 7},
    "patlican-kebabi": {"kalori": 180, "protein": 12, "karbonhidrat": 8, "yag": 12},
    "peynirli-borek": {"kalori": 300, "protein": 10, "karbonhidrat": 26, "yag": 18},
    "pilav": {"kalori": 130, "protein": 3, "karbonhidrat": 28, "yag": 1},
    "pirasa": {"kalori": 61, "protein": 1.5, "karbonhidrat": 14, "yag": 0.3},
    "portakal": {"kalori": 47, "protein": 0.9, "karbonhidrat": 12, "yag": 0.1},
    "sahlep": {"kalori": 90, "protein": 3, "karbonhidrat": 16, "yag": 2},
    "salatalik": {"kalori": 15, "protein": 0.7, "karbonhidrat": 3.6, "yag": 0.1},
    "salcali-makarna": {"kalori": 180, "protein": 7, "karbonhidrat": 30, "yag": 4},
    "sandvic": {"kalori": 250, "protein": 12, "karbonhidrat": 28, "yag": 10},
    "seftali": {"kalori": 39, "protein": 0.9, "karbonhidrat": 10, "yag": 0.3},
    "sehriye-corbasi": {"kalori": 60, "protein": 2, "karbonhidrat": 10, "yag": 1.5},
    "siyah-zeytin": {"kalori": 115, "protein": 0.8, "karbonhidrat": 6, "yag": 11},
    "su-boregi": {"kalori": 260, "protein": 9, "karbonhidrat": 24, "yag": 14},
    "sucuklu-yumurta": {"kalori": 250, "protein": 14, "karbonhidrat": 2, "yag": 20},
    "sulu-bamya-yemegi": {"kalori": 80, "protein": 3, "karbonhidrat": 8, "yag": 4},
    "sulu-barbunya-yemegi": {"kalori": 110, "protein": 6, "karbonhidrat": 16, "yag": 3},
    "sulu-bezelye-yemegi": {"kalori": 100, "protein": 5, "karbonhidrat": 14, "yag": 3},
    "sulu-kuru-fasulye-yemegi": {"kalori": 120, "protein": 7, "karbonhidrat": 18, "yag": 3},
    "sulu-mercimek-yemegi": {"kalori": 110, "protein": 7, "karbonhidrat": 16, "yag": 2},
    "sulu-nohut-yemegi": {"kalori": 130, "protein": 7, "karbonhidrat": 20, "yag": 3},
    "sulu-patates-yemegi": {"kalori": 100, "protein": 3, "karbonhidrat": 14, "yag": 4},
    "sutlac": {"kalori": 130, "protein": 4, "karbonhidrat": 20, "yag": 4},
    "tantuni": {"kalori": 220, "protein": 16, "karbonhidrat": 12, "yag": 12},
    "tarhana-corbasi": {"kalori": 65, "protein": 3, "karbonhidrat": 10, "yag": 1.5},
    "tas-kebabi": {"kalori": 190, "protein": 16, "karbonhidrat": 6, "yag": 12},
    "tavuk-sote": {"kalori": 160, "protein": 18, "karbonhidrat": 6, "yag": 7},
    "tulumba-tatlisi": {"kalori": 360, "protein": 4, "karbonhidrat": 50, "yag": 17},
    "turk-kahvesi": {"kalori": 5, "protein": 0.3, "karbonhidrat": 0.7, "yag": 0},
    "tursu": {"kalori": 18, "protein": 0.5, "karbonhidrat": 4, "yag": 0.1},
    "uzum": {"kalori": 69, "protein": 0.7, "karbonhidrat": 18, "yag": 0.2},
    "yaprak-sarma": {"kalori": 160, "protein": 5, "karbonhidrat": 18, "yag": 8},
    "yayla-corbasi": {"kalori": 70, "protein": 3, "karbonhidrat": 8, "yag": 3},
    "yesil-zeytin": {"kalori": 145, "protein": 1, "karbonhidrat": 4, "yag": 15},
    "yogurt": {"kalori": 63, "protein": 5, "karbonhidrat": 4, "yag": 3.5},
    "yogurtlu-makarna": {"kalori": 190, "protein": 8, "karbonhidrat": 26, "yag": 6},
    "zeytinyagli-fasulye": {"kalori": 90, "protein": 3, "karbonhidrat": 10, "yag": 4},
}

# Eski isimle uyumluluk
FOOD101_TR_MAP = TURKISH_FOOD_MAP

# Birleşik sınıf haritası (her iki modelden de ada göre çeviri yapar)
COMBINED_FOOD_MAP = {**FOOD101_CLASS_MAP, **TURKISH_FOOD_MAP}
COMBINED_NUTRITION = {**FOOD101_NUTRITION, **TURKISH_FOOD_NUTRITION}


# ═══════════════════════════════════════════════════════════════════
# FONKSİYON: Model Yükleme
# ═══════════════════════════════════════════════════════════════════
def load_model(model_path: str | None = None) -> Any:
    """
    YOLOv8 classification modelini yükler.

    Args:
        model_path: Model dosyasının yolu (.pt).
            None ise varsayılan model yolu (config'den) kullanılır.

    Returns:
        YOLO model nesnesi.
    """
    from ultralytics import YOLO

    if model_path is None:
        # Önce birleşik modeli ara, sonra ayrı modelleri
        default_paths = [
            os.path.join(PROJE_KOK, "models_data", "combined_food_yolov8s_best.pt"),
            os.path.join(PROJE_KOK, "runs", "classify", "combined_food_yolov8s", "weights", "best.pt"),
            os.path.join(PROJE_KOK, "models_data", "turkish_food_yolov8s_best.pt"),
            os.path.join(PROJE_KOK, "runs", "classify", "turkish_food_yolov8s", "weights", "best.pt"),
            os.path.join(PROJE_KOK, "models_data", "food_yolov8s_best.pt"),
            os.path.join(PROJE_KOK, "runs", "classify", "food101_yolov8s", "weights", "best.pt"),
            os.path.join(PROJE_KOK, "models_data", "best.pt"),
        ]
        for path in default_paths:
            if os.path.exists(path):
                model_path = path
                break

        if model_path is None:
            print("⚠️ Eğitilmiş model bulunamadı. Genel yolov8s-cls.pt kullanılıyor.")
            print("   Daha iyi sonuçlar için: python scripts/train_yolo.py")
            model_path = "yolov8s-cls.pt"

    print(f"⏳ Yemek tanıma modeli yükleniyor: {model_path}")
    model = YOLO(model_path)
    print(f"✅ Model yüklendi: {model_path}")

    return model


def load_ensemble_models() -> list[Any]:
    """
    Hem Turkish Food hem de Food101 modellerini yükler (ensemble için).
    
    Returns:
        list[YOLO]: Yüklenmiş modellerin listesi.
    """
    from ultralytics import YOLO
    
    models = []
    model_paths = [
        # Turkish Food modeli
        os.path.join(PROJE_KOK, "models_data", "turkish_food_yolov8s_best.pt"),
        os.path.join(PROJE_KOK, "runs", "classify", "turkish_food_yolov8s", "weights", "best.pt"),
        # Food101 modeli
        os.path.join(PROJE_KOK, "models_data", "food_yolov8s_best.pt"),
        os.path.join(PROJE_KOK, "runs", "classify", "food101_yolov8s", "weights", "best.pt"),
    ]
    
    loaded_paths = set()
    for path in model_paths:
        if os.path.exists(path) and path not in loaded_paths:
            try:
                model = YOLO(path)
                models.append(model)
                loaded_paths.add(path)
                print(f"✅ Ensemble model yüklendi: {os.path.basename(path)}")
                # Her tip modelden sadece birini yükle
                if len(models) >= 2:
                    break
            except Exception as e:
                print(f"⚠️ Model yüklenemedi {path}: {e}")
    
    if not models:
        print("⚠️ Hiç model bulunamadı, varsayılan model kullanılıyor.")
        models.append(load_model())
    
    print(f"📦 Toplam {len(models)} model ensemble için hazır.")
    return models


# ═══════════════════════════════════════════════════════════════════
# FONKSİYON: Yemek Tanıma
# ═══════════════════════════════════════════════════════════════════
def recognize_food(
    model: Any,
    image_path: str,
    confidence_threshold: float = 0.10,
    top_k: int = 5,
    use_tta: bool = True,
) -> list[dict]:
    """
    Verilen fotoğraftan yemekleri tanıyıp sınıflandırır.
    YOLOv8 classification modeli kullanır.
    TTA (Test-Time Augmentation) desteği ile daha doğru sonuçlar.

    Args:
        model: Yüklü YOLO model nesnesi.
        image_path: Fotoğraf dosyasının yolu.
        confidence_threshold: Minimum güven eşiği (0.0 - 1.0).
        top_k: En olası kaç sonuç dönsün.
        use_tta: Test-Time Augmentation kullan.

    Returns:
        list[dict]: Tanınan yemekler listesi.
    """
    print(f"🔍 Yemek tanıma yapılıyor: {image_path}")

    # Dosya kontrolü
    if not Path(image_path).exists():
        print(f"❌ Dosya bulunamadı: {image_path}")
        return []

    if use_tta:
        # TTA: Orijinal + yatay çevrilmiş görüntüler ile tahmin yap
        return _recognize_with_tta(model, image_path, confidence_threshold, top_k)
    else:
        return _recognize_single(model, image_path, confidence_threshold, top_k)


def _recognize_single(
    model: Any,
    image_path: str,
    confidence_threshold: float = 0.10,
    top_k: int = 5,
) -> list[dict]:
    """
    Tek bir görüntü ile tahmin yapar (TTA olmadan).
    """
    # YOLO Classification inference
    results = model(image_path, verbose=False)

    if not results or len(results) == 0:
        print("⚠️ Sonuç alınamadı.")
        return []

    result = results[0]

    # Classification sonuçlarını işle
    probs = result.probs
    if probs is None:
        print("⚠️ Sınıflandırma olasılıkları alınamadı.")
        return []

    # Top-K sonuçları al
    top_indices = probs.top5  # Top-5 sınıf indexleri
    top_confs = probs.top5conf  # Top-5 güven skorları

    detections = []
    names = result.names  # Sınıf isimleri dict'i

    for i in range(min(top_k, len(top_indices))):
        class_idx = top_indices[i]
        confidence = float(top_confs[i])

        if confidence < confidence_threshold:
            continue

        class_name = names[class_idx]
        tr_name = COMBINED_FOOD_MAP.get(class_name, class_name.replace("-", " ").replace("_", " ").title())

        detections.append({
            "yemek_adi": class_name,
            "yemek_adi_tr": tr_name,
            "guven_skoru": round(confidence, 4),
        })

    print(f"✅ {len(detections)} yemek tespit edildi.")
    for d in detections:
        print(f"   🍽️ {d['yemek_adi_tr']} ({d['yemek_adi']}) — %{d['guven_skoru']*100:.1f}")

    return detections


def _recognize_with_tta(
    model: Any,
    image_path: str,
    confidence_threshold: float = 0.10,
    top_k: int = 5,
) -> list[dict]:
    """
    Test-Time Augmentation (TTA) ile tahmin yapar.
    Orijinal + yatay çevrilmiş görüntünün olasılıklarını ortalar.
    """
    try:
        from PIL import Image, ImageOps
    except ImportError:
        print("⚠️ PIL bulunamadı, TTA devre dışı.")
        return _recognize_single(model, image_path, confidence_threshold, top_k)

    try:
        img = Image.open(image_path)
    except Exception as e:
        print(f"⚠️ Görüntü açılamadı: {e}")
        return _recognize_single(model, image_path, confidence_threshold, top_k)

    # TTA augmentasyonları: orijinal + yatay flip
    tta_images = [
        img,                              # Orijinal
        ImageOps.mirror(img),             # Yatay çevrilmiş
    ]

    all_probs = []
    names = None

    for tta_img in tta_images:
        results = model(tta_img, verbose=False)
        if results and len(results) > 0:
            result = results[0]
            if result.probs is not None:
                # Tüm sınıfların olasılıklarını al
                probs_data = result.probs.data.cpu().numpy()
                all_probs.append(probs_data)
                if names is None:
                    names = result.names

    if not all_probs or names is None:
        print("⚠️ TTA sonuç alınamadı, normal tahmin yapılıyor.")
        return _recognize_single(model, image_path, confidence_threshold, top_k)

    # Olasılıkları ortala
    avg_probs = np.mean(all_probs, axis=0)

    # Top-K al
    top_indices = np.argsort(avg_probs)[::-1][:top_k]

    detections = []
    for idx in top_indices:
        confidence = float(avg_probs[idx])
        if confidence < confidence_threshold:
            continue

        class_name = names[idx]
        tr_name = COMBINED_FOOD_MAP.get(class_name, class_name.replace("-", " ").replace("_", " ").title())

        detections.append({
            "yemek_adi": class_name,
            "yemek_adi_tr": tr_name,
            "guven_skoru": round(confidence, 4),
        })

    print(f"✅ TTA ile {len(detections)} yemek tespit edildi.")
    for d in detections:
        print(f"   🍽️ {d['yemek_adi_tr']} ({d['yemek_adi']}) — %{d['guven_skoru']*100:.1f}")

    return detections


def recognize_food_ensemble(
    models: list[Any],
    image_path: str,
    confidence_threshold: float = 0.10,
    top_k: int = 5,
) -> list[dict]:
    """
    Birden fazla modelle ensemble tahmin yapar.
    Her modelin olasılıklarını ortalar.

    Args:
        models: YOLO model nesneleri listesi.
        image_path: Fotoğraf dosyasının yolu.
        confidence_threshold: Minimum güven eşiği.
        top_k: En olası kaç sonuç dönsün.

    Returns:
        list[dict]: Tanınan yemekler listesi.
    """
    if len(models) <= 1:
        return recognize_food(models[0], image_path, confidence_threshold, top_k)

    print(f"🔍 Ensemble tahmin yapılıyor ({len(models)} model): {image_path}")

    if not Path(image_path).exists():
        print(f"❌ Dosya bulunamadı: {image_path}")
        return []

    # Her modelden tahmin al
    all_results = []
    for i, model in enumerate(models):
        detections = recognize_food(
            model, image_path,
            confidence_threshold=0.01,  # Düşük eşik, sonra filtrele
            top_k=top_k * 2,
            use_tta=True,
        )
        all_results.append(detections)

    # Sonuçları birleştir - her yemek için ortalama güven skoru hesapla
    combined = {}
    for detections in all_results:
        for d in detections:
            key = d["yemek_adi"]
            if key not in combined:
                combined[key] = {
                    "yemek_adi": d["yemek_adi"],
                    "yemek_adi_tr": d["yemek_adi_tr"],
                    "scores": [],
                }
            combined[key]["scores"].append(d["guven_skoru"])

    # Ortalama skorları hesapla ve filtrele
    detections = []
    for key, data in combined.items():
        avg_score = sum(data["scores"]) / len(models)  # Eksik modelde 0 say
        if avg_score >= confidence_threshold:
            detections.append({
                "yemek_adi": data["yemek_adi"],
                "yemek_adi_tr": data["yemek_adi_tr"],
                "guven_skoru": round(avg_score, 4),
            })

    # Güven skoruna göre sırala
    detections.sort(key=lambda x: x["guven_skoru"], reverse=True)
    detections = detections[:top_k]

    print(f"✅ Ensemble: {len(detections)} yemek tespit edildi.")
    for d in detections:
        print(f"   🍽️ {d['yemek_adi_tr']} ({d['yemek_adi']}) — %{d['guven_skoru']*100:.1f}")

    return detections


# ═══════════════════════════════════════════════════════════════════
# FONKSİYON: Besin Değeri Sorgula
# ═══════════════════════════════════════════════════════════════════
def get_nutrition_info(yemek_adi: str, db_session=None) -> dict | None:
    """
    Yemek adına göre besin değeri bilgisini veritabanından
    veya sabit listeden getirir.

    Önce veritabanını sorgular (Türkçe yemek adı ile).
    Bulamazsa Türk Yemekleri sabit besin tablosuna bakar.

    Args:
        yemek_adi: Sınıf adı (ör: "adana-kebap") veya Türkçe ad.
        db_session: SQLAlchemy oturum nesnesi (opsiyonel).

    Returns:
        dict | None: Besin değerleri.
            {
                "ad": str,
                "kalori": float,
                "protein": float,
                "karbonhidrat": float,
                "yag": float,
                "kaynak": "veritabani" | "turk_yemekleri_tablo"
            }
    """
    print(f"🥗 Besin değeri sorgulanıyor: {yemek_adi}")

    # Türkçe adı bul (her iki modelden de)
    tr_name = COMBINED_FOOD_MAP.get(yemek_adi, yemek_adi.replace("-", " ").replace("_", " ").title())

    # 1. Veritabanında ara
    if db_session:
        try:
            from models import Yemek as YemekModel

            # Hem Food-101 adı hem Türkçe adla ara
            yemek = (
                db_session.query(YemekModel)
                .filter(
                    YemekModel.ad.ilike(f"%{tr_name}%")
                )
                .first()
            )

            if yemek:
                print(f"✅ DB'den bulundu: {yemek.ad}")
                return {
                    "ad": yemek.ad,
                    "kalori": yemek.kalori,
                    "protein": yemek.protein,
                    "karbonhidrat": yemek.karbonhidrat,
                    "yag": yemek.yag,
                    "kaynak": "veritabani",
                }
        except Exception as e:
            print(f"⚠️ Veritabanı hatası: {e}")

    # 2. Birleşik besin tablosundan al (Turkish Food + Food101)
    food_key = yemek_adi.lower().replace(" ", "-")
    nutrition = COMBINED_NUTRITION.get(food_key)
    # Food101 isimleri alt çizgili olabilir
    if not nutrition:
        food_key2 = yemek_adi.lower().replace(" ", "_")
        nutrition = COMBINED_NUTRITION.get(food_key2)
    # Orijinal adi ile de dene
    if not nutrition:
        nutrition = COMBINED_NUTRITION.get(yemek_adi)

    if nutrition:
        print(f"✅ Besin tablosundan bulundu: {tr_name}")
        return {
            "ad": tr_name,
            "kalori": nutrition["kalori"],
            "protein": nutrition["protein"],
            "karbonhidrat": nutrition["karbonhidrat"],
            "yag": nutrition["yag"],
            "kaynak": "besin_tablo",
        }

    print(f"⚠️ Besin değeri bulunamadı: {yemek_adi}")
    return None


# ═══════════════════════════════════════════════════════════════════
# FONKSİYON: Fotoğraftan Tam Analiz
# ═══════════════════════════════════════════════════════════════════
def analyze_food_photo(
    model: Any,
    image_path: str,
    db_session=None,
    confidence_threshold: float = 0.10,
    top_k: int = 5,
    use_tta: bool = True,
) -> dict:
    """
    Fotoğraftan yemek tanıma + besin değeri analizini
    birleştiren üst düzey fonksiyon.

    Args:
        model: Yüklü YOLO model nesnesi.
        image_path: Fotoğraf yolu.
        db_session: SQLAlchemy oturumu (opsiyonel).
        confidence_threshold: Minimum güven eşiği.
        top_k: En olası kaç sonuç dönsün.

    Returns:
        dict: {
            "taninan_yemekler": [
                {
                    "yemek_adi": str,
                    "yemek_adi_tr": str,
                    "guven_skoru": float,
                    "besin_degeri": {...} | None,
                },
                ...
            ],
            "en_olasi_yemek": {
                "yemek": str,
                "guven": float,
                "kalori": float,
                "protein": float,
                "karbonhidrat": float,
                "yag": float,
            },
        }
    """
    # Yemek tanıma (TTA ile daha doğru sonuçlar)
    taninan = recognize_food(
        model, image_path,
        confidence_threshold=confidence_threshold,
        top_k=top_k,
        use_tta=use_tta,
    )

    # Porsiyon tahmini
    porsiyon = estimate_portion_size(image_path)

    # Besin değerlerini ekle (porsiyon çarpanı ile)
    carpan = porsiyon.get("carpan", 1.0)
    for yemek in taninan:
        besin = get_nutrition_info(yemek["yemek_adi"], db_session)
        if besin and carpan != 1.0:
            besin = {
                **besin,
                "kalori": round(besin["kalori"] * carpan),
                "protein": round(besin["protein"] * carpan, 1),
                "karbonhidrat": round(besin["karbonhidrat"] * carpan, 1),
                "yag": round(besin["yag"] * carpan, 1),
            }
        yemek["besin_degeri"] = besin

    # En olası yemek özeti
    en_olasi = None
    if taninan:
        top = taninan[0]
        besin = top.get("besin_degeri") or {}
        en_olasi = {
            "yemek": top["yemek_adi_tr"],
            "yemek_en": top["yemek_adi"],
            "guven": top["guven_skoru"],
            "kalori": besin.get("kalori", 0),
            "protein": besin.get("protein", 0),
            "karbonhidrat": besin.get("karbonhidrat", 0),
            "yag": besin.get("yag", 0),
        }

    return {
        "taninan_yemekler": taninan,
        "en_olasi_yemek": en_olasi,
        "porsiyon": porsiyon,
    }


# ═══════════════════════════════════════════════════════════════════
# FONKSİYON: Porsiyon Tahmini
# ═══════════════════════════════════════════════════════════════════
def estimate_portion_size(image_path: str) -> dict:
    """
    Fotoğraftaki yemeğin kapladığı alana göre porsiyon boyutu tahmin eder.

    Yöntem:
    - Fotoğrafın merkez bölgesindeki renk yoğunluğu analiz edilir.
    - Yemek pikselleri (koyu olmayan, renkli alanlar) / toplam piksel oranı hesaplanır.
    - Oran → Küçük/Normal/Büyük porsiyon → Kalori çarpanı (0.6x / 1.0x / 1.4x).

    Args:
        image_path: Fotoğraf dosyası yolu.

    Returns:
        dict: {"boyut": str, "carpan": float, "oran": float}
    """
    try:
        from PIL import Image
        import numpy as np

        img = Image.open(image_path).convert("RGB")
        w, h = img.size

        # Merkez %70 bölge (kenar boşluklarını at)
        margin_x = int(w * 0.15)
        margin_y = int(h * 0.15)
        center = img.crop((margin_x, margin_y, w - margin_x, h - margin_y))

        arr = np.array(center, dtype=np.float32)

        # HSV'ye yakın analiz: yemek pikselleri genelde orta-yüksek satürasyon
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

        # "Yemek pikseli" tahmini: çok koyu (tabak kenarı) veya çok açık (beyaz tabak) değil
        brightness = (r + g + b) / 3
        food_mask = (brightness > 40) & (brightness < 230)

        # Renk varyansı (yemek renkli, tabak tekdüze)
        color_var = np.std(arr, axis=2)
        colorful_mask = color_var > 15

        food_pixels = np.sum(food_mask & colorful_mask)
        total_pixels = arr.shape[0] * arr.shape[1]

        ratio = food_pixels / max(total_pixels, 1)

        # Oran → porsiyon boyutu
        if ratio < 0.35:
            boyut = "Küçük"
            carpan = 0.6
        elif ratio < 0.65:
            boyut = "Normal"
            carpan = 1.0
        else:
            boyut = "Büyük"
            carpan = 1.4

        print(f"🍽️ Porsiyon tahmini: {boyut} (oran: {ratio:.2f}, çarpan: {carpan}x)")
        return {
            "boyut": boyut,
            "carpan": carpan,
            "oran": round(ratio, 2),
        }

    except Exception as e:
        print(f"⚠️ Porsiyon tahmini yapılamadı: {e}")
        return {"boyut": "Normal", "carpan": 1.0, "oran": 0.5}


# ═══════════════════════════════════════════════════════════════════
# FONKSİYON: Tepsi Tanıma (Grid-Based Multi-Food)
# ═══════════════════════════════════════════════════════════════════
def recognize_tray(
    model: Any,
    image_path: str,
    confidence_threshold: float = 0.15,
    grid_size: int = 2,
) -> list[dict]:
    """
    Fotoğrafı grid'lere bölerek birden fazla yemeği tanır.

    Args:
        model: Yüklü YOLO model nesnesi.
        image_path: Fotoğraf dosyası yolu.
        confidence_threshold: Minimum güven eşiği.
        grid_size: Grid boyutu (2=2x2, 3=3x3).

    Returns:
        list[dict]: Tanınan benzersiz yemekler listesi.
    """
    try:
        from PIL import Image
    except ImportError:
        print("⚠️ Pillow yüklü değil, tepsi tanıma yapılamıyor.")
        return []

    print(f"🍱 Tepsi tanıma yapılıyor ({grid_size}x{grid_size} grid): {image_path}")

    img = Image.open(image_path).convert("RGB")
    w, h = img.size

    cell_w = w // grid_size
    cell_h = h // grid_size

    all_detections = {}  # yemek_adi -> en yüksek skor

    import tempfile

    for row in range(grid_size):
        for col in range(grid_size):
            # Bölgeyi kes
            left = col * cell_w
            top = row * cell_h
            right = min(left + cell_w, w)
            bottom = min(top + cell_h, h)

            crop = img.crop((left, top, right, bottom))

            # Geçici dosyaya kaydet ve tanı
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                crop.save(tmp.name)
                tmp_path = tmp.name

            try:
                results = model(tmp_path, verbose=False)
                for result in results:
                    if result.probs is not None:
                        names = result.names
                        probs = result.probs.data.cpu().numpy()
                        top_idx = probs.argmax()
                        confidence = float(probs[top_idx])

                        if confidence >= confidence_threshold:
                            class_name = names[top_idx]
                            tr_name = COMBINED_FOOD_MAP.get(
                                class_name,
                                class_name.replace("-", " ").replace("_", " ").title()
                            )

                            # En yüksek güveni tut
                            if class_name not in all_detections or confidence > all_detections[class_name]["guven_skoru"]:
                                all_detections[class_name] = {
                                    "yemek_adi": class_name,
                                    "yemek_adi_tr": tr_name,
                                    "guven_skoru": round(confidence, 4),
                                    "bolge": f"Satır {row+1}, Sütun {col+1}",
                                }
            finally:
                try:
                    os.remove(tmp_path)
                except:
                    pass

    # Tüm fotoğrafı da bir kez tara (genel yemek tespiti)
    results = model(image_path, verbose=False)
    for result in results:
        if result.probs is not None:
            names = result.names
            probs = result.probs.data.cpu().numpy()
            top3 = probs.argsort()[::-1][:3]
            for idx in top3:
                confidence = float(probs[idx])
                if confidence >= confidence_threshold:
                    class_name = names[idx]
                    tr_name = COMBINED_FOOD_MAP.get(
                        class_name,
                        class_name.replace("-", " ").replace("_", " ").title()
                    )
                    if class_name not in all_detections or confidence > all_detections[class_name]["guven_skoru"]:
                        all_detections[class_name] = {
                            "yemek_adi": class_name,
                            "yemek_adi_tr": tr_name,
                            "guven_skoru": round(confidence, 4),
                            "bolge": "Genel",
                        }

    # Güven skoruna göre sırala
    detections = sorted(all_detections.values(), key=lambda x: x["guven_skoru"], reverse=True)

    print(f"✅ Tepsi: {len(detections)} farklı yemek tespit edildi.")
    for d in detections:
        print(f"   🍽️ {d['yemek_adi_tr']} ({d['yemek_adi']}) — %{d['guven_skoru']*100:.1f} [{d['bolge']}]")

    return detections


def analyze_tray_photo(
    model: Any,
    image_path: str,
    db_session=None,
    confidence_threshold: float = 0.15,
) -> dict:
    """
    Tepsi fotoğrafından çoklu yemek tanıma + toplam besin analizi.

    Returns:
        dict: {
            "taninan_yemekler": [...],
            "toplam_besin": {"kalori": ..., "protein": ..., ...},
            "yemek_sayisi": int,
        }
    """
    detections = recognize_tray(model, image_path, confidence_threshold)

    toplam = {"kalori": 0, "protein": 0, "karbonhidrat": 0, "yag": 0}

    for yemek in detections:
        besin = get_nutrition_info(yemek["yemek_adi"], db_session)
        yemek["besin_degeri"] = besin
        if besin:
            toplam["kalori"] += besin.get("kalori", 0)
            toplam["protein"] += besin.get("protein", 0)
            toplam["karbonhidrat"] += besin.get("karbonhidrat", 0)
            toplam["yag"] += besin.get("yag", 0)

    return {
        "taninan_yemekler": detections,
        "toplam_besin": {
            "kalori": round(toplam["kalori"]),
            "protein": round(toplam["protein"], 1),
            "karbonhidrat": round(toplam["karbonhidrat"], 1),
            "yag": round(toplam["yag"], 1),
        },
        "yemek_sayisi": len(detections),
    }
