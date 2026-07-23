# YaguWiseAi'ni Windows'da Docker'siz ishlatish

Bu rejim faqat kompyuteringizda ishlaydi. Docker, Podman, Qdrant, Phoenix,
Ollama, GPU va tashqi API kaliti talab qilinmaydi. Ma'lumot tashqariga
yuborilmaydi.

## Birinchi ishga tushirish

PowerShell'ni loyiha papkasida oching va bajaring:

```powershell
.\start-local.ps1
```

Birinchi ishga tushirishda skript Python virtual muhitini yaratadi hamda Python
va Node paketlarini o'rnatadi. Keyingi safar ularni qayta o'rnatmaydi.

Brauzerda oching: <http://127.0.0.1:3000>

API hujjati: <http://127.0.0.1:8000/docs>

## To'xtatish

```powershell
.\stop-local.ps1
```

## Alohida o'rnatish

Paketlarni avval o'rnatib, keyin serverlarni boshlash ham mumkin:

```powershell
.\setup-local.ps1
.\start-local.ps1 -SkipSetup
```

Loglar `.local-run` papkasida saqlanadi. Lokal hujjatlar va indekslar `data`
papkasida saqlanadi.
