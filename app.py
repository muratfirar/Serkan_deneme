from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from decimal import Decimal
import xml.etree.ElementTree as ET
from collections import defaultdict
import os
from werkzeug.utils import secure_filename
from datetime import datetime
from config import TDHPConfig
from models import db, Firma, FirmaTuru, MuhasebeVerisi
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# Veritabanı konfigürasyonu
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///muhasebe.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Diğer konfigürasyonlar
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SECRET_KEY'] = 'gizli-anahtar-buraya'
app.config['MAX_PERIODS'] = 3

# SQLAlchemy'yi başlat
db.init_app(app)

# Upload klasörünü oluştur
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Veritabanını oluştur
with app.app_context():
    db.create_all()

# Jinja2 filtresi - para formatı için
@app.template_filter('para_format')
def para_format(value):
    return f"{float(value):,.2f} ₺"

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/veri-girisi', methods=['GET'])
def veri_girisi():
    # Sayfa yüklenirken session'ı temizle
    for key in list(session.keys()):
        if key.startswith('sonuclar_donem_'):
            session.pop(key)
    return render_template('veri_girisi.html', max_periods=app.config['MAX_PERIODS'])

@app.route('/upload', methods=['POST'])
def upload():
    if 'files[]' not in request.files:
        return jsonify({'error': 'Dosya seçilmedi'}), 400
    
    files = request.files.getlist('files[]')
    firma_id = request.form.get('firma_id')
    
    if not firma_id:
        return jsonify({'error': 'Firma ID bulunamadı'}), 400
    
    if not files or all(file.filename == '' for file in files):
        return jsonify({'error': 'Lütfen en az bir XML dosyası seçin'}), 400

    results = []
    
    def process_file(file):
        try:
            # Geçici dosya oluştur
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # XML'i analiz et
            data = analiz_yap(filepath)
            
            # Dosyayı sil
            os.remove(filepath)
            
            return {
                'success': True,
                'data': data,
                'filename': filename
            }
        except Exception as e:
            app.logger.error(f'Dosya işleme hatası: {str(e)}')
            return {
                'success': False,
                'error': str(e),
                'filename': filename
            }
    
    # Çoklu thread ile dosyaları işle
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(process_file, files))
    
    # Hata kontrolü
    errors = [r for r in results if not r['success']]
    if errors:
        return jsonify({
            'error': 'Bazı dosyalar işlenemedi',
            'details': errors
        }), 400
    
    try:
        # Başarılı sonuçları veritabanına kaydet
        for result in results:
            data = result['data']
            
            try:
                # YYYY-MM formatına çevir
                donem_sonu = data.get('donem_sonu')
                if not donem_sonu:
                    raise ValueError('Dönem sonu bilgisi eksik')
                
                donem = datetime.strptime(donem_sonu, '%Y-%m-%d').strftime('%Y-%m')
                
                # Mevcut kayıtları kontrol et ve varsa güncelle
                existing_mizan = MuhasebeVerisi.query.filter_by(
                    firma_id=firma_id,
                    donem=donem,
                    veri_tipi='mizan'
                ).first()
                
                if existing_mizan:
                    existing_mizan.veri = {
                        'mizan': data['mizan'],
                        'toplam': data['toplam'],
                        'donem_sonu': donem_sonu
                    }
                else:
                    mizan_verisi = MuhasebeVerisi(
                        firma_id=firma_id,
                        donem=donem,
                        veri_tipi='mizan',
                        veri={
                            'mizan': data['mizan'],
                            'toplam': data['toplam'],
                            'donem_sonu': donem_sonu
                        }
                    )
                    db.session.add(mizan_verisi)
                
                # Fiş verilerini güncelle veya ekle
                existing_fis = MuhasebeVerisi.query.filter_by(
                    firma_id=firma_id,
                    donem=donem,
                    veri_tipi='fis'
                ).first()
                
                if existing_fis:
                    existing_fis.veri = {
                        'fis_listesi': data['fis_listesi'],
                        'donem_sonu': donem_sonu
                    }
                else:
                    fis_verisi = MuhasebeVerisi(
                        firma_id=firma_id,
                        donem=donem,
                        veri_tipi='fis',
                        veri={
                            'fis_listesi': data['fis_listesi'],
                            'donem_sonu': donem_sonu
                        }
                    )
                    db.session.add(fis_verisi)
                
            except Exception as e:
                app.logger.error(f'Veri kaydetme hatası: {str(e)}')
                db.session.rollback()
                raise
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Veriler başarıyla yüklendi',
            'redirect': url_for('firma_detay', id=firma_id)
        })
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Veritabanı hatası: {str(e)}')
        return jsonify({
            'error': 'Veriler kaydedilirken hata oluştu',
            'details': str(e)
        }), 500

