#!/usr/bin/env python3
"""
TEZ ÖZETLEYİCİ API
PDF dosyalarından metin çıkarıp özetleyen FastAPI uygulaması
"""

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import PyPDF2
import io
import os
from datetime import datetime
import re
from typing import Dict, Any
import logging
import requests
from bs4 import BeautifulSoup
import urllib.parse
import time

# Özetleme için kütüphaneler
# try:
#     from transformers import pipeline
#     TRANSFORMERS_VAR_MI = True
# except ImportError:
#     TRANSFORMERS_VAR_MI = False
TRANSFORMERS_VAR_MI = False  # Transformer'ı devre dışı bırak

try:
    import yake
    YAKE_VAR_MI = True
except ImportError:
    YAKE_VAR_MI = False

try:
    from rake_nltk import Rake
    RAKE_VAR_MI = True
except ImportError:
    RAKE_VAR_MI = False

# Logging ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI uygulaması
uygulama = FastAPI(
    title="🎓 Türkçe Tez Özetleyici API",
    description="""
    📚 **Türkçe PDF Tez Özetleyici API**
    
    Bu API ile PDF dosyalarınızı yükleyebilir ve Türkçe özetlerini alabilirsiniz.
    
    ## 🚀 Özellikler:
    - 📄 **PDF Okuma**: PDF dosyalarından metin çıkarma
    - 📝 **Akıllı Özetleme**: Gelişmiş algoritma ile özet oluşturma  
    - 🔑 **Anahtar Kelimeler**: Otomatik anahtar kelime çıkarma
    - 🇹🇷 **Türkçe Destek**: Türkçe karakterler ve dil desteği
    - 📊 **İstatistikler**: Detaylı analiz ve raporlama
    
    ## 📋 Kullanım:
    1. **PDF Yükleme**: `/pdf-yukle/` endpoint'ine PDF dosyanızı gönderin
    2. **Metin Özetleme**: `/metin-ozetle/` endpoint'ine metninizi gönderin
    """,
    version="1.0.0",
    contact={
        "name": "Tez Özetleyici API",
        "email": "destek@tezozet.com"
    }
)

# CORS ayarları
uygulama.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MetinOzetleyici:
    """Türkçe metin özetleme sınıfı"""
    
    def __init__(self):
        self.ozetleyici = None
        # Transformer modelini şimdilik atla - çok büyük
        # if TRANSFORMERS_VAR_MI:
        #     try:
        #         # Türkçe destekleyen özetleme modeli
        #         self.ozetleyici = pipeline("summarization", 
        #                                  model="facebook/bart-large-cnn")
        #         logger.info("BART özetleme modeli yüklendi")
        #     except Exception as e:
        #         logger.warning(f"BART modeli yüklenemedi: {e}")
        logger.info("Basit özetleme modu aktif")
    
    def pdf_den_metin_cikar(self, pdf_dosyasi) -> str:
        """PDF'den metin çıkarma"""
        try:
            pdf_okuyucu = PyPDF2.PdfReader(pdf_dosyasi)
            metin = ""
            
            for sayfa_numarasi in range(len(pdf_okuyucu.pages)):
                sayfa = pdf_okuyucu.pages[sayfa_numarasi]
                metin += sayfa.extract_text() + "\n"
            
            return metin.strip()
        except Exception as hata:
            logger.error(f"PDF okuma hatası: {hata}")
            raise HTTPException(status_code=400, detail=f"❌ PDF okuma hatası: {str(hata)}")

