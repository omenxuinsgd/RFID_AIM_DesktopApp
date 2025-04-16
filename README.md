# Asset Inventory Management System (Desktop App)

Aplikasi desktop berbasis **PyQt6** untuk mengelola sistem inventaris aset dengan berbagai fitur seperti pelacakan, peminjaman, pengembalian, pembelian, dan manajemen aset menggunakan **RFID Reader** dan integrasi ke **database lokal**.

---

## 📦 Fitur Utama

- **Tracking**: Lacak keberadaan aset dengan antarmuka yang intuitif.
- **Borrowing**: Catat dan kelola proses peminjaman aset.
- **Returning**: Proses pengembalian aset oleh pengguna.
- **Purchasing**: Tambahkan data pembelian aset baru ke sistem.
- **Management**: Lakukan manajemen aset lanjutan dengan dukungan pembacaan RFID.

---

## 🧱 Struktur Proyek

```
project-root/
│
├── routes/                # Routing API
│   ├── assetRoutes.js
│   ├── authRoutes.js
│   ├── borrowingRoutes.js
│   └── checkoutRoutes.js
│
├── models/                # Skema MongoDB
│   └── Asset.js
│
├── controllers/           # Logic controller
│
├── middleware/            # Middleware auth dsb.
│
├── rfid_reader.py         # Kelas untuk pembacaan RFID
├── database.py            # Koneksi dan logika database
├── widgets.py             # Komponen GUI kustom (seperti MenuCard)
├── tracking_page.py       # Halaman pelacakan aset
├── borrowing_page.py      # Halaman peminjaman aset
├── returning_page.py      # Halaman pengembalian aset
├── purchasing_page.py     # Halaman pembelian aset
├── management_page.py     # Halaman manajemen aset (termasuk RFID)
├── styles.qss             # Stylesheet aplikasi (QSS)
├── server.js              # Entry point untuk backend (jika ada)
└── main.py                # Entry point aplikasi desktop
```

---

## 🚀 Cara Menjalankan Aplikasi

1. **Install dependensi Python**:

```bash
pip install PyQt6
```

2. **Jalankan aplikasi**:

```bash
python main.py
```

> Pastikan file `styles.qss` tersedia agar antarmuka tampil optimal.

---

## 🧩 Teknologi yang Digunakan

- **Python 3.x**
- **PyQt6** — Untuk pembuatan GUI
- **MongoDB (opsional)** — Untuk penyimpanan data
- **RFID Reader** — Untuk fitur manajemen aset berbasis tag RFID

---

## 📁 Catatan Tambahan

- Gambar ikon disimpan dalam folder `icons/`.
- File `styles.qss` dapat disesuaikan untuk mengubah tampilan antarmuka.
- Sistem ini cocok digunakan di lingkungan kantor, laboratorium, atau institusi pendidikan untuk mengelola aset secara digital dan efisien.

---

## 📌 Kontributor

- **Nama**: [Nur Rokhman](https://www.linkedin.com/in/nur-rokhman)
- **Email**: nurrokhman0302@gmail.com
- **Website**: https://portofolio-nurrokhman.vercel.app

---

## 🪪 Lisensi

Proyek ini dibuat untuk tujuan pengembangan internal. Silakan hubungi untuk kerjasama. MajoreIT License @2025