@app.route('/mizan', methods=['GET'])
def mizan():
    # Tüm dönemlerin verilerini topla
    periods_data = {}
    for i in range(1, app.config['MAX_PERIODS'] + 1):
        if f'sonuclar_donem_{i}' in session:
            periods_data[i] = session[f'sonuclar_donem_{i}']
    
    return render_template('mizan.html', periods=periods_data)

@app.route('/bilanco', methods=['GET'])
def bilanco():
    periods_data = {}
    for i in range(1, app.config['MAX_PERIODS'] + 1):
        if f'sonuclar_donem_{i}' in session:
            data = session[f'sonuclar_donem_{i}']
            
            # Bilanço hesaplarını ve grup toplamlarını hesapla
            bilanco_hesaplari = {}
            grup_toplamlari = defaultdict(lambda: {
                'net_bakiye': Decimal('0'), 
                'tip': '',
                'hesap_adi': ''  # Alt grup adı için
            })
            ana_grup_toplamlari = defaultdict(lambda: {
                'net_bakiye': Decimal('0'), 
                'tip': '',
                'hesap_adi': ''  # Ana grup adı için
            })
            
            for hesap in data['mizan']:
                hesap_kodu = hesap['hesap_kodu']
                if hesap_kodu[0] in ['1', '2', '3', '4', '5']:
                    # Decimal olarak net bakiye hesapla
                    borc_bakiye = Decimal(str(hesap['borc_bakiye']))
                    alacak_bakiye = Decimal(str(hesap['alacak_bakiye']))
                    net_bakiye = abs(borc_bakiye - alacak_bakiye)
                    tip = 'Borç' if borc_bakiye > alacak_bakiye else 'Alacak'
                    
                    # Hesap detayı
                    bilanco_hesaplari[hesap_kodu] = {
                        'hesap_kodu': hesap_kodu,
                        'hesap_adi': hesap['hesap_adi'],
                        'net_bakiye': net_bakiye,
                        'tip': tip
                    }
                    
                    # Ana grup toplamı için
                    ana_grup = hesap_kodu[0]
                    ana_grup_toplamlari[ana_grup]['net_bakiye'] += net_bakiye
                    ana_grup_toplamlari[ana_grup]['tip'] = tip
                    ana_grup_toplamlari[ana_grup]['hesap_adi'] = TDHPConfig.get_ana_grup_adi(ana_grup)
                    
                    # Alt grup toplamı için
                    if len(hesap_kodu) >= 2:
                        alt_grup = hesap_kodu[:2]
                        grup_toplamlari[alt_grup]['net_bakiye'] += net_bakiye
                        grup_toplamlari[alt_grup]['tip'] = tip
                        grup_toplamlari[alt_grup]['hesap_adi'] = TDHPConfig.get_alt_grup_adi(alt_grup)
            
            periods_data[i] = {
                'bilanco': bilanco_hesaplari,
                'grup_toplamlari': dict(grup_toplamlari),
                'ana_grup_toplamlari': dict(ana_grup_toplamlari),
                'donem_sonu': data.get('donem_sonu', 'Tarih bilgisi yok')
            }
    
    return render_template('bilanco.html', periods=periods_data)

@app.route('/karsilastirmali-analiz', methods=['GET'])
def karsilastirmali_analiz():
    # Tüm dönemlerin verilerini topla
    periods_data = {}
    for i in range(1, app.config['MAX_PERIODS'] + 1):
        if f'sonuclar_donem_{i}' in session:
            periods_data[i] = session[f'sonuclar_donem_{i}']
    
    return render_template('karsilastirmali_analiz.html', periods=periods_data)