class YokTezArayici:
    """YÖK Tez Merkezi'nden tez arama ve çekme sınıfı"""
    
    def __init__(self):
        self.temel_url = "https://tez.yok.gov.tr/UlusalTezMerkezi/"
        self.arama_url = "https://tez.yok.gov.tr/UlusalTezMerkezi/tezSorguSonucYeni.jsp"
        self.oturum = requests.Session()
        
        # Headers - normal tarayıcı gibi görünmek için
        self.oturum.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'tr-TR,tr;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def tez_ara(self, anahtar_kelime: str, sayfa_sayisi: int = 1, tur: str = "tum") -> Dict:
        """YÖK Tez'de arama yap"""
        try:
            # Arama parametreleri
            arama_parametreleri = {
                'arama': anahtar_kelime,
                'tur': tur,  # "tum", "yuksek_lisans", "doktora"
                'sayfa': sayfa_sayisi,
                'kayitSayisi': '20'  # Sayfa başına sonuç sayısı
            }
            
            logger.info(f"YÖK Tez araması başlatılıyor: {anahtar_kelime}")
            
            # Arama yap
            yanit = self.oturum.get(self.arama_url, params=arama_parametreleri, timeout=30)
            yanit.raise_for_status()
            
            # HTML parse et
            soup = BeautifulSoup(yanit.text, 'html.parser')
            
            # Tez listesini çıkar
            tezler = self.tez_listesi_cıkar(soup)
            
            sonuc = {
                "arama_terimi": anahtar_kelime,
                "bulunan_tez_sayisi": len(tezler),
                "sayfa": sayfa_sayisi,
                "tezler": tezler,
                "durum": "başarılı",
                "zaman": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            return sonuc
            
        except Exception as e:
            logger.error(f"YÖK Tez arama hatası: {e}")
            return {
                "hata": str(e),
                "durum": "başarısız",
                "mesaj": "YÖK Tez araması yapılırken hata oluştu"
            }
    
    def tez_listesi_cıkar(self, soup) -> list:
        """HTML'den tez listesini çıkar"""
        tezler = []
        
        try:
            # Tez sonuçlarını bul (YÖK Tez HTML yapısına göre)
            tez_satirlari = soup.find_all('div', class_='tez-bilgi') or soup.find_all('tr')
            
            for satir in tez_satirlari[:10]:  # İlk 10 tez
                tez_bilgisi = self.tez_bilgisini_cıkar(satir)
                if tez_bilgisi:
                    tezler.append(tez_bilgisi)
                    
            # Eğer yukarıdaki selector çalışmazsa alternatif yöntem
            if not tezler:
                tezler = self.alternatif_tez_cikart(soup)
                
        except Exception as e:
            logger.warning(f"Tez listesi çıkarma uyarısı: {e}")
            
        return tezler
    
    def tez_bilgisini_cıkar(self, element) -> Dict:
        """Tek tez bilgisini çıkar"""
        try:
            tez = {}
            
            # Başlık
            baslik_elementi = element.find('a') or element.find('strong') or element.find('h3')
            if baslik_elementi:
                tez['baslik'] = baslik_elementi.get_text(strip=True)
                tez['link'] = baslik_elementi.get('href', '')
            
            # Yazar
            yazar_metni = element.get_text()
            if 'Yazar:' in yazar_metni:
                yazar = yazar_metni.split('Yazar:')[1].split('\n')[0].strip()
                tez['yazar'] = yazar
            
            # Üniversite
            if 'Üniversite:' in yazar_metni:
                universite = yazar_metni.split('Üniversite:')[1].split('\n')[0].strip()
                tez['universite'] = universite
            
            # Yıl
            yil_match = re.search(r'(\d{4})', yazar_metni)
            if yil_match:
                tez['yil'] = yil_match.group(1)
            
            # Tür (YL/DR)
            if 'Doktora' in yazar_metni or 'DR' in yazar_metni:
                tez['tur'] = 'Doktora'
            elif 'Yüksek' in yazar_metni or 'YL' in yazar_metni:
                tez['tur'] = 'Yüksek Lisans'
            else:
                tez['tur'] = 'Belirtilmemiş'
            
            return tez if tez.get('baslik') else None
            
        except Exception as e:
            logger.warning(f"Tez bilgisi çıkarma uyarısı: {e}")
            return None
    
    def alternatif_tez_cikart(self, soup) -> list:
        """Alternatif HTML parsing yöntemi"""
        tezler = []
        
        try:
            # Tüm text'i al ve pattern'lerle ara
            tum_metin = soup.get_text()
            
            # Basit pattern matching ile tez başlıklarını bul
            satirlar = tum_metin.split('\n')
            
            gecerli_tez = {}
            for satir in satirlar:
                satir = satir.strip()
                
                if len(satir) > 10 and not satir.startswith(('http', 'www', 'Sayfa')):
                    # Potansiyel tez başlığı
                    if len(satir) > 20 and len(satir) < 200:
                        if gecerli_tez.get('baslik'):
                            tezler.append(gecerli_tez)
                            gecerli_tez = {}
                        
                        gecerli_tez['baslik'] = satir
                        gecerli_tez['tur'] = 'Genel'
                        gecerli_tez['yil'] = '2024'
                        gecerli_tez['yazar'] = 'Belirtilmemiş'
                        gecerli_tez['universite'] = 'Belirtilmemiş'
                        
                        if len(tezler) >= 5:  # Maksimum 5 tez
                            break
                            
            if gecerli_tez.get('baslik'):
                tezler.append(gecerli_tez)
                
        except Exception as e:
            logger.warning(f"Alternatif parsing uyarısı: {e}")
            
        return tezler[:5]  # İlk 5 tez
    
    def tez_detay_al(self, tez_linki: str) -> Dict:
        """Tez detay sayfasından özet ve diğer bilgileri al"""
        try:
            if not tez_linki.startswith('http'):
                tez_linki = self.temel_url + tez_linki
                
            yanit = self.oturum.get(tez_linki, timeout=30)
            yanit.raise_for_status()
            
            soup = BeautifulSoup(yanit.text, 'html.parser')
            
            detay = {
                "link": tez_linki,
                "ozet": self.ozet_bul(soup),
                "anahtar_kelimeler": self.anahtar_kelimeler_bul(soup),
                "tam_bilgi": self.tam_bilgi_cıkar(soup)
            }
            
            return detay
            
        except Exception as e:
            logger.error(f"Tez detay alma hatası: {e}")
            return {"hata": str(e)}
    
    def ozet_bul(self, soup) -> str:
        """Tez özetini bul"""
        try:
            # Çeşitli özet selectors'ları dene
            ozet_selectors = [
                'div.ozet', '.abstract', '.summary', '#ozet', 
                'div:contains("Özet")', 'div:contains("Abstract")'
            ]
            
            for selector in ozet_selectors:
                ozet_elementi = soup.select_one(selector)
                if ozet_elementi:
                    return ozet_elementi.get_text(strip=True)
            
            # Text'de "Özet:" kelimesini ara
            tum_metin = soup.get_text()
            if 'Özet:' in tum_metin:
                ozet_baslangic = tum_metin.find('Özet:')
                ozet_bitis = tum_metin.find('Anahtar Kelimeler:', ozet_baslangic)
                if ozet_bitis == -1:
                    ozet_bitis = ozet_baslangic + 1000
                
                ozet = tum_metin[ozet_baslangic:ozet_bitis].replace('Özet:', '').strip()
                return ozet[:500] + "..." if len(ozet) > 500 else ozet
            
            return "Özet bulunamadı"
            
        except Exception as e:
            return f"Özet alma hatası: {str(e)}"
    
    def anahtar_kelimeler_bul(self, soup) -> list:
        """Anahtar kelimeleri bul"""
        try:
            # Anahtar kelime patternleri
            tum_metin = soup.get_text()
            
            patterns = [
                r'Anahtar Kelimeler?:\s*([^\n\r]+)',
                r'Keywords?:\s*([^\n\r]+)',
                r'Key words?:\s*([^\n\r]+)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, tum_metin, re.IGNORECASE)
                if match:
                    kelimeler_str = match.group(1)
                    kelimeler = [k.strip() for k in re.split(r'[,;]', kelimeler_str) if k.strip()]
                    return kelimeler[:10]  # İlk 10 anahtar kelime
            
            return []
            
        except Exception as e:
            return []
    
    def tam_bilgi_cıkar(self, soup) -> Dict:
        """Tez hakkında tam bilgi çıkar"""
        try:
            bilgi = {}
            tum_metin = soup.get_text()
            
            # Danışman
            if 'Danışman:' in tum_metin:
                danisman = re.search(r'Danışman:\s*([^\n\r]+)', tum_metin)
                if danisman:
                    bilgi['danisman'] = danisman.group(1).strip()
            
            # Sayfa sayısı
            sayfa_match = re.search(r'(\d+)\s*sayfa', tum_metin)
            if sayfa_match:
                bilgi['sayfa_sayisi'] = sayfa_match.group(1)
            
            # Dil
            if 'Türkçe' in tum_metin:
                bilgi['dil'] = 'Türkçe'
            elif 'İngilizce' in tum_metin:
                bilgi['dil'] = 'İngilizce'
            
            return bilgi
            
        except Exception as e:
            return {}
    
    def tez_pdf_indir(self, tez_linki: str, dosya_adi: str = None) -> str:
        """Tez PDF'ini indir (mümkünse)"""
        try:
            # Bu özellik YÖK Tez'in izin verdiği durumlar için
            # Çoğu tez erişim izni gerektiriyor
            
            logger.info("PDF indirme özelliği geliştirilmekte...")
            return "PDF indirme şu anda desteklenmiyor (erişim izni gerekli)"
            
        except Exception as e:
            return f"PDF indirme hatası: {str(e)}"
    
    def gelismis_arama(self, **kwargs) -> Dict:
        """Gelişmiş arama seçenekleri"""
        arama_parametreleri = {}
        
        # Arama terimleri
        if kwargs.get('baslik'):
            arama_parametreleri['baslik'] = kwargs['baslik']
        if kwargs.get('yazar'):
            arama_parametreleri['yazar'] = kwargs['yazar']
        if kwargs.get('universite'):
            arama_parametreleri['universite'] = kwargs['universite']
        if kwargs.get('yil_baslangic'):
            arama_parametreleri['yil1'] = kwargs['yil_baslangic']
        if kwargs.get('yil_bitis'):
            arama_parametreleri['yil2'] = kwargs['yil_bitis']
        if kwargs.get('tur'):
            arama_parametreleri['tur'] = kwargs['tur']  # "YL" veya "DR"
            
        try:
            yanit = self.oturum.get(self.arama_url, params=arama_parametreleri, timeout=30)
            yanit.raise_for_status()
            
            soup = BeautifulSoup(yanit.text, 'html.parser')
            tezler = self.tez_listesi_cıkar(soup)
            
            return {
                "arama_parametreleri": arama_parametreleri,
                "bulunan_tezler": tezler,
                "toplam": len(tezler),
                "durum": "başarılı"
            }
            
        except Exception as e:
            return {
                "hata": str(e),
                "durum": "başarısız"
            }
    
    def tez_ozetle_ve_analiz_et(self, tez_bilgisi: Dict, ozetleyici) -> Dict:
        """Bulunan tezi özetle ve analiz et"""
        try:
            # Tez detaylarını al
            if tez_bilgisi.get('link'):
                detay = self.tez_detay_al(tez_bilgisi['link'])
                
                # Özet varsa özetle
                if detay.get('ozet') and len(detay['ozet']) > 100:
                    kisa_ozet = ozetleyici.metin_ozetle(detay['ozet'], maksimum_uzunluk=300)
                    anahtar_kelimeler = ozetleyici.anahtar_kelime_cikar(detay['ozet'])
                    
                    return {
                        "tez_bilgisi": tez_bilgisi,
                        "orijinal_ozet": detay['ozet'],
                        "kisa_ozet": kisa_ozet,
                        "anahtar_kelimeler": anahtar_kelimeler,
                        "durum": "özetlendi"
                    }
            
            return {
                "tez_bilgisi": tez_bilgisi,
                "mesaj": "Özet metnine erişilemedi",
                "durum": "kısmi"
            }
            
        except Exception as e:
            return {
                "tez_bilgisi": tez_bilgisi,
                "hata": str(e),
                "durum": "hata"
            }
    
    def metni_temizle(self, metin: str) -> str:
        """Metni temizleme ve Türkçe karakterleri koruma"""
        # Türkçe karakterleri koru
        turkce_karakterler = "çğıöşüÇĞIİÖŞÜ"
        
        # Gereksiz boşlukları temizle
        metin = re.sub(r'\s+', ' ', metin)
        
        # Sadece Türkçe karakterler, harfler, sayılar ve temel noktalama işaretlerini koru
        metin = re.sub(r'[^\w\s.,!?;:çğıöşüÇĞIİÖŞÜ]', ' ', metin)
        
        # Çoklu boşlukları tek boşluğa çevir
        metin = ' '.join(metin.split())
        return metin.strip()
    
    def anahtar_kelime_cikar(self, metin: str, yontem: str = "yake") -> list:
        """Anahtar kelime çıkarma"""
        anahtar_kelimeler = []
        
        if yontem == "yake" and YAKE_VAR_MI:
            try:
                kelime_cikartici = yake.KeywordExtractor(
                    lan="tr",  # Türkçe
                    n=3,       # 3-gram'a kadar
                    dedupLim=0.7,
                    top=20
                )
                kelime_puanlari = kelime_cikartici.extract_keywords(metin)
                anahtar_kelimeler = [kelime[1] for kelime in kelime_puanlari]
            except Exception as hata:
                logger.warning(f"YAKE anahtar kelime çıkarma hatası: {hata}")
        
        elif yontem == "rake" and RAKE_VAR_MI:
            try:
                rake = Rake()
                rake.extract_keywords_from_text(metin)
                anahtar_kelimeler = rake.get_ranked_phrases()[:20]
            except Exception as hata:
                logger.warning(f"RAKE anahtar kelime çıkarma hatası: {hata}")
        
        return anahtar_kelimeler
    
    def basit_ozetle(self, metin: str, maksimum_cumle: int = 5) -> str:
        """Gelişmiş basit özetleme algoritması"""
        cumleler = metin.split('.')
        cumleler = [cumle.strip() for cumle in cumleler if len(cumle.strip()) > 20]
        
        if len(cumleler) <= maksimum_cumle:
            return '. '.join(cumleler) + '.'
        
        # Cümle skorlama
        kelime_sikligi = {}
        kelimeler = metin.lower().split()
        
        # Kelime frekansı hesapla
        for kelime in kelimeler:
            if kelime.isalpha() and len(kelime) > 3:
                kelime_sikligi[kelime] = kelime_sikligi.get(kelime, 0) + 1
        
        # Cümle skorları
        cumle_puanlari = {}
        for indeks, cumle in enumerate(cumleler):
            cumledeki_kelimeler = cumle.lower().split()
            puan = 0
            kelime_sayisi = 0
            
            for kelime in cumledeki_kelimeler:
                if kelime in kelime_sikligi:
                    puan += kelime_sikligi[kelime]
                    kelime_sayisi += 1
            
            if kelime_sayisi > 0:
                cumle_puanlari[indeks] = puan / kelime_sayisi
                
                # İlk ve son cümlelere bonus
                if indeks < 3 or indeks >= len(cumleler) - 3:
                    cumle_puanlari[indeks] *= 1.5
        
        # En yüksek skorlu cümleleri seç
        en_iyi_cumleler = sorted(cumle_puanlari.items(), 
                             key=lambda x: x[1], reverse=True)[:maksimum_cumle]
        
        # Orijinal sırayla düzenle
        en_iyi_cumleler.sort(key=lambda x: x[0])
        
        ozet_cumleleri = [cumleler[i] for i, _ in en_iyi_cumleler]
        return '. '.join(ozet_cumleleri) + '.'
    
    def metin_ozetle(self, metin: str, maksimum_uzunluk: int = 500) -> str:
        """Türkçe metin özetleme"""
        if not metin or len(metin.strip()) < 100:
            return "⚠️ Metin çok kısa, özetlenemeye uygun değil. En az 100 karakter gerekli."
        
        # Metni temizle
        temiz_metin = self.metni_temizle(metin)
        
        if len(temiz_metin) < 50:
            return "⚠️ Temizlenen metin çok kısa. Lütfen daha uzun bir metin sağlayın."
        
        # Basit özetleme algoritması kullan
        ozet = self.basit_ozetle(temiz_metin)
        
        if not ozet or len(ozet.strip()) < 20:
            return "⚠️ Özet oluşturulamadı. Metninizi kontrol edip tekrar deneyin."
            
        return ozet

# Global özetleyici ve YÖK arayıcı örnekleri
ozetleyici = MetinOzetleyici()
yok_arayici = YokTezArayici()

@uygulama.get("/")
async def ana_sayfa():
    """Ana sayfa"""
    return {
        "mesaj": "🎓 Tez Özetleyici API'ye Hoş Geldiniz",
        "versiyon": "1.0.0",
        "aciklama": "PDF dosyalarından metin çıkarıp Türkçe özetleyen API",
        "endpoint_ler": {
            "pdf_yukle": "/pdf-yukle/",
            "metin_ozetle": "/metin-ozetle/", 
            "dokumantasyon": "/docs"
        },
        "ozellikler": {
            "pdf_okuma": "✅",
            "akilli_ozet": "✅", 
            "anahtar_kelime": "✅",
            "turkce_destek": "✅"
        }
    }

@uygulama.post("/pdf-yukle/")
async def pdf_yukle(dosya: UploadFile = File(...)):
    """PDF yükleyip Türkçe özetleme"""
    
    # Dosya kontrolü
    if not dosya.filename.endswith('.pdf'):
        raise HTTPException(
            status_code=400, 
            detail="❌ Hata: Sadece PDF dosyaları kabul edilir (.pdf uzantılı)"
        )
    
    try:
        # Dosyayı oku
        icerik = await dosya.read()
        pdf_dosyasi = io.BytesIO(icerik)
        
        # Metni çıkar
        logger.info(f"PDF işleniyor: {dosya.filename}")
        metin = ozetleyici.pdf_den_metin_cikar(pdf_dosyasi)
        
        if not metin:
            raise HTTPException(
                status_code=400, 
                detail="❌ Hata: PDF'den metin çıkarılamadı. Dosya bozuk olabilir."
            )
        
        # Özetle
        ozet = ozetleyici.metin_ozetle(metin)
        
        # Anahtar kelimeleri çıkar
        anahtar_kelimeler = ozetleyici.anahtar_kelime_cikar(metin)
        
        # İstatistikler
        istatistikler = {
            "orijinal_uzunluk": len(metin),
            "ozet_uzunluk": len(ozet),
            "sikistirma_orani": round(len(ozet) / len(metin) * 100, 2),
            "kelime_sayisi": len(metin.split()),
            "ozet_kelime_sayisi": len(ozet.split()),
            "sayfa_tahmini": round(len(metin) / 2000)  # Sayfa başına ~2000 karakter
        }
        
        sonuc = {
            "durum": "✅ Başarılı",
            "dosya_adi": dosya.filename,
            "islem_zamani": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "orijinal_metin_onizleme": metin[:300] + "..." if len(metin) > 300 else metin,
            "ozet": ozet,
            "anahtar_kelimeler": anahtar_kelimeler[:10],  # İlk 10 anahtar kelime
            "istatistikler": istatistikler,
            "basarili": True,
            "mesaj": f"📄 '{dosya.filename}' başarıyla özetlendi!"
        }
        
        logger.info(f"PDF başarıyla işlendi: {dosya.filename}")
        return JSONResponse(content=sonuc)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Beklenmeyen hata: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"❌ İşlem sırasında hata oluştu: {str(e)}"
        )

@uygulama.post("/metin-ozetle/")
async def metin_ozetle_endpoint(veri: dict):
    """Direkt metin özetleme endpoint'i"""
    metin = veri.get("metin", "")
    
    if not metin:
        raise HTTPException(
            status_code=400, 
            detail="❌ Hata: 'metin' alanı gerekli ve boş olamaz"
        )
    
    if len(metin.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="❌ Hata: Metin çok kısa. En az 50 karakter olmalı."
        )
    
    try:
        ozet = ozetleyici.metin_ozetle(metin)
        anahtar_kelimeler = ozetleyici.anahtar_kelime_cikar(metin)
        
        # İstatistikler
        istatistikler = {
            "orijinal_uzunluk": len(metin),
            "ozet_uzunluk": len(ozet),
            "sikistirma_orani": round(len(ozet) / len(metin) * 100, 2),
            "kelime_sayisi": len(metin.split()),
            "ozet_kelime_sayisi": len(ozet.split())
        }
        
        sonuc = {
            "durum": "✅ Başarılı",
            "orijinal_metin": metin,
            "ozet": ozet,
            "anahtar_kelimeler": anahtar_kelimeler[:10],
            "istatistikler": istatistikler,
            "islem_zamani": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "basarili": True,
            "mesaj": "📝 Metin başarıyla özetlendi!"
        }
        
        return JSONResponse(content=sonuc)
        
    except Exception as e:
        logger.error(f"Metin özetleme hatası: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"❌ Özetleme sırasında hata oluştu: {str(e)}"
        )

@uygulama.post("/export-txt/")
async def txt_disarı_aktar(disarı_aktarma_verisi: dict):
    """TXT formatında dışarı aktarma"""
    try:
        from fastapi.responses import PlainTextResponse
        
        ozet = disarı_aktarma_verisi.get("ozet", "")
        anahtar_kelimeler = disarı_aktarma_verisi.get("anahtar_kelimeler", [])
        istatistikler = disarı_aktarma_verisi.get("istatistikler", {})
        
        icerik = f"""TEZ ÖZETİ
{'='*50}

📝 ÖZET:
{ozet}

🔑 ANAHTAR KELİMELER:
{', '.join(anahtar_kelimeler)}

📊 İSTATİSTİKLER:
• Orijinal Uzunluk: {istatistikler.get('orijinal_uzunluk', 0):,} karakter
• Özet Uzunluk: {istatistikler.get('ozet_uzunluk', 0):,} karakter
• Sıkıştırma Oranı: %{istatistikler.get('sikistirma_orani', 0)}
• Kelime Sayısı: {istatistikler.get('kelime_sayisi', 0):,} kelime

📅 Oluşturulma Tarihi: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
🛠️  Oluşturan: Türkçe Tez Özetleyici API
"""
        
        return PlainTextResponse(
            content=icerik, 
            headers={"Content-Disposition": "attachment; filename=tez-ozeti.txt"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TXT dışarı aktarma hatası: {str(e)}")

@uygulama.post("/export-json/")
async def json_disarı_aktar(disarı_aktarma_verisi: dict):
    """JSON formatında dışarı aktarma"""
    try:
        from fastapi.responses import JSONResponse
        
        disarı_aktarma_verisi["disarı_aktarma_tarihi"] = datetime.now().isoformat()
        disarı_aktarma_verisi["biçim"] = "JSON"
        disarı_aktarma_verisi["sürüm"] = "1.0"
        
        return JSONResponse(
            content=disarı_aktarma_verisi,
            headers={"Content-Disposition": "attachment; filename=tez-ozeti.json"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"JSON dışarı aktarma hatası: {str(e)}")

@uygulama.get("/batch-process/")
async def toplu_işlem_bilgi():
    """Toplu işleme bilgileri"""
    return {
        "desteklenen_biçimler": ["PDF", "TXT", "DOCX"],
        "en_fazla_dosya_sayısı": 10,
        "en_fazla_dosya_boyutu": "50MB",
        "tahmini_işlem_süresi": "2-5 dakika",
        "özellikler": [
            "Çoklu PDF işleme",
            "Toplu özet oluşturma",
            "Karşılaştırmalı analiz",
            "Birleşik rapor oluşturma"
        ],
        "durum": "geliştirme_aşamasında",
        "kullanılabilir": False
    }

@uygulama.post("/compare-texts/")
async def metinleri_karşılaştır(karşılaştırma_verisi: dict):
    """İki metin arasında karşılaştırma"""
    try:
        metin1 = karşılaştırma_verisi.get("metin1", "")
        metin2 = karşılaştırma_verisi.get("metin2", "")
        
        if not metin1 or not metin2:
            raise HTTPException(status_code=400, detail="İki metin de gereklidir")
        
        # Temel karşılaştırma
        kelime_sayisi_1 = len(metin1.split())
        kelime_sayisi_2 = len(metin2.split())
        
        # Ortak kelimeler
        kelimeler_1 = set(metin1.lower().split())
        kelimeler_2 = set(metin2.lower().split())
        ortak_kelimeler = kelimeler_1.intersection(kelimeler_2)
        
        benzerlik_orani = len(ortak_kelimeler) / len(kelimeler_1.union(kelimeler_2)) * 100
        
        sonuc = {
            "metin1_kelime_sayisi": kelime_sayisi_1,
            "metin2_kelime_sayisi": kelime_sayisi_2,
            "ortak_kelime_sayisi": len(ortak_kelimeler),
            "benzerlik_orani": round(benzerlik_orani, 2),
            "ortak_kelimeler": list(ortak_kelimeler)[:20],  # İlk 20 ortak kelime
            "farklilık_orani": round(100 - benzerlik_orani, 2),
            "analiz_tarihi": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return JSONResponse(content=sonuc)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Karşılaştırma hatası: {str(e)}")

# YÖK TEZ ENDPOİNT'LERİ

@uygulama.get("/yok-tez-ara/")
async def yok_tez_ara_get(anahtar_kelime: str, sayfa: int = 1, tur: str = "tum"):
    """YÖK Tez'de basit arama (GET metodu)"""
    try:
        sonuc = yok_arayici.tez_ara(anahtar_kelime, sayfa, tur)
        
        if sonuc.get("durum") == "başarılı":
            return JSONResponse(content={
                "durum": "✅ Başarılı",
                "arama_terimi": anahtar_kelime,
                "bulunan_tez_sayisi": sonuc["bulunan_tez_sayisi"],
                "sayfa": sayfa,
                "tezler": sonuc["tezler"],
                "basarili": True,
                "mesaj": f"🔍 '{anahtar_kelime}' için {sonuc['bulunan_tez_sayisi']} tez bulundu!"
            })
        else:
            raise HTTPException(status_code=500, detail=f"❌ Arama hatası: {sonuc.get('hata', 'Bilinmeyen hata')}")
            
    except Exception as e:
        logger.error(f"YÖK Tez arama hatası: {e}")
        raise HTTPException(status_code=500, detail=f"❌ YÖK Tez arama sırasında hata: {str(e)}")

@uygulama.post("/yok-tez-ara/")
async def yok_tez_ara_post(arama_verisi: dict):
    """YÖK Tez'de gelişmiş arama (POST metodu)"""
    try:
        anahtar_kelime = arama_verisi.get("anahtar_kelime", "")
        sayfa = arama_verisi.get("sayfa", 1)
        tur = arama_verisi.get("tur", "tum")
        
        if not anahtar_kelime:
            raise HTTPException(status_code=400, detail="❌ Anahtar kelime gereklidir!")
        
        sonuc = yok_arayici.tez_ara(anahtar_kelime, sayfa, tur)
        
        if sonuc.get("durum") == "başarılı":
            return JSONResponse(content={
                "durum": "✅ Başarılı", 
                "arama_parametreleri": arama_verisi,
                "sonuclar": sonuc,
                "basarili": True,
                "zaman": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "mesaj": f"🎯 YÖK Tez araması tamamlandı!"
            })
        else:
            return JSONResponse(content={
                "durum": "⚠️ Kısmi Başarı",
                "hata": sonuc.get("hata"),
                "mesaj": "YÖK Tez'e erişimde sorun yaşandı",
                "basarili": False
            })
            
    except Exception as e:
        logger.error(f"YÖK Tez POST arama hatası: {e}")
        raise HTTPException(status_code=500, detail=f"❌ Arama işlemi hatası: {str(e)}")

@uygulama.post("/yok-tez-ozet/")
async def yok_tez_ozet(ozet_verisi: dict):
    """YÖK Tez'den bulunan tezi özetle"""
    try:
        anahtar_kelime = ozet_verisi.get("anahtar_kelime", "")
        tez_indeksi = ozet_verisi.get("tez_indeksi", 0)  # Hangi tezi seçeceği
        
        if not anahtar_kelime:
            raise HTTPException(status_code=400, detail="❌ Anahtar kelime gereklidir!")
        
        # Önce tezleri ara
        arama_sonucu = yok_arayici.tez_ara(anahtar_kelime, 1, "tum")
        
        if arama_sonucu.get("durum") != "başarılı" or not arama_sonucu.get("tezler"):
            raise HTTPException(status_code=404, detail="❌ Tez bulunamadı!")
        
        # Seçilen tezi al
        if tez_indeksi >= len(arama_sonucu["tezler"]):
            tez_indeksi = 0
        
        secilen_tez = arama_sonucu["tezler"][tez_indeksi]
        
        # Tez detayını özetle
        ozet_sonucu = yok_arayici.tez_ozetle_ve_analiz_et(secilen_tez, ozetleyici)
        
        return JSONResponse(content={
            "durum": "✅ Başarılı",
            "arama_terimi": anahtar_kelime,
            "secilen_tez_indeksi": tez_indeksi,
            "tez_bilgileri": secilen_tez,
            "ozet_analizi": ozet_sonucu,
            "toplam_bulunan": len(arama_sonucu["tezler"]),
            "basarili": True,
            "mesaj": f"📚 '{secilen_tez.get('baslik', 'Bilinmeyen')}' tezi analiz edildi!",
            "zaman": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"YÖK Tez özetleme hatası: {e}")
        raise HTTPException(status_code=500, detail=f"❌ Tez özetleme hatası: {str(e)}")

@uygulama.post("/yok-gelismis-arama/")
async def yok_gelismis_arama(gelismis_arama_verisi: dict):
    """YÖK Tez'de gelişmiş arama seçenekleri"""
    try:
        # Gelişmiş arama parametreleri
        baslik = gelismis_arama_verisi.get("baslik", "")
        yazar = gelismis_arama_verisi.get("yazar", "")
        universite = gelismis_arama_verisi.get("universite", "")
        yil_baslangic = gelismis_arama_verisi.get("yil_baslangic", "")
        yil_bitis = gelismis_arama_verisi.get("yil_bitis", "")
        tur = gelismis_arama_verisi.get("tur", "")  # YL/DR
        
        if not any([baslik, yazar, universite]):
            raise HTTPException(status_code=400, detail="❌ En az bir arama kriteri gereklidir!")
        
        # Gelişmiş arama yap
        sonuc = yok_arayici.gelismis_arama(
            baslik=baslik,
            yazar=yazar,
            universite=universite,
            yil_baslangic=yil_baslangic,
            yil_bitis=yil_bitis,
            tur=tur
        )
        
        if sonuc.get("durum") == "başarılı":
            return JSONResponse(content={
                "durum": "✅ Başarılı",
                "arama_kriterleri": gelismis_arama_verisi,
                "bulunan_tezler": sonuc["bulunan_tezler"],
                "toplam": sonuc["toplam"],
                "basarili": True,
                "mesaj": f"🎯 Gelişmiş arama ile {sonuc['toplam']} tez bulundu!",
                "zaman": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        else:
            return JSONResponse(content={
                "durum": "❌ Başarısız",
                "hata": sonuc.get("hata"),
                "mesaj": "Gelişmiş arama yapılırken hata oluştu",
                "basarili": False
            })
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"YÖK gelişmiş arama hatası: {e}")
        raise HTTPException(status_code=500, detail=f"❌ Gelişmiş arama hatası: {str(e)}")

@uygulama.get("/yok-tez-detay/")
async def yok_tez_detay(tez_linki: str):
    """Belirli bir tezin detaylarını al"""
    try:
        if not tez_linki:
            raise HTTPException(status_code=400, detail="❌ Tez linki gereklidir!")
        
        detay = yok_arayici.tez_detay_al(tez_linki)
        
        if detay.get("hata"):
            raise HTTPException(status_code=500, detail=f"❌ Tez detay hatası: {detay['hata']}")
        
        return JSONResponse(content={
            "durum": "✅ Başarılı",
            "tez_linki": tez_linki,
            "detaylar": detay,
            "basarili": True,
            "mesaj": "📄 Tez detayları başarıyla alındı!",
            "zaman": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"YÖK Tez detay hatası: {e}")
        raise HTTPException(status_code=500, detail=f"❌ Tez detay alma hatası: {str(e)}")

@uygulama.get("/yok-tez-istatistik/")
async def yok_tez_istatistik():
    """YÖK Tez API kullanım istatistikleri"""
    return {
        "durum": "✅ Aktif",
        "desteklenen_ozellikler": [
            "🔍 Basit tez arama",
            "🎯 Gelişmiş arama (yazar, üniversite, yıl)",
            "📚 Tez özet analizi",
            "📄 Tez detay bilgileri",
            "🔗 Tez link işleme"
        ],
        "arama_turleri": {
            "tum": "Tüm tezler",
            "yuksek_lisans": "Yüksek Lisans tezleri",
            "doktora": "Doktora tezleri"
        },
        "limitler": {
            "sayfa_basina_sonuc": "20 tez",
            "maksimum_sayfa": "10 sayfa",
            "timeout": "30 saniye"
        },
        "uyarilar": [
            "⚠️ YÖK Tez erişim politikalarına uygun kullanım",
            "⚠️ PDF indirme çoğu tez için kısıtlı",
            "⚠️ Yoğun kulımda rate limiting olabilir"
        ],
        "mesaj": "🎓 YÖK Tez entegrasyonu aktif!",
        "versiyon": "1.0",
        "zaman": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

if __name__ == "__main__":
    print("🎓 Türkçe Tez Özetleyici API Başlatılıyor...")
    print("📖 Özellikler:")
    print(f"   - AI Modeller: {'❌ (hafif mod)' if not TRANSFORMERS_VAR_MI else '✅'}")
    print(f"   - YAKE Anahtar Kelime: {'✅' if YAKE_VAR_MI else '❌'}")
    print(f"   - RAKE Anahtar Kelime: {'✅' if RAKE_VAR_MI else '❌'}")
    print(f"   - Türkçe Destek: ✅")
    print(f"   - YÖK Tez Entegrasyonu: ✅")
    print("\n🌐 Türkçe API Endpoint'leri:")
    print("   - GET  /              : Ana sayfa")
    print("   - POST /pdf-yukle/    : PDF yükle ve Türkçe özetle")
    print("   - POST /metin-ozetle/ : Direkt metin Türkçe özetleme")
    print("   - GET  /docs          : API dokümantasyonu")
    print("\n🔍 YÖK Tez Endpoint'leri:")
    print("   - GET  /yok-tez-ara/      : YÖK Tez'de basit arama")
    print("   - POST /yok-tez-ara/      : YÖK Tez'de gelişmiş arama")
    print("   - POST /yok-tez-ozet/     : Bulunan tezi özetle")
    print("   - POST /yok-gelismis-arama/ : Detaylı arama seçenekleri")
    print("   - GET  /yok-tez-detay/    : Tez detay bilgileri")
    print("   - GET  /yok-tez-istatistik/ : YÖK Tez API durumu")
    print("\n💡 Kullanım Örnekleri:")
    print("   📄 PDF Özetleme: POST /pdf-yukle/ (multipart/form-data)")
    print("   📝 Metin Özetleme: POST /metin-ozetle/ {'metin': 'Uzun metniniz...'}")
    print("\n🚀 Server başlatılıyor...")
    
    uvicorn.run(
        "untitled_script:uygulama", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        log_level="info"
    )
