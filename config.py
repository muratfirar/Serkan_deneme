# TDHP (Tekdüzen Hesap Planı) Konfigürasyonu

class TDHPConfig:
    # Ana Gruplar
    ANA_GRUPLAR = {
        '1': 'DÖNEN VARLIKLAR',
        '2': 'DURAN VARLIKLAR',
        '3': 'KISA VADELİ YABANCI KAYNAKLAR',
        '4': 'UZUN VADELİ YABANCI KAYNAKLAR',
        '5': 'ÖZKAYNAKLAR'
    }

    # Alt Gruplar
    ALT_GRUPLAR = {
        # Dönen Varlıklar
        '10': 'HAZIR DEĞERLER',
        '11': 'MENKUL KIYMETLER',
        '12': 'TİCARİ ALACAKLAR',
        '13': 'DİĞER ALACAKLAR',
        '15': 'STOKLAR',
        '18': 'GELECEK AYLARA AİT GİDERLER VE GELİR TAHAKKUKLARI',
        '19': 'DİĞER DÖNEN VARLIKLAR',
        
        # Duran Varlıklar
        '20': 'TİCARİ ALACAKLAR',
        '22': 'MADDİ DURAN VARLIKLAR',
        '25': 'MADDİ OLMAYAN DURAN VARLIKLAR',
        '26': 'ÖZEL TÜKENMEYE TABİ VARLIKLAR',
        
        # Kısa Vadeli Yabancı Kaynaklar
        '30': 'MALİ BORÇLAR',
        '32': 'TİCARİ BORÇLAR',
        '33': 'DİĞER BORÇLAR',
        '36': 'ÖDENECEK VERGİ VE DİĞER YÜKÜMLÜLÜKLER',
        
        # Uzun Vadeli Yabancı Kaynaklar
        '40': 'MALİ BORÇLAR',
        '42': 'TİCARİ BORÇLAR',
        
        # Özkaynaklar
        '50': 'ÖDENMİŞ SERMAYE',
        '52': 'SERMAYE YEDEKLERİ',
        '54': 'KAR YEDEKLERİ',
        '57': 'GEÇMİŞ YILLAR KARLARI',
        '58': 'GEÇMİŞ YILLAR ZARARLARI',
        '59': 'DÖNEM NET KARI (ZARARI)'
    }

    # Hesap Grupları (Ana grup altındaki alt gruplar)
    HESAP_GRUPLARI = {
        '1': ['10', '11', '12', '13', '15', '18', '19'],  # Dönen Varlıklar
        '2': ['20', '22', '25', '26'],                    # Duran Varlıklar
        '3': ['30', '32', '33', '36'],                    # Kısa Vadeli Y.K.
        '4': ['40', '42'],                                # Uzun Vadeli Y.K.
        '5': ['50', '52', '54', '57', '58', '59']        # Özkaynaklar
    }

    @classmethod
    def get_ana_grup_adi(cls, kod):
        """Ana grup adını döndürür"""
        return cls.ANA_GRUPLAR.get(kod, f"{kod} ANA GRUP")

    @classmethod
    def get_alt_grup_adi(cls, kod):
        """Alt grup adını döndürür"""
        return cls.ALT_GRUPLAR.get(kod, f"{kod} HESAP GRUBU")

    @classmethod
    def get_alt_gruplar(cls, ana_grup):
        """Bir ana gruba ait alt grupları döndürür"""
        return cls.HESAP_GRUPLARI.get(ana_grup, []) 