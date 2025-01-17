from app import app, db
from models import Firma
import click

@click.group()
def cli():
    """Veritabanı Yönetim Aracı"""
    pass

@cli.command()
def init_db():
    """Veritabanını oluştur"""
    with app.app_context():
        db.create_all()
        click.echo('Veritabanı oluşturuldu.')

@cli.command()
def drop_db():
    """Veritabanını sil"""
    if click.confirm('Tüm veriler silinecek. Emin misiniz?'):
        with app.app_context():
            db.drop_all()
            click.echo('Veritabanı silindi.')

@cli.command()
def list_firms():
    """Tüm firmaları listele"""
    with app.app_context():
        firmalar = Firma.query.all()
        if not firmalar:
            click.echo('Kayıtlı firma bulunamadı.')
            return
        
        for firma in firmalar:
            click.echo(f"""
ID: {firma.id}
Ünvan: {firma.unvan}
VKN: {firma.vergi_no}
Durum: {'Aktif' if firma.durum else 'Pasif'}
Oluşturma: {firma.olusturma_tarihi}
------------------------""")

@cli.command()
@click.option('--id', prompt='Firma ID', type=int, help='Silinecek firmanın ID\'si')
def delete_firm(id):
    """Firma sil"""
    with app.app_context():
        firma = Firma.query.get(id)
        if firma:
            if click.confirm(f'"{firma.unvan}" firması silinecek. Emin misiniz?'):
                db.session.delete(firma)
                db.session.commit()
                click.echo('Firma silindi.')
        else:
            click.echo('Firma bulunamadı.')

@cli.command()
def check_db():
    """Veritabanı durumunu kontrol et"""
    with app.app_context():
        try:
            firma_sayisi = Firma.query.count()
            click.echo(f"""
Veritabanı Durumu:
-----------------
Firma Sayısı: {firma_sayisi}
Bağlantı: Başarılı
""")
        except Exception as e:
            click.echo(f'Hata: {str(e)}')

if __name__ == '__main__':
    cli() 