@app.route('/fisler', methods=['GET'])
def fisler():
    # Tüm dönemlerin verilerini topla
    periods_data = {}
    for i in range(1, app.config['MAX_PERIODS'] + 1):
        if f'sonuclar_donem_{i}' in session:
            periods_data[i] = session[f'sonuclar_donem_{i}']
    
    # Filtreleme
    fis_no = request.args.get('fis_no')
    tarih_baslangic = request.args.get('tarih_baslangic')
    tarih_bitis = request.args.get('tarih_bitis')
    hesap_kodu = request.args.get('hesap_kodu')
    donem = request.args.get('donem')
    
    # Seçili dönemin fişlerini al
    if donem and donem in periods_data:
        fis_listesi = periods_data[donem]['fis_listesi']
    else:
        # Tüm dönemlerin fişlerini birleştir
        fis_listesi = []
        for period_data in periods_data.values():
            fis_listesi.extend(period_data['fis_listesi'])
    
    # Filtreleri uygula
    if fis_no:
        fis_listesi = [f for f in fis_listesi if fis_no in f['no']]
    if tarih_baslangic:
        fis_listesi = [f for f in fis_listesi if f['tarih'] >= tarih_baslangic]
    if tarih_bitis:
        fis_listesi = [f for f in fis_listesi if f['tarih'] <= tarih_bitis]
    if hesap_kodu:
        fis_listesi = [f for f in fis_listesi if any(s['hesap_kodu'].startswith(hesap_kodu) for s in f['satirlar'])]
    
    return render_template('fisler.html', fis_listesi=fis_listesi, periods=periods_data)

@app.route('/firma-tanim', methods=['GET', 'POST'])
def firma_tanim():
    if request.method == 'POST':
        yeni_firma = Firma(
            firma_turu=request.form['firma_turu'],
            unvan=request.form['unvan'],
            vergi_no=request.form['vergi_no'],
            vergi_dairesi=request.form['vergi_dairesi'],
            adres=request.form['adres'],
            telefon=request.form['telefon'],
            email=request.form['email'],
            yetkili_adi=request.form['yetkili_adi'],
            yetkili_telefon=request.form['yetkili_telefon'],
            aciklama=request.form['aciklama']
        )
        db.session.add(yeni_firma)
        db.session.commit()
        return redirect(url_for('firma_listesi'))
    
    firma_turleri = FirmaTuru.choices()
    return render_template('firma_tanim.html', firma_turleri=firma_turleri)

@app.route('/firma-listesi')
def firma_listesi():
    firmalar = Firma.query.all()
    return render_template('firma_listesi.html', firmalar=firmalar)

@app.route('/firma-duzenle/<int:id>', methods=['GET', 'POST'])
def firma_duzenle(id):
    firma = Firma.query.get_or_404(id)
    if request.method == 'POST':
        firma.firma_turu = request.form['firma_turu']
        firma.unvan = request.form['unvan']
        firma.vergi_no = request.form['vergi_no']
        firma.vergi_dairesi = request.form['vergi_dairesi']
        firma.adres = request.form['adres']
        firma.telefon = request.form['telefon']
        firma.email = request.form['email']
        firma.yetkili_adi = request.form['yetkili_adi']
        firma.yetkili_telefon = request.form['yetkili_telefon']
        firma.aciklama = request.form['aciklama']
        db.session.commit()
        return redirect(url_for('firma_listesi'))
    
    firma_turleri = FirmaTuru.choices()
    return render_template('firma_tanim.html', firma=firma, firma_turleri=firma_turleri)

@app.route('/firma-sil/<int:id>', methods=['DELETE'])
def firma_sil(id):
    firma = Firma.query.get_or_404(id)
    db.session.delete(firma)
    db.session.commit()
    return '', 204

@app.route('/firma/<int:id>')
def firma_detay(id):
    firma = Firma.query.get_or_404(id)
    
    # Veritabanından dönem verilerini al
    muhasebe_verileri = MuhasebeVerisi.query.filter_by(firma_id=id).all()
    
    # Verileri dönemlere göre organize et
    periods = {}
    for veri in muhasebe_verileri:
        if veri.donem not in periods:
            periods[veri.donem] = {}
        
        if veri.veri_tipi == 'mizan':
            periods[veri.donem].update({
                'mizan': veri.veri['mizan'],
                'toplam': veri.veri['toplam']
            })
        elif veri.veri_tipi == 'fis':
            periods[veri.donem]['fis_listesi'] = veri.veri['fis_listesi']
    
    return render_template('firma_detay.html', 
                         firma=firma, 
                         periods=periods,
                         max_periods=app.config['MAX_PERIODS'])

