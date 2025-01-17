import xml.etree.ElementTree as ET
from collections import defaultdict
from decimal import Decimal
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
from datetime import datetime
import os
import re

def dosya_sec():
    root = tk.Tk()
    root.withdraw()  # Ana pencereyi gizle
    
    dosya_yolu = filedialog.askopenfilename(
        title="Muhasebe XML Dosyasını Seçin",
        filetypes=[("XML Dosyaları", "*.xml"), ("Tüm Dosyalar", "*.*")],
        initialdir=Path.cwd()  # Mevcut çalışma dizininden başla
    )
    
    if dosya_yolu:
        print(f"\nSeçilen dosya: {dosya_yolu}")
        return dosya_yolu
    else:
        print("\nDosya seçilmedi!")
        return None

def cizgi_cek(uzunluk=100):
    print("=" * uzunluk)

def tablo_baslik_yazdir(baslik):
    cizgi_cek()
    print(f"{baslik:^100}")
    cizgi_cek()

def format_tutar(tutar):
    return f"{tutar:,.2f}".replace(",", ".")

def analiz_yap(xml_dosya):
    try:
        tree = ET.parse(xml_dosya)
        root = tree.getroot()
        
        # Firma ve Dönem Bilgileri
        firma_bilgileri = {
            'unvan': '',
            'vergi_no': '',
            'donem_baslangic': '',
            'donem_bitis': ''
        }
        
        # Dönem bilgilerini al - önce FiscalPeriod'u dene
        donem_sonu = None
        
        # 1. FiscalPeriod'dan dene
        fiscal_period = root.find('.//FiscalPeriod')
        if fiscal_period is not None:
            donem_sonu = fiscal_period.findtext('FiscalYearEnd')
        
        # 2. Son işlem tarihini bul
        if not donem_sonu:
            son_tarih = None
            for entry in root.findall('.//Entry'):
                header = entry.find('Header')
                if header is not None:
                    tarih = header.findtext('EnteredDate')
                    if tarih and (son_tarih is None or tarih > son_tarih):
                        son_tarih = tarih
            if son_tarih:
                donem_sonu = son_tarih
        
        # 3. Dosya adından tarihi çıkarmaya çalış
        if not donem_sonu and isinstance(xml_dosya, str):
            try:
                dosya_adi = os.path.basename(xml_dosya)
                # Tarih formatlarını kontrol et (YYYYMM, YYYY-MM, vb.)
                tarih_match = re.search(r'(20\d{2}[-_]?[01]\d)', dosya_adi)
                if tarih_match:
                    tarih_str = tarih_match.group(1).replace('_', '-')
                    if '-' not in tarih_str:
                        tarih_str = f"{tarih_str[:4]}-{tarih_str[4:]}"
                    donem_sonu = f"{tarih_str}-01"
            except:
                pass
        
        # 4. Son çare olarak bugünün tarihini kullan
        if not donem_sonu:
            donem_sonu = datetime.now().strftime('%Y-%m-%d')
            app.logger.warning(f'Dönem sonu tarihi bulunamadı, bugünün tarihi kullanılıyor: {donem_sonu}')
        
        # Mizan verilerini topla
        mizan = defaultdict(lambda: {
            'hesap_kodu': '',
            'hesap_adi': '',
            'borc': Decimal('0'),
            'alacak': Decimal('0'),
            'borc_bakiye': Decimal('0'),
            'alacak_bakiye': Decimal('0')
        })
        
        # Fiş listesini topla
        fis_listesi = []
        
        # Entry'leri bul (hem doğrudan root altında hem de Entries altında olabilir)
        entries = root.findall('.//Entry')
        
        # Her işlem için hesapları topla
        for entry in entries:
            header = entry.find('Header')
            if header is None:
                continue
            
            fis = {
                'no': header.findtext('EntryNumber', ''),
                'aciklama': header.findtext('EntryComment', ''),
                'tarih': header.findtext('EnteredDate', ''),
                'satirlar': []
            }
            
            for line in entry.findall('.//Line'):
                hesap_kodu = line.findtext('AccountMainID', '')
                hesap_adi = line.findtext('AccountMainDescription', '')
                tutar_text = line.findtext('Amount', '0')
                borc_alacak = line.findtext('DebitCreditCode', '')
                
                try:
                    tutar = Decimal(tutar_text.replace(',', '.'))
                except:
                    tutar = Decimal('0')
                
                if hesap_kodu:
                    # Mizan için hesapları topla
                    if hesap_kodu not in mizan:
                        mizan[hesap_kodu].update({
                            'hesap_kodu': hesap_kodu,
                            'hesap_adi': hesap_adi
                        })
                    
                    if borc_alacak == 'D':
                        mizan[hesap_kodu]['borc'] += tutar
                    elif borc_alacak == 'C':
                        mizan[hesap_kodu]['alacak'] += tutar
                    
                    # Fiş satırını ekle
                    fis['satirlar'].append({
                        'hesap_kodu': hesap_kodu,
                        'hesap_adi': hesap_adi,
                        'borc': tutar if borc_alacak == 'D' else Decimal('0'),
                        'alacak': tutar if borc_alacak == 'C' else Decimal('0')
                    })
            
            if fis['satirlar']:  # Sadece satırı olan fişleri ekle
                fis_listesi.append(fis)
        
        # Bakiyeleri hesapla
        toplam_borc = Decimal('0')
        toplam_alacak = Decimal('0')
        toplam_borc_bakiye = Decimal('0')
        toplam_alacak_bakiye = Decimal('0')
        
        for hesap in mizan.values():
            borc = hesap['borc']
            alacak = hesap['alacak']
            borc_bakiye = max(borc - alacak, Decimal('0'))
            alacak_bakiye = max(alacak - borc, Decimal('0'))
            
            hesap['borc_bakiye'] = borc_bakiye
            hesap['alacak_bakiye'] = alacak_bakiye
            
            toplam_borc += borc
            toplam_alacak += alacak
            toplam_borc_bakiye += borc_bakiye
            toplam_alacak_bakiye += alacak_bakiye
        
        app.logger.info(f'XML başarıyla analiz edildi. Dönem sonu: {donem_sonu}')
        return {
            'firma_bilgileri': firma_bilgileri,
            'mizan': list(mizan.values()),
            'fis_listesi': fis_listesi,
            'toplam': {
                'borc': float(toplam_borc),
                'alacak': float(toplam_alacak),
                'borc_bakiye': float(toplam_borc_bakiye),
                'alacak_bakiye': float(toplam_alacak_bakiye)
            },
            'donem_sonu': donem_sonu
        }
        
    except Exception as e:
        app.logger.error(f'XML analiz hatası: {str(e)}')
        raise ValueError(f'XML dosyası işlenirken hata oluştu: {str(e)}')

if __name__ == "__main__":
    print("Muhasebe Analiz Programı")
    print("------------------------")
    
    dosya_yolu = dosya_sec()
    if dosya_yolu:
        muhasebe_analizi(dosya_yolu) 