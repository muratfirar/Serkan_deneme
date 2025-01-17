from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from enum import Enum

db = SQLAlchemy()

class FirmaTuru(str, Enum):
    SAHIS = 'Şahıs Firması'
    ANONIM = 'Anonim Şirket'
    LIMITED = 'Limited Şirket'
    KOMANDIT = 'Komandit Şirket'
    ADI_ORTAKLIK = 'Adi Ortaklık'
    KOOPERATIF = 'Kooperatif'
    DIGER = 'Diğer'

    @classmethod
    def choices(cls):
        return [(choice.name, choice.value) for choice in cls]

class Firma(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    firma_turu = db.Column(db.String(20), nullable=False)
    unvan = db.Column(db.String(200), nullable=False)
    vergi_no = db.Column(db.String(11), nullable=False, unique=True)
    vergi_dairesi = db.Column(db.String(100))
    adres = db.Column(db.Text)
    telefon = db.Column(db.String(20))
    email = db.Column(db.String(120))
    yetkili_adi = db.Column(db.String(100))
    yetkili_telefon = db.Column(db.String(20))
    aciklama = db.Column(db.Text)
    durum = db.Column(db.Boolean, default=True)
    olusturma_tarihi = db.Column(db.DateTime, default=datetime.utcnow)
    guncelleme_tarihi = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def firma_turu_adi(self):
        try:
            return FirmaTuru[self.firma_turu].value
        except (KeyError, TypeError):
            return '' 

class MuhasebeVerisi(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    firma_id = db.Column(db.Integer, db.ForeignKey('firma.id'), nullable=False)
    donem = db.Column(db.String(10), nullable=False)  # örn: "2024-01"
    veri_tipi = db.Column(db.String(20), nullable=False)  # "mizan", "fis", vs.
    veri = db.Column(db.JSON, nullable=False)
    olusturma_tarihi = db.Column(db.DateTime, default=datetime.utcnow)
    
    firma = db.relationship('Firma', backref=db.backref('muhasebe_verileri', lazy=True))

    __table_args__ = (
        db.UniqueConstraint('firma_id', 'donem', 'veri_tipi', name='unique_firma_donem_veri'),
    ) 