def analiz_yap(xml_dosya):
    tree = ET.parse(xml_dosya)
    root = tree.getroot()
    
    # Firma bilgilerini al (XML'de yoksa varsayılan değerler kullan)
    firma_bilgileri = {
        'unvan': root.find('.//CompanyName').text if root.find('.//CompanyName') is not None else "Firma Adı Belirtilmemiş",
        'vkn': root.find('.//TaxNumber').text if root.find('.//TaxNumber') is not None else "VKN Belirtilmemiş",
        'donem': {
            'baslangic': root.find('.//FiscalYearStart').text,
            'bitis': root.find('.//FiscalYearEnd').text
        }
    }
    
    hesap_bakiyeleri = defaultdict(lambda: {'borc': Decimal('0'), 'alacak': Decimal('0'), 'hesap_adi': ''})
    fis_listesi = []
    
    for entry in root.findall('.//Entry'):
        fis = {
            'no': entry.find('.//EntryNumber').text,
            'tarih': entry.find('.//EnteredDate').text,
            'aciklama': entry.find('.//EntryComment').text,
            'satirlar': [],
            'toplam_borc': Decimal('0'),
            'toplam_alacak': Decimal('0')
        }
        
        for line in entry.findall('.//Line'):
            hesap_kodu = line.find('AccountMainID').text
            hesap_adi = line.find('AccountMainDescription').text
            tutar = Decimal(line.find('Amount').text)
            borc_alacak = line.find('DebitCreditCode').text
            
            # Hesap adını sakla
            hesap_bakiyeleri[hesap_kodu]['hesap_adi'] = hesap_adi
            
            satir = {
                'hesap_kodu': hesap_kodu,
                'hesap_adi': hesap_adi,
                'tutar': float(tutar),  # Template'de format için float'a çevir
                'borc_alacak': borc_alacak
            }
            
            if borc_alacak == 'D':
                hesap_bakiyeleri[hesap_kodu]['borc'] += tutar
                fis['toplam_borc'] += tutar
            else:
                hesap_bakiyeleri[hesap_kodu]['alacak'] += tutar
                fis['toplam_alacak'] += tutar
                
            fis['satirlar'].append(satir)
            
        # Fişin toplam tutarlarını float'a çevir
        fis['toplam_borc'] = float(fis['toplam_borc'])
        fis['toplam_alacak'] = float(fis['toplam_alacak'])
        fis_listesi.append(fis)
    
    # Mizan hesapla
    mizan = []
    toplam = {
        'borc': Decimal('0'),
        'alacak': Decimal('0'),
        'borc_bakiye': Decimal('0'),
        'alacak_bakiye': Decimal('0')
    }
    
    for hesap_kodu in sorted(hesap_bakiyeleri.keys()):
        borc = hesap_bakiyeleri[hesap_kodu]['borc']
        alacak = hesap_bakiyeleri[hesap_kodu]['alacak']
        borc_bakiye = max(borc - alacak, Decimal('0'))
        alacak_bakiye = max(alacak - borc, Decimal('0'))
        
        toplam['borc'] += borc
        toplam['alacak'] += alacak
        toplam['borc_bakiye'] += borc_bakiye
        toplam['alacak_bakiye'] += alacak_bakiye
        
        mizan.append({
            'hesap_kodu': hesap_kodu,
            'hesap_adi': hesap_bakiyeleri[hesap_kodu]['hesap_adi'],
            'borc': float(borc),
            'alacak': float(alacak),
            'borc_bakiye': float(borc_bakiye),
            'alacak_bakiye': float(alacak_bakiye)
        })
    
    # Toplamları float'a çevir
    toplam = {k: float(v) for k, v in toplam.items()}
    
    return {
        'firma_bilgileri': firma_bilgileri,
        'fis_listesi': fis_listesi,
        'mizan': mizan,
        'toplam': toplam
    }

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)  # use_reloader=False ekledik 