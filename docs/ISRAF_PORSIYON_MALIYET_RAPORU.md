# İsraf, Porsiyon ve Maliyet Hesaplama Raporu

Güncelleme tarihi: 10 Mayıs 2026

Bu rapor, proje dosyaları yeniden taranarak hazırlanmıştır. Önceki rapordan sonra projede yapılan değişiklikler dikkate alınmıştır. Raporun amacı, uygulamada israfın nasıl hesaplandığını, ML modellerinin nerede kullanıldığını, porsiyon önerisinin nasıl üretildiğini, maliyetin nasıl hesaplandığını ve fotoğraf/resim yükleyerek yemek tanıma özelliğinin mevcut durumda projede aktif olup olmadığını açıklamaktır.

## 1. Kısa Sonuç

Projede israfın temel ve resmi hesabı doğrudan üretim loglarından yapılır. Bir yemek için üretilen porsiyon ve kalan porsiyon girildiğinde:

```text
tüketilen porsiyon = üretilen porsiyon - kalan porsiyon
tüketim oranı (%) = tüketilen porsiyon / üretilen porsiyon * 100
israf oranı (%) = kalan porsiyon / üretilen porsiyon * 100
```

Bu hesap ML modeliyle yapılmaz. Kullanıcıdan veya sistemden gelen gerçek üretim ve kalan porsiyon kayıtlarına dayanır.

Ancak projede ML modeli vardır ve israfı tahmin etmek için kullanılır. Model, geçmiş üretim kayıtları, kullanıcı puanları, yemek kategorisi, gün, ay, geçmiş israf, popülerlik ve benzeri özelliklerden beklenen israf oranını tahmin eder. Bu tahmin özellikle üretim planlama ve porsiyon önerisi tarafında karar destek girdisi olarak kullanılır.

Porsiyon önerisi önceki açıklamadaki gibi tamamen kural tabanlı değildir. Güncel kodda porsiyon önerisi ML destekli hibrit bir yöntemle hesaplanmaktadır. Sistem hem son 60 günlük tüketim geçmişini hem tüketim belirsizliğini hem trendi hem öğrenci puanlarını hem de ML modelinin tahmin ettiği israf oranını birlikte kullanır.

Maliyet hesabı ise temelde porsiyon başı maliyet ile kalan porsiyonun çarpılmasıdır. Bazı ekranlarda hızlı analiz için sabit varsayılan porsiyon maliyeti kullanılırken, maliyet API tarafında yemek bazlı `birim_maliyet` değeri veya kategori varsayılanı kullanılır.

Fotoğraf çekip veya resim yükleyip yemek tanıma özelliği aktif uygulama akışından kaldırılmış görünmektedir. Backend route, aktif sayfa ve mobil ekran tarafında yemek tanıma akışı bulunmamaktadır. Fakat YOLO model dosyaları, eğitim scriptleri ve bazı dokümantasyon/bağımlılık kalıntıları projede hala durmaktadır.

## 2. Uygulamanın Genel Çalışma Mantığı

Uygulama yemekhane üretim sürecini birkaç ana veri akışı üzerinden yönetir:

1. Menü ve yemekler tanımlanır.
2. Öğrenciler menüleri puanlar.
3. Gün sonunda veya servis sonrasında üretim logu girilir.
4. Üretim logundan gerçek tüketim ve gerçek israf oranı hesaplanır.
5. Geçmiş üretim, puanlama ve menü verileri ML modelinin eğitiminde kullanılır.
6. Eğitimli model, gelecek günler için beklenen israf oranını tahmin eder.
7. Üretim planlama modülü, son 60 günlük tüketim geçmişini ve ML tahminini kullanarak önerilen porsiyon sayısını hesaplar.
8. Maliyet ekranları, kalan porsiyonu porsiyon maliyetiyle çarparak parasal kaybı hesaplar.
9. Yönetici ekranları ve API'ler bu sonuçları raporlar.

Bu yapı içinde model her şeyi yapan merkezi bir karar verici değildir. Bazı hesaplar doğrudan matematiksel formüllerle yapılır, bazı kararlar kural tabanlıdır, bazı tahminler ise ML modelinden gelir.

## 3. Veri Modeli ve Kullanılan Ana Alanlar

