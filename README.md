# StudyFlow 🌊

Çalışma saatlerini takip et, arkadaşlarınla gerçek zamanlı gör.

**Site:** https://bircanbektas.github.io/studyflow/

## Özellikler
- Derse tıklayarak kronometre; cihazlar arasında senkron
- Günlük/haftalık hedef, seri (streak), son 7 gün istatistikleri
- Oturumları elle ekleme ve düzenleme
- Arkadaşlar sekmesi: kim şu an neye çalışıyor, anlık
- Telefonda ana ekrana eklenebilir

## Yapı
- `index.html`: uygulamanın tamamı (GitHub Pages'ten yayınlanır)
- Firebase Authentication (e-posta/şifre) + Firestore, proje: `studyflow-c0ed6`
- `firestore.rules`: güvenlik kuralları; değişince Firebase Console > Firestore > Rules'a yapıştırılır
- `server.py`: sadece eski Render adresini yeni siteye yönlendirir