Projede israf ve porsiyon hesabı açısından en önemli tablolar şunlardır.

### 3.1. Yemek

`Yemek` modeli yemek adını, kategorisini ve maliyet bilgisini taşır. Özellikle `birim_maliyet` alanı önemlidir.

```text
birim_maliyet: Porsiyon başı maliyet, TL/porsiyon
```

Bu alan doluysa maliyet hesabında öncelikle bu değer kullanılır. Boşsa kategoriye göre varsayılan maliyet alınır.

### 3.2. Menü Puanlama

`MenuPuanlama` modeli öğrencilerin yemeklere verdiği puanları içerir. Bu kayıtlar:

```text
puan
israf_self_report
yorum
tarih
```

alanları üzerinden hem popülerlik hem de israf tahmini için kullanılır.

`israf_self_report` alanı öğrencinin kendi bildirdiği tabak israfı seviyesidir. Bu alan gerçek üretim israfının yerine geçmez, fakat model için yardımcı sinyal olabilir.

### 3.3. Üretim Logu

`UretimLog` modeli gerçek üretim ve kalan porsiyon bilgilerini içerir. İsraf hesabının ana kaynağı bu tablodur.

```text
uretilen_porsiyon
kalan_porsiyon
tuketim_orani
israf_orani
tartilan_israf_kg
tartilan_israf_kaynagi
```

`uretilen_porsiyon` ve `kalan_porsiyon` girildiğinde `tuketim_orani` ve `israf_orani` hesaplanır. Bu iki oran model tahmini değildir, doğrudan gerçek kayıttan türetilir.

## 4. İsraf Nasıl Hesaplanıyor?

İsraf hesabının ana formülü `consumption_tracker.py` içinde uygulanır.

```text
tuketim_orani = ((uretilen - kalan) / uretilen) * 100
israf_orani = (kalan / uretilen) * 100
```

Örnek:

```text
Üretilen porsiyon: 100
Kalan porsiyon: 18
Tüketilen porsiyon: 82
Tüketim oranı: %82
İsraf oranı: %18
```

Bu örnekte model hiçbir hesap yapmaz. Hesap tamamen üretim ve kalan porsiyon verisine dayanır.

Sistem veri doğrulaması da yapar:

```text
üretilen porsiyon > 0 olmalı
kalan porsiyon >= 0 olmalı
kalan porsiyon üretilen porsiyondan büyük olamaz
```

Bu kurallar, hatalı veya fiziksel olarak mümkün olmayan kayıtların sisteme girmesini engeller.

## 5. ML Modeli Ne Yapıyor?

ML modeli gerçek israfı hesaplamaz. Gerçek israf zaten üretim logundan hesaplanır. Modelin görevi, geçmiş verilere bakarak gelecek veya belirli koşullar için beklenen israf oranını tahmin etmektir.

Güncel projede `waste_analyzer.py` içinde ML tabanlı israf tahmin yapısı bulunmaktadır. Eğitim sonucu dosyaları `models_data` klasöründe tutulmaktadır.

Mevcut model metrik dosyasına göre:

```text
Model tipi: Ensemble(RF+GBR+XGBoost)
Örnek sayısı: 816
MAE CV: 4.146
RMSE CV: 4.91
R2 CV: 0.3
Doğrulama: TimeSeriesSplit
Eğitim zamanı: 2026-05-10T20:13:19Z
```

Bu değerler modelin ortalama mutlak hata seviyesinin yaklaşık 4.1 puan olduğunu gösterir. Örneğin model %20 israf tahmin ettiyse gerçek değer yaklaşık birkaç puan yukarı veya aşağı sapabilir. `R2 = 0.3` değeri modelin faydalı sinyal yakaladığını, ancak tek başına kusursuz karar verici olmadığını gösterir. Bu nedenle üretim planlama kodu modeli tek kaynak olarak kullanmaz; geçmiş tüketim ve güvenlik payı ile birlikte hibrit şekilde kullanır.

### 5.1. Modelin Kullandığı Özellikler

Modelin kullandığı özellikler arasında şunlar vardır:

```text
yemek_adi
kategori
gun_hafta
ay
uretilen_porsiyon
rating_avg
rating_count
onceki_hafta_israf
populerlik_skoru
mevsim
hafta_ici_mi
son_3_gun_ort_israf
kategori_ort_israf
rating_std
menu_cesitlilik
ogrenci_sayisi_tahmini
menu_cekiciligi
gun_tipi
onceki_gun_israf
self_report_avg
```

Bu alanlar modelin sadece yemek adından karar vermediğini gösterir. Model, yemek adıyla birlikte tarihsel tüketim, puanlama davranışı, takvim bilgisi ve geçmiş israf gibi sinyalleri beraber kullanır.

### 5.2. En Önemli Model Sinyalleri

Mevcut feature importance dosyasında en güçlü sinyal `rating_avg` olarak görünmektedir. Yani öğrencilerin yemeğe verdiği ortalama puan model açısından çok etkili bir girdidir.

Öne çıkan sinyaller:

```text
rating_avg
uretilen_porsiyon
rating_std
menu_cekiciligi
onceki_gun_israf
son_3_gun_ort_israf
populerlik_skoru
ay
rating_count
gun_hafta
self_report_avg
kategori_ort_israf
```

Bu da uygulamadaki mantığı destekler: düşük puan alan, geçmişte çok kalan veya benzer kategoride yüksek israf üreten yemekler için model daha yüksek israf riski tahmin edebilir.

### 5.3. Model Yoksa Ne Oluyor?

Model her zaman kullanılmayabilir. Kodda fallback mantığı vardır. Sistem sırayla şunları dener:

1. Eğitimli ML modeli varsa ML tahmini kullanılır.
2. ML kullanılamıyorsa gerçek üretim geçmişindeki ortalama israf oranı kullanılır.
3. O da yoksa öğrenci puanına göre kural tabanlı tahmin yapılır.
4. Hiç veri yoksa belirsiz/varsayılan sonuç üretilir.

Puan tabanlı kural mantığı kabaca şöyledir:

```text
1 puan -> çok yüksek israf riski
2 puan -> yüksek israf riski
3 puan -> orta israf riski
4 puan -> düşük israf riski
5 puan -> çok düşük israf riski
```

Bu fallback yapısı önemlidir çünkü proje tamamen modele bağımlı değildir.

## 6. Porsiyon Önerisi Model mi Yapıyor?

Kısa cevap: Güncel projede porsiyon önerisini tek başına model yapmıyor, ama ML modeli porsiyon önerisine doğrudan etki ediyor.

Önceki açıklamada porsiyon önerisinin doğrudan ML modeliyle değil, kural tabanlı bir planlama formülüyle hesaplandığı yazılmıştı. Bu açıklama artık güncel kodu tam karşılamıyor. `production_planner.py` dosyası değişmiş ve modül artık kendisini `ML-Destekli Hibrit Porsiyon Önerisi` olarak tanımlıyor.

Yani doğru güncel açıklama şu olmalıdır:

```text
Porsiyon önerisi ML destekli hibrit bir hesaplama ile yapılır.
ML modeli beklenen israf oranını tahmin eder.
Son 60 günlük tüketim geçmişi gerçek talep tabanını oluşturur.
Tüketim standart sapması güvenlik payı olarak eklenir.
Trend ve öğrenci puanı karar destek sinyali olarak kullanılır.
Son porsiyon önerisi, hem talep tabanını hem ML kaynaklı azaltma sinyalini birlikte dikkate alır.
```

Bu nedenle "model mi yapıyor?" sorusunun net cevabı şudur:

```text
Model, önerilen porsiyon sayısını doğrudan tek başına üretmez.
Model beklenen israf oranını tahmin eder.
Porsiyon sayısını üretim planlama formülü hesaplar.
Bu formül ML tahminini de kullandığı için sonuç ML desteklidir.
```

## 7. Porsiyon Önerisi Güncel Kodda Nasıl Hesaplanıyor?

Porsiyon önerisi `production_planner.py` içinde `get_dish_recommendation` fonksiyonuyla hesaplanır.

### 7.1. Kullanılan Veri Aralığı

Sistem ilgili yemek için son 60 günlük üretim kayıtlarını alır.

```text
geçmiş aralık = son 60 gün
```

Bu kayıtlar üzerinden:

```text
ortalama tüketim
ortalama üretim
ortalama kalan porsiyon
ortalama israf oranı
tüketim standart sapması
trend
öğrenci puan ortalaması
toplam oy sayısı
```

hesaplanır.

### 7.2. Ortalama Tüketim

Her geçmiş kayıt için tüketilen porsiyon bulunur:

```text
tüketilen = üretilen_porsiyon - kalan_porsiyon
```

Sonra ortalama tüketim hesaplanır:

```text
D = son 60 gündeki ortalama tüketilen porsiyon
```

Bu değer gerçek talep tabanıdır. Örneğin son 60 günde bu yemekten ortalama 180 porsiyon tüketildiyse, sistemin başlangıç talep tahmini 180 civarındadır.

### 7.3. Güvenlik Payı

Kodda güvenlik seviyesi için:

```text
SERVICE_LEVEL_Z = 1.28
```

kullanılır. Bu yaklaşık %90 servis seviyesi anlamına gelir.

Tüketim standart sapması `sigma` ile gösterilirse:

```text
güvenlik payı = 1.28 * sigma
talep tabanı = D + 1.28 * sigma
```

Örnek:

```text
ortalama tüketim = 180
tüketim standart sapması = 20
güvenlik payı = 1.28 * 20 = 25.6
talep tabanı = 205.6
```

Bu durumda sadece ortalamaya bakılsaydı 180 porsiyon üretilebilirdi. Fakat talep günlük olarak değiştiği için sistem yaklaşık 206 porsiyonluk bir taban öneri oluşturur.

### 7.4. Trend Etkisi

Son kayıtlar önceki kayıtlarla karşılaştırılır.

```text
son 3 kayıt ortalaması
önceki kayıtların ortalaması
```

Son 3 kayıtta tüketim önceki ortalamaya göre %10'dan fazla artmışsa trend artış kabul edilir. %10'dan fazla düşmüşse trend azalış kabul edilir.

Kodda trend etkisi:

```text
talep artıyorsa talep tabanı * 1.05
talep düşüyorsa talep tabanı * 0.95
trend sabitse değişiklik yok
```

Bu, trendin porsiyonu tamamen belirlemediğini ama küçük bir düzeltme yaptığını gösterir.

### 7.5. Öğrenci Puanı Etkisi

Öğrenci puanı iki yerde etkilidir:

1. ML modelinin tahmin girdisi olarak kullanılır.
2. ML modeli yoksa kural tabanlı israf tahmininde kullanılır.

Kodda puan yorumu şu şekilde sınıflandırılır:

```text
puan < 2.5 -> düşük puan, talep azalabilir
puan < 3.5 -> orta puan
puan >= 3.5 -> iyi puan
```

Güncel porsiyon formülünde puan doğrudan "şu kadar azalt" diye tek başına uygulanmaz. Daha çok ML tahmininin ve açıklama metninin içinde etkili olur.

### 7.6. ML İsraf Tahmini

Üretim planlama fonksiyonu `waste_analyzer.estimate_waste_ratio` fonksiyonunu çağırır.

Bu fonksiyon yemekte beklenen israf oranını yüzde olarak döndürür.

```text
w_pred = ML veya fallback ile tahmin edilen beklenen israf oranı
```

Kodda hedef israf oranı:

```text
HEDEF_ISRAF_ORANI = 0.10
```

Yani hedef %10 israftır.

Tahmin edilen israf hedefin üzerindeyse sistem üretim azaltma sinyali üretir.

```text
israf_farkı = max(0, w_pred - 0.10)
```

Örnek:

```text
ML tahmini = %25 israf
hedef = %10
fark = %15
```

Bu durumda sistem geçmiş ortalama üretimden %15 azaltma sinyali çıkarır.

### 7.7. Hibrit Porsiyon Formülü

Kodun döndürdüğü güncel formül:

```text
P = max(D + z*sigma, P_geçmiş * (1 - max(0, w_pred - %10)))
```

Kodun uyguladığı anlam daha açık şekilde şöyledir:

```text
talep_tabanı = ortalama_tüketim + 1.28 * tüketim_standart_sapması
ml_oneri = ortalama_üretim * (1 - max(0, tahmini_israf - hedef_israf))
ham_oneri = max(talep_tabanı, ml_oneri)
```

Sonra alt ve üst sınır uygulanır:

```text
alt sınır = ortalama_üretim * 0.60
üst sınır = ortalama_üretim * 1.50
öneri = alt sınır ile üst sınır arasına sıkıştırılmış ham_oneri
```

Son değer tam sayıya yuvarlanır.

Bu tasarımın amacı şudur:

```text
ML modeli yüksek israf bekliyorsa gereksiz üretimi azaltmak ister.
Fakat talep tabanı daha yüksekse sistem öğrenciyi yemeksiz bırakmamak için talep tabanının altına inmez.
Bu yüzden max(...) kullanılır.
```

### 7.8. Örnek Porsiyon Hesabı

Varsayım:

```text
son 60 gün ortalama üretim = 240 porsiyon
son 60 gün ortalama tüketim = 190 porsiyon
tüketim standart sapması = 20
ML israf tahmini = %25
hedef israf = %10
```

Talep tabanı:

```text
190 + 1.28 * 20 = 215.6
```

ML azaltma sinyali:

```text
israf farkı = 0.25 - 0.10 = 0.15
ml_oneri = 240 * (1 - 0.15) = 204
```

Hibrit karar:

```text
ham_oneri = max(215.6, 204) = 215.6
önerilen porsiyon = 216
```

Bu örnekte model azaltma sinyali vermiştir, fakat talep belirsizliği nedeniyle sistem 204'e kadar düşmemiştir. Sonuç, hem israfı azaltmaya hem de talebi karşılamaya çalışan dengeli bir öneridir.

### 7.9. Güven Seviyesi

Porsiyon önerisi güven seviyesi de döndürür.

```text
kayıt sayısı >= 10 ve kaynak ML ise -> yüksek güven
kayıt sayısı >= 5 ise -> orta güven
diğer durumlarda -> düşük güven
```

Bu, aynı yemeğe ait geçmiş veri azsa sistemin önerisini daha temkinli gösterdiği anlamına gelir.

## 8. Porsiyon Önerisi Neden İsrafı Etkiler?

İsraf oranı kalan porsiyon üzerinden hesaplandığı için üretim miktarı doğrudan israfı etkiler.

Örnek:

```text
Talep 180 porsiyon
Üretim 250 porsiyon
Kalan 70 porsiyon
İsraf oranı = 70 / 250 = %28
```

Aynı talepte üretim daha doğru ayarlanırsa:

```text
Talep 180 porsiyon
Üretim 205 porsiyon
Kalan 25 porsiyon
İsraf oranı = 25 / 205 = %12.2
```

Bu nedenle porsiyon önerisi israfı düşürmenin ana mekanizmalarından biridir. Modelin görevi burada "bu yemek hangi koşulda ne kadar riskli" sinyalini vermektir. Formül ise bu sinyali üretim miktarına çevirir.

## 9. Maliyet Nasıl Hesaplanıyor?

Projede maliyet hesabı birkaç katmanda yapılmaktadır. Temel mantık aynıdır:

```text
israf maliyeti = kalan porsiyon * porsiyon başı maliyet
```

### 9.1. Maliyet API Hesabı

`maliyet.py` tarafında öncelik sırası şöyledir:

1. Yemek için `birim_maliyet` değeri girilmişse bu değer kullanılır.
2. Girilmemişse kategori varsayılan maliyeti kullanılır.

Varsayılan kategori maliyetleri:

```text
çorba: 15 TL
ana yemek: 35 TL
yan yemek: 10 TL
tatlı: 20 TL
salata: 12 TL
içecek: 8 TL
```

Kayıp hesaplama:

```text
kayıp TL = kalan_porsiyon * birim_maliyet
```

Örnek:

```text
Yemek: ana yemek
Birim maliyet: 35 TL
Kalan porsiyon: 40
İsraf maliyeti = 40 * 35 = 1400 TL
```

### 9.2. Analytics Hızlı Maliyet Hesabı

`analytics.py` içindeki bazı endpointlerde hızlı analiz için sorgu parametresi kullanılır:

```text
porsiyon_maliyet_tl = 35.0
```

Bu durumda:

```text
israf_maliyeti = toplam_kalan_porsiyon * 35
toplam_uretim_maliyeti = toplam_uretilen_porsiyon * 35
```

Ayrıca AI tasarruf potansiyeli yaklaşık olarak:

```text
ai_tasarruf_potansiyeli = israf_maliyeti * 0.30
```

şeklinde hesaplanır.

Bu değer gerçek garanti tasarruf değildir. Raporlama amaçlı potansiyel tasarruf varsayımıdır.

### 9.3. Menü Optimizasyonu Maliyet Hesabı

`menu_optimizer.py` içinde menü seçimi için ayrı kategori maliyetleri vardır:

```text
çorba: 8 TL
ana yemek: 25 TL
yan yemek: 10 TL
tatlı: 12 TL
salata: 7 TL
```

Günlük bütçe hedefi:

```text
65 TL
```

Menü optimizasyonunda maliyet, tek başına toplam kaybı hesaplamak için değil, menü seçim skorunun bir bileşeni olarak kullanılır.

## 10. Maliyet İsrafı Nasıl Etkiliyor?

Maliyet israf oranını doğrudan değiştirmez. İsraf oranı fiziksel olarak kalan porsiyona bağlıdır. Fakat maliyet, hangi israfın daha kritik olduğunu gösterir.

Örnek:

```text
Çorba kalan: 40 porsiyon
Çorba birim maliyet: 15 TL
Kayıp: 600 TL

Ana yemek kalan: 40 porsiyon
Ana yemek birim maliyet: 35 TL
Kayıp: 1400 TL
```

İki yemekte kalan porsiyon aynı olsa bile ana yemeğin finansal kaybı daha yüksektir. Bu nedenle sistemde maliyet, israf önceliklendirmesi için önemlidir.

Doğru üretim planlama hem israf oranını hem de mali kaybı azaltır:

```text
daha az gereksiz üretim -> daha az kalan porsiyon
daha az kalan porsiyon -> daha düşük israf oranı
daha düşük kalan porsiyon -> daha düşük mali kayıp
```

## 11. Menü Optimizasyonu Nasıl Çalışıyor?

Menü optimizasyon modülü yemekleri sadece popülerliğe göre seçmez. Çok hedefli bir skor kullanır.

Güncel ağırlıklar:

```text
popülerlik: 0.35
israf: 0.30
beslenme: 0.20
maliyet: 0.15
```

Skorun genel mantığı:

```text
yüksek popülerlik -> skoru artırır
düşük israf riski -> skoru artırır
beslenme dengesi -> skoru artırır
düşük maliyet -> skoru artırır
```

İsraf bileşeni şu mantıkla normalize edilir:

```text
israf_normalized = 1 - israf_orani
```

Yani israf oranı düşük olan yemeklerin optimizasyon skoru daha yüksek olur.

Menü oluşturulurken ayrıca bazı kısıtlar uygulanır:

```text
kritik israf uyarısı olan yemekleri atlama
aynı yemeği haftada en fazla 2 kez kullanma
aynı çorbayı aynı hafta tekrar etmemeye çalışma
aynı et tipini haftada sınırlama
alerjen sayısını sınırlama
vejetaryen gün dengesi sağlama
```

Bu bölümde de ML modeli karar desteği sağlar, fakat menüyü seçen mekanizma ağırlıklı optimizasyon ve kural setidir.

## 12. IoT ve Tartılmış İsraf Verisi

Projede IoT simülasyonu ve tartılmış israf alanları da vardır.

Ana sabit:

```text
ortalama porsiyon ağırlığı = 0.35 kg
```

Simülasyon mantığı:

```text
üretilen kg = üretilen porsiyon * 0.35
baz israf kg = üretilen kg * israf_orani / 100
simüle tartım = baz israf kg + rastgele sapma
```

Bu değer `tartilan_israf_kg` alanına yazılabilir. Ancak mevcut kodda tartılmış kg değeri ana `israf_orani` hesabının yerine geçmez. Ana israf oranı hala üretim ve kalan porsiyon üzerinden hesaplanır.

Bu ayrım önemlidir:

```text
kalan porsiyon tabanlı israf -> ana raporlama oranı
tartılan kg tabanlı israf -> IoT destekli ek ölçüm/karşılaştırma
```

## 13. Fotoğraf Çekip veya Resim Yükleyip Yemek Tanıma Özelliği

Güncel proje taramasına göre fotoğraf/resim yükleyerek yemek tanıma özelliği aktif uygulama akışından kaldırılmış görünmektedir.

### 13.1. Aktif Backend Durumu

Aktif route listesinde yemek tanıma endpointi bulunmamaktadır. `main.py` içinde dahil edilen route modülleri arasında `recognize`, `food_recognizer` veya benzeri bir modül yoktur.

Aktif route yapısında şunlar vardır:

```text
pages
menu
ratings
waste
analytics
reports
production
chatbot
notifications
tasks
websocket
experiments
auto_trainer
model_tracker
iot
maliyet
simulation
voting
xai
anomaly
```

Yemek tanıma route'u bu listede yoktur.

### 13.2. Silinen veya Eksik Dosyalar

Git durumunda şu dosyaların silinmiş olduğu görülmektedir:

```text
ai_yemekhane/modules/food_recognizer.py
ai_yemekhane/templates/recognize.html
```

Bu dosyalar daha önce aktif yemek tanıma özelliğine ait olabilecek dosyalardır. Güncel çalışma ağacında silinmiş görünüyorlar.

### 13.3. Mobil Uygulama Durumu

Mobil uygulamada aktif ekranlar şunlardır:

```text
MenuScreen
RateScreen
ChatScreen
StatsScreen
```

Yemek fotoğrafı çekme veya resim yükleyerek tanıma yapan ayrı bir ekran bulunmamaktadır.

### 13.4. Kalan Artıklar

Özellik aktif akıştan kaldırılmış olsa da projede bazı kalıntılar vardır:

```text
models_data/food_yolov8s_best.pt
models_data/yolov8s-cls.pt
models_data/yolo11n-seg.pt
YOLO eğitim scriptleri
expo-image-picker bağımlılığı
bazı dokümantasyon referansları
```

Bu nedenle teknik sonuç şudur:

```text
Aktif uygulamada fotoğrafla yemek tanıma akışı kaldırılmış veya devre dışı kalmış.
Ancak model dosyaları, eğitim materyali ve bazı bağımlılıklar projeden tamamen temizlenmemiş.
```

## 14. Önceki Rapora Göre En Önemli Değişiklikler

Bu güncellemede önceki rapora göre özellikle şu noktalar değişmiştir:

1. Porsiyon önerisi artık sadece kural tabanlı olarak açıklanmamalıdır. Güncel kod ML destekli hibrit porsiyon önerisi kullanmaktadır.
2. Model dosyaları ve metrikleri güncellenmiştir. Mevcut waste modeli 816 örnekle eğitilmiş ensemble modeldir.
3. `production_planner.py` ML tahminini doğrudan porsiyon önerisi hesabına dahil etmektedir.
4. Yemek tanıma özelliğinin aktif backend ve frontend akışından kaldırıldığı görülmektedir.
5. Maliyet tarafında birden fazla varsayılan maliyet katmanı olduğu görülmektedir: maliyet API, analytics hızlı özetleri ve menü optimizasyonu farklı varsayımlar kullanmaktadır.

## 15. Dikkat Edilmesi Gereken Teknik Noktalar

### 15.1. Porsiyon Planlama Formülünün Net Hali

Porsiyon önerisinde amaç sadece israfı azaltmak değildir. Sistem aynı zamanda öğrencilerin yemeksiz kalmaması için beklenen talebi de korur. Bu yüzden güncel çalışan mantık iki hesabı karşılaştırır:

```text
1. Talep tabanı:
   Ortalama tüketim + güvenlik payı

2. ML destekli azaltma önerisi:
   Geçmiş üretimden, tahmin edilen fazla israf kadar azaltılmış değer
```

Son porsiyon önerisi bu iki değerden büyük olanıdır:

```text
P = max(D + z*sigma, P_geçmiş * (1 - max(0, w_pred - %10)))
```

Bu formülün sade anlamı şudur:

```text
ML modeli yüksek israf bekliyorsa üretim azaltılır.
Ama önerilen porsiyon, beklenen talebi karşılayacak seviyenin altına düşürülmez.
```

Bu güncellemede `production_planner.py` içindeki açıklama da bu gerçek çalışan formülle uyumlu hale getirilmiştir.

### 15.2. Maliyet Varsayımları Tekleştirilmeli

Projede farklı alanlarda farklı maliyet varsayımları vardır:

```text
maliyet API kategori varsayımları
analytics varsayılan 35 TL
menü optimizasyonu kategori maliyetleri
```

Bu farklılık teknik olarak çalışır, ancak akademik rapor veya demo sırasında karışıklık yaratabilir. En doğru yaklaşım, tek bir merkezi maliyet konfigürasyonu kullanmak ve tüm modülleri buradan beslemektir.

### 15.3. Fotoğrafla Tanıma Kalıntıları Temizlenmeli

Özellik bilerek kaldırıldıysa dokümantasyon, bağımlılıklar ve model dosyaları temizlenmelidir. Eğer daha sonra geri getirilecekse route, sayfa ve mobil ekran tekrar eklenmelidir.

### 15.4. Model Kararı Nihai Gerçek Değildir

Model sadece tahmin üretir. Gerçek israfı belirleyen ana veri üretim logudur. Bu nedenle uygulama anlatılırken:

```text
gerçek israf = üretim logu hesabı
tahmini israf = ML modeli çıktısı
porsiyon önerisi = geçmiş tüketim + güvenlik payı + ML tahmini + kurallar
```

ayrımı net yapılmalıdır.

## 16. Sunumda Kullanılabilecek Net Cevaplar

### İsrafı model mi hesaplıyor?

Hayır. Gerçek israf oranı model tarafından hesaplanmaz. Üretilen porsiyon ve kalan porsiyon üzerinden doğrudan hesaplanır.

### Model ne yapıyor?

Model geçmiş verilere bakarak beklenen israf oranını tahmin eder. Bu tahmin üretim planlama, porsiyon önerisi ve karar destek ekranlarında kullanılır.

### Porsiyonu model mi belirliyor?

Tek başına model belirlemiyor. Porsiyon önerisini üretim planlama formülü hesaplıyor. Ancak bu formül ML modelinin tahmin ettiği israf oranını kullandığı için güncel sistem ML destekli hibrit çalışıyor.

### Öğrenci puanı ne işe yarıyor?

Öğrenci puanı model için önemli bir girdidir. Ayrıca model yoksa kural tabanlı israf tahmini için kullanılır. Düşük puan, daha yüksek israf veya düşük talep riski anlamına gelebilir.

### Maliyet nasıl hesaplanıyor?

Kalan porsiyon, porsiyon başı maliyetle çarpılır. Yemek bazlı maliyet girilmişse o kullanılır, yoksa kategori varsayılanı kullanılır. Bazı analytics ekranlarında hızlı hesap için 35 TL varsayılanı bulunur.

### Fotoğrafla yemek tanıma var mı?

Aktif uygulama akışında görünmüyor. Backend route, web sayfası ve mobil ekran tarafında bu özellik kaldırılmış görünüyor. Fakat model dosyaları ve bazı eğitim/bağımlılık kalıntıları projede duruyor.

## 17. Sonuç

Güncel projede israf hesaplama, ML tahminleme ve porsiyon önerisi birbirinden ayrı ama bağlantılı çalışmaktadır.

Gerçek israf hesabı basit ve denetlenebilir bir formüle dayanır:

```text
israf_orani = kalan_porsiyon / uretilen_porsiyon * 100
```

ML modeli bu gerçek israf kayıtlarından öğrenerek gelecek israf riskini tahmin eder.

Porsiyon önerisi ise artık sadece kural tabanlı değildir. Güncel sistem, son 60 günlük tüketim geçmişiyle talep tabanı oluşturur, tüketim değişkenliğine göre güvenlik payı ekler, trendi dikkate alır ve ML modelinin tahmin ettiği israf oranını kullanarak üretim azaltma sinyali üretir. Nihai öneri, talebi karşılamayı ve israfı azaltmayı aynı anda hedefleyen hibrit bir formülle hesaplanır.

Maliyet hesabı kalan porsiyon üzerinden parasal kaybı gösterir. Bu maliyet, hangi yemeklerde israf azaltmanın daha önemli olduğunu belirlemek için kullanılır.

Fotoğrafla/resim yükleyerek yemek tanıma özelliği ise güncel aktif uygulamadan kaldırılmış görünmektedir. Özelliğe ait bazı dosya ve bağımlılık kalıntıları durduğu için proje temizliği veya özelliğin geri eklenmesi konusunda net bir karar verilmesi önerilir